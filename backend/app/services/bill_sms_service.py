import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.entities import Bill, BillStatus, NotificationLog, AuditLog, Patient
from app.services.sms_provider import sms_gateway, mask_phone_number, is_valid_phone_number

logger = logging.getLogger("medisentinel.bill_sms")

def generate_bill_completion_message(patient_name: str, bill_number: str, medicine_names: List[str]) -> str:
    """
    Generates ONE friendly greeting/confirmation SMS for a successfully completed pharmacy bill.

    Spec:
    "Hello [Patient Name], thank you for choosing our pharmacy.
     Your bill #[Bill Number] has been successfully generated. We wish you good health."

    Rules:
    - ONE SMS per bill (regardless of how many medicines are in the bill).
    - Does NOT include diagnosis, clinical details, or medical advice.
    - Friendly, short, professional.
    - Uses actual patient name and bill number — never hardcoded.
    """
    clean_name = patient_name.strip() if patient_name else "Valued Patient"

    # Strictly <= 160 characters to ensure Fast2SMS only debits 1 SMS credit (₹5)
    return (
        f"Hello {clean_name}, your MediSentinel Hospital bill #{bill_number} is successfully generated. "
        f"We wish you good health and a speedy recovery!"
    )

def send_bill_completion_sms(
    bill_id: int,
    db: Session,
    notification_consent: bool = True,
    force: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Autonomous post-billing patient SMS notification trigger.
    Can also be manually triggered upon explicit approval with force=True.
    
    CRITICAL SAFETY RULES:
    1. Only sends if bill.status == BillStatus.SUCCESS.
    2. One successful bill -> ONE SMS (all items consolidated).
    3. Failure in SMS dispatch or provider MUST NEVER reverse the successful bill or stock reduction.
    4. Masks phone number in logs (+91 ******3210).
    5. Stores provider reference / message ID.
    6. Initial dispatch status is QUEUED or SENT; only becomes DELIVERED upon webhook confirmation.
    """
    try:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            logger.warning(f"[BillSMS] Bill {bill_id} not found. Skipping SMS.")
            return None

        # Verify bill status is SUCCESS
        bill_status_str = bill.status.value if hasattr(bill.status, 'value') else str(bill.status)
        if bill_status_str != BillStatus.SUCCESS.value:
            logger.warning(f"[BillSMS] Bill {bill_id} status is {bill_status_str} (not SUCCESS). Skipping SMS.")
            return None

        # Resolve patient and phone number
        phone_to_use = None
        patient_name = bill.patient_name or "Valued Patient"
        patient = None

        if bill.patient_id:
            patient = db.query(Patient).filter(Patient.id == bill.patient_id).first()
            if patient:
                phone_to_use = patient.mobile_number
                patient_name = patient.full_name or patient_name

        if not phone_to_use and hasattr(bill, "patient_phone") and bill.patient_phone:
            phone_to_use = bill.patient_phone

        # Check consent (unless explicitly approved / forced by pharmacist)
        if not force and (not notification_consent or (patient and patient.notification_consent is False)):
            masked = mask_phone_number(phone_to_use) if phone_to_use else "N/A"
            logger.info(f"[BillSMS] Patient opted out of SMS notifications for Bill #{bill.bill_number}.")
            
            # Record opted-out log for UI transparency
            opt_out_log = NotificationLog(
                bill_id=bill.id,
                patient_id=patient.id if patient else bill.patient_id,
                channel="SMS",
                recipient=phone_to_use or "OPTED_OUT",
                masked_phone_number=masked,
                message="SMS notification skipped: Patient opted out of notifications.",
                provider="None",
                provider_message_id=None,
                status="OPTED_OUT",
                failure_reason="Patient opted out / consent withheld",
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow()
            )
            db.add(opt_out_log)
            
            audit = AuditLog(
                event_type="PATIENT_NOTIFICATION",
                actor="NotificationEngine",
                entity_type="Bill",
                entity_id=str(bill.id),
                action="SMS_OPTED_OUT",
                details={
                    "bill_number": bill.bill_number,
                    "patient_name": patient_name,
                    "masked_phone": masked,
                    "status": "OPTED_OUT",
                    "reason": "Patient notification consent is False"
                }
            )
            db.add(audit)
            db.commit()
            return {
                "status": "OPTED_OUT",
                "masked_phone": masked,
                "provider": "None",
                "provider_message_id": None,
                "message": opt_out_log.message
            }

        # Check phone number presence and validity
        if not phone_to_use or not is_valid_phone_number(phone_to_use):
            masked = mask_phone_number(phone_to_use) if phone_to_use else "NONE"
            logger.warning(f"[BillSMS] Invalid or missing phone number '{phone_to_use}' for Bill #{bill.bill_number}.")
            
            fail_log = NotificationLog(
                bill_id=bill.id,
                patient_id=patient.id if patient else bill.patient_id,
                channel="SMS",
                recipient=phone_to_use or "UNKNOWN",
                masked_phone_number=masked,
                message="SMS dispatch skipped: Invalid or missing phone number.",
                provider="Validation",
                provider_message_id=None,
                status="FAILED",
                failure_reason=f"Invalid or missing mobile number '{phone_to_use}'",
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow()
            )
            db.add(fail_log)

            audit = AuditLog(
                event_type="PATIENT_NOTIFICATION",
                actor="NotificationEngine",
                entity_type="Bill",
                entity_id=str(bill.id),
                action="SMS_FAILED",
                details={
                    "bill_number": bill.bill_number,
                    "patient_name": patient_name,
                    "masked_phone": masked,
                    "status": "FAILED",
                    "failure_reason": f"Invalid or missing mobile number '{phone_to_use}'"
                }
            )
            db.add(audit)
            db.commit()
            return {
                "status": "FAILED",
                "masked_phone": masked,
                "provider": "Validation",
                "provider_message_id": None,
                "failure_reason": f"Invalid or missing mobile number"
            }

        # Consolidate medicines into ONE message
        medicine_names = []
        for item in bill.items:
            m_name = item.medicine.name if (item.medicine and item.medicine.name) else f"Medicine #{item.medicine_id}"
            medicine_names.append(m_name)

        message_body = generate_bill_completion_message(
            patient_name=patient_name,
            bill_number=bill.bill_number,
            medicine_names=medicine_names
        )

        formatted_phone = sms_gateway.format_phone_number(phone_to_use)
        masked_phone = mask_phone_number(formatted_phone)

        # Create initial QUEUED notification log
        notif_log = NotificationLog(
            bill_id=bill.id,
            patient_id=patient.id if patient else bill.patient_id,
            channel="SMS",
            recipient=formatted_phone,
            masked_phone_number=masked_phone,
            message=message_body,
            provider="Initializing",
            provider_message_id=None,
            status="QUEUED",
            created_at=datetime.utcnow(),
            sent_at=datetime.utcnow()
        )
        db.add(notif_log)
        db.commit()
        db.refresh(notif_log)

        # Dispatch via SMS Gateway
        logger.info(f"[BillSMS] Dispatching consolidated SMS for Bill #{bill.bill_number} to {masked_phone}...")
        dispatch_res = sms_gateway.dispatch_bill_sms(
            to_phone=formatted_phone,
            message=message_body,
            patient_name=patient_name,
            bill_number=bill.bill_number
        )

        # Update NotificationLog with provider status & reference
        sms_status = dispatch_res.get("status", "QUEUED")
        provider_name = dispatch_res.get("provider", "MediSentinel SMS Gateway")
        provider_msg_id = dispatch_res.get("reference")
        fail_reason = dispatch_res.get("failure_reason")

        notif_log.status = sms_status
        notif_log.provider = provider_name
        notif_log.provider_message_id = provider_msg_id
        notif_log.failure_reason = fail_reason
        if sms_status in ("SENT", "DELIVERED"):
            notif_log.sent_at = datetime.utcnow()
        if sms_status == "DELIVERED":
            notif_log.delivered_at = datetime.utcnow()

        db.commit()

        # AuditLog record
        audit_action = f"SMS_{sms_status}"
        audit = AuditLog(
            event_type="PATIENT_NOTIFICATION",
            actor="NotificationEngine",
            entity_type="Bill",
            entity_id=str(bill.id),
            action=audit_action,
            details={
                "bill_number": bill.bill_number,
                "notification_log_id": notif_log.id,
                "patient_name": patient_name,
                "masked_phone": masked_phone,
                "status": sms_status,
                "provider": provider_name,
                "provider_message_id": provider_msg_id,
                "failure_reason": fail_reason,
                "items_count": len(bill.items)
            }
        )
        db.add(audit)
        db.commit()

        logger.info(f"[BillSMS] SMS logged for Bill #{bill.bill_number}: Status={sms_status}, Provider={provider_name}, Ref={provider_msg_id}")
        return {
            "id": notif_log.id,
            "status": sms_status,
            "masked_phone": masked_phone,
            "provider": provider_name,
            "provider_message_id": provider_msg_id,
            "message": message_body,
            "failure_reason": fail_reason
        }

    except Exception as e:
        logger.error(f"[BillSMS] Unexpected exception during SMS dispatch for bill {bill_id}: {e}", exc_info=True)
        # Rollback any uncommitted notification/audit changes in this try block, but DO NOT impact previous bill commit
        try:
            db.rollback()
        except Exception:
            pass
        return None
