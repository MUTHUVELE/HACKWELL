import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import (
    Patient, MedicationReminder, NotificationLog, ReminderStatus,
    NotificationChannel, NotificationStatus, Bill, BillItem, Medicine
)
from app.schemas.schemas import ReminderProcessResult

logger = logging.getLogger("medisentinel.patient_reminders")

def calculate_finish_and_reminder_dates(
    bill_date: datetime,
    days_supply: int,
    window_days: Optional[int] = None
) -> tuple[date, date]:
    """
    Calculate estimated medicine finish date and reminder date.
    estimated_finish_date = bill_date + days_supply
    reminder_date = estimated_finish_date - reminder_window
    Clamps reminder_date to not precede the bill_date.
    """
    if days_supply <= 0:
        days_supply = 1
    
    window = window_days if window_days is not None else settings.REFILL_REMINDER_WINDOW_DAYS
    
    base_date = bill_date.date() if isinstance(bill_date, datetime) else bill_date
    finish_date = base_date + timedelta(days=days_supply)
    reminder_date = finish_date - timedelta(days=window)
    
    if reminder_date < base_date:
        reminder_date = base_date
        
    return finish_date, reminder_date

def generate_reminder_message(
    patient_name: str,
    medicine_name: str,
    finish_date: date
) -> str:
    """
    Generate professional, non-clinical reminder text strictly <= 160 chars
    to consume exactly 1 SMS credit (₹5) on Fast2SMS.
    """
    formatted_date = finish_date.strftime("%d-%b-%Y")
    clean_patient = patient_name.strip() if patient_name else "Patient"
    return (
        f"Dear {clean_patient}, your {medicine_name} refill from MediSentinel Pharmacy is due "
        f"around {formatted_date}. Please visit our pharmacy for a timely refill."
    )

def schedule_reminders_for_bill(bill_id: int, db: Session) -> List[MedicationReminder]:
    """
    Asynchronously/safely schedules medication reminders for all items in a bill
    that specify days_supply and have a registered patient.
    Wrapped in try/except so billing transaction is never reversed if scheduling encounters an issue.
    """
    created_reminders: List[MedicationReminder] = []
    try:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            logger.warning(f"schedule_reminders_for_bill: Bill #{bill_id} not found.")
            return []

        # Resolve patient: by bill.patient_id or fallback by matching patient_name
        patient = None
        if bill.patient_id:
            patient = db.query(Patient).filter(Patient.id == bill.patient_id).first()
        elif bill.patient_name:
            patient = db.query(Patient).filter(Patient.full_name.ilike(bill.patient_name.strip())).first()

        if not patient:
            logger.info(f"schedule_reminders_for_bill: No registered patient associated with Bill #{bill.bill_number}.")
            return []

        for item in bill.items:
            days_supply = item.days_supply
            # If days_supply is not set or <= 0, default to standard 30-day supply
            if not days_supply or days_supply <= 0:
                days_supply = 30

            med = item.medicine or db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
            med_name = med.name if med else f"Medicine #{item.medicine_id}"

            finish_date, reminder_date = calculate_finish_and_reminder_dates(
                bill.created_at or datetime.utcnow(),
                days_supply
            )

            msg = generate_reminder_message(patient.full_name, med_name, finish_date)

            reminder = MedicationReminder(
                patient_id=patient.id,
                bill_id=bill.id,
                bill_item_id=item.id,
                medicine_id=item.medicine_id,
                quantity=item.quantity,
                days_supply=days_supply,
                bill_date=bill.created_at or datetime.utcnow(),
                estimated_finish_date=finish_date,
                reminder_date=reminder_date,
                status=ReminderStatus.PENDING,
                notification_message=msg,
                created_at=datetime.utcnow()
            )
            db.add(reminder)
            created_reminders.append(reminder)

        if created_reminders:
            db.commit()
            for r in created_reminders:
                db.refresh(r)
            logger.info(f"Successfully scheduled {len(created_reminders)} refill reminders for Bill #{bill.bill_number}.")

    except Exception as e:
        logger.error(f"Error scheduling reminders for Bill #{bill_id}: {str(e)}", exc_info=True)
        db.rollback()

    return created_reminders

def process_due_reminders(
    target_date: Optional[date] = None,
    force_all: bool = False,
    db: Session = None
) -> ReminderProcessResult:
    """
    Scheduled job / on-demand process to evaluate active reminders.
    Criteria:
      - status == PENDING
      - current_date >= reminder_date (unless force_all=True)
      - notification_consent == True
      - idempotent: records status=DELIVERED/FAILED to prevent duplicate dispatches
    """
    check_date = target_date or datetime.utcnow().date()
    
    # Query all PENDING reminders
    pending_reminders = db.query(MedicationReminder).filter(
        MedicationReminder.status == ReminderStatus.PENDING
    ).all()

    total_checked = len(pending_reminders)
    sent_count = 0
    opted_out_count = 0
    failed_count = 0
    already_processed_count = 0
    details: List[Dict[str, Any]] = []

    for rem in pending_reminders:
        # Check if reminder date is reached unless force_all requested
        if not force_all and check_date < rem.reminder_date:
            continue

        patient = rem.patient
        med = rem.medicine

        # Check consent
        if not patient or not patient.notification_consent:
            rem.status = ReminderStatus.OPTED_OUT
            reason = "Patient has not opted in to refill reminders."
            log = NotificationLog(
                reminder_id=rem.id,
                channel="SMS",
                recipient=patient.mobile_number if patient else "N/A",
                message=rem.notification_message or "",
                status="OPTED_OUT",
                sent_at=datetime.utcnow(),
                failure_reason=reason
            )
            db.add(log)
            opted_out_count += 1
            details.append({
                "reminder_id": rem.id,
                "patient": patient.full_name if patient else "Unknown",
                "medicine": med.name if med else "Medicine",
                "status": "OPTED_OUT",
                "reason": reason
            })
            continue

        # Real SMS Provider Dispatch
        try:
            from app.services.sms_provider import sms_gateway
            dispatch_result = sms_gateway.dispatch_sms(
                to_phone=patient.mobile_number,
                message=rem.notification_message or "",
                patient_name=patient.full_name,
                medicine_name=med.name if med else "Medicine"
            )

            status_str = dispatch_result.get("status", "DELIVERED")
            provider_name = dispatch_result.get("provider", "SMS Provider")
            ref_id = dispatch_result.get("reference", "")
            fail_reason = dispatch_result.get("failure_reason")
            log_msg = f"[{provider_name} | Ref: {ref_id}] {rem.notification_message}" if ref_id else (rem.notification_message or "")

            if status_str in ("DELIVERED", "SENT", "QUEUED"):
                log = NotificationLog(
                    reminder_id=rem.id,
                    channel="SMS",
                    recipient=dispatch_result.get("recipient", patient.mobile_number),
                    message=log_msg,
                    status=status_str,
                    sent_at=datetime.utcnow(),
                    failure_reason=None
                )
                db.add(log)
                rem.status = ReminderStatus.DELIVERED
                sent_count += 1
                details.append({
                    "reminder_id": rem.id,
                    "patient": patient.full_name,
                    "medicine": med.name if med else "Medicine",
                    "status": status_str,
                    "provider": provider_name,
                    "reference": ref_id,
                    "recipient": dispatch_result.get("recipient", patient.mobile_number),
                    "finish_date": str(rem.estimated_finish_date),
                    "reminder_date": str(rem.reminder_date)
                })
            else:
                log = NotificationLog(
                    reminder_id=rem.id,
                    channel="SMS",
                    recipient=dispatch_result.get("recipient", patient.mobile_number),
                    message=log_msg,
                    status="FAILED",
                    sent_at=datetime.utcnow(),
                    failure_reason=fail_reason or f"SMS Gateway returned {status_str}"
                )
                db.add(log)
                rem.status = ReminderStatus.FAILED
                failed_count += 1
                details.append({
                    "reminder_id": rem.id,
                    "patient": patient.full_name if patient else "Unknown",
                    "medicine": med.name if med else "Medicine",
                    "status": "FAILED",
                    "provider": provider_name,
                    "reason": fail_reason or f"SMS Gateway returned {status_str}"
                })
        except Exception as e:
            rem.status = ReminderStatus.FAILED
            failed_count += 1
            log = NotificationLog(
                reminder_id=rem.id,
                channel="SMS",
                recipient=patient.mobile_number if patient else "Unknown",
                message=rem.notification_message or "",
                status="FAILED",
                sent_at=datetime.utcnow(),
                failure_reason=str(e)
            )
            db.add(log)
            details.append({
                "reminder_id": rem.id,
                "patient": patient.full_name if patient else "Unknown",
                "medicine": med.name if med else "Medicine",
                "status": "FAILED",
                "reason": str(e)
            })

    db.commit()

    return ReminderProcessResult(
        target_date=str(check_date),
        total_checked=total_checked,
        sent_count=sent_count,
        opted_out_count=opted_out_count,
        failed_count=failed_count,
        already_processed_count=already_processed_count,
        details=details
    )

def send_single_reminder(
    reminder_id: int,
    channel: str = "SMS",
    force: bool = False,
    db: Session = None
) -> Dict[str, Any]:
    """
    Manually dispatch or test a specific reminder notification from the management interface.
    """
    rem = db.query(MedicationReminder).filter(MedicationReminder.id == reminder_id).first()
    if not rem:
        raise ValueError(f"MedicationReminder with ID {reminder_id} not found.")

    patient = rem.patient
    if not patient:
        raise ValueError(f"No patient record associated with Reminder #{reminder_id}.")

    if not patient.notification_consent and not force:
        rem.status = ReminderStatus.OPTED_OUT
        db.commit()
        return {
            "status": "OPTED_OUT",
            "message": "Patient has not opted in to refill reminders.",
            "reminder_id": rem.id
        }

    from app.services.sms_provider import sms_gateway
    to_phone = patient.mobile_number if channel == "SMS" else (patient.email or patient.mobile_number)
    dispatch_res = sms_gateway.dispatch_sms(
        to_phone=to_phone,
        message=rem.notification_message or "",
        patient_name=patient.full_name,
        medicine_name=rem.medicine.name if rem.medicine else "Medicine"
    )

    status_str = dispatch_res.get("status", "DELIVERED")
    provider_name = dispatch_res.get("provider", "SMS Gateway")
    ref_id = dispatch_res.get("reference", "")
    fail_reason = dispatch_res.get("failure_reason")
    log_msg = f"[{provider_name} | Ref: {ref_id}] {rem.notification_message}" if ref_id else (rem.notification_message or "")

    if status_str in ("DELIVERED", "SENT", "QUEUED"):
        log = NotificationLog(
            reminder_id=rem.id,
            channel=channel,
            recipient=dispatch_res.get("recipient", to_phone),
            message=log_msg,
            status=status_str,
            sent_at=datetime.utcnow(),
            failure_reason=None
        )
        db.add(log)
        rem.status = ReminderStatus.DELIVERED
        db.commit()

        return {
            "status": status_str,
            "message": f"Refill reminder delivered to {patient.full_name} via {provider_name} [Ref: {ref_id}].",
            "reminder_id": rem.id,
            "recipient": log.recipient,
            "provider": provider_name,
            "reference": ref_id,
            "sent_at": log.sent_at.isoformat()
        }
    else:
        log = NotificationLog(
            reminder_id=rem.id,
            channel=channel,
            recipient=dispatch_res.get("recipient", to_phone),
            message=log_msg,
            status="FAILED",
            sent_at=datetime.utcnow(),
            failure_reason=fail_reason or f"SMS Gateway returned {status_str}"
        )
        db.add(log)
        rem.status = ReminderStatus.FAILED
        db.commit()

        return {
            "status": "FAILED",
            "message": f"Refill reminder dispatch failed via {provider_name}: {fail_reason or status_str}",
            "reminder_id": rem.id,
            "recipient": log.recipient,
            "provider": provider_name,
            "reference": ref_id,
            "failure_reason": fail_reason,
            "sent_at": log.sent_at.isoformat()
        }

def seed_default_patients(db: Session) -> int:
    """
    Pre-populates authorized sample patients if table is empty.
    Allows Chief Pharmacist to immediately pick patients during billing.
    """
    if db.query(Patient).count() > 0:
        return 0

    sample_patients = [
        {
            "patient_id": "PID-4001",
            "full_name": "Arun Kumar",
            "mobile_number": "+91 98401 23456",
            "email": "arun.kumar@healthcare.net",
            "notification_consent": True,
            "company_id": 1,
            "branch_id": 1
        },
        {
            "patient_id": "PID-4002",
            "full_name": "Priya Sharma",
            "mobile_number": "+91 98402 34567",
            "email": "priya.sharma@healthcare.net",
            "notification_consent": True,
            "company_id": 1,
            "branch_id": 1
        },
        {
            "patient_id": "PID-4003",
            "full_name": "Rajesh Verma",
            "mobile_number": "+91 98403 45678",
            "email": "rajesh.verma@healthcare.net",
            "notification_consent": False,  # Opted out to demonstrate consent enforcement
            "company_id": 1,
            "branch_id": 1
        },
        {
            "patient_id": "PID-4004",
            "full_name": "Deepa Menon",
            "mobile_number": "+91 98404 56789",
            "email": "deepa.menon@healthcare.net",
            "notification_consent": True,
            "company_id": 1,
            "branch_id": 1
        },
        {
            "patient_id": "PID-4005",
            "full_name": "Karthik Sundaram",
            "mobile_number": "+91 98405 67890",
            "email": "karthik.s@healthcare.net",
            "notification_consent": True,
            "company_id": 1,
            "branch_id": 1
        }
    ]

    for p_data in sample_patients:
        patient = Patient(**p_data)
        db.add(patient)

    db.commit()
    logger.info(f"Seeded {len(sample_patients)} default patients for refill reminders.")
    return len(sample_patients)
