import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import NotificationLog, AuditLog, Bill, UserRole
from app.schemas.schemas import SMSDeliveryWebhookPayload, SMSDeliveryWebhookResponse
from app.services.auth_service import require_role

logger = logging.getLogger("medisentinel.sms_webhook")

router = APIRouter(prefix="/api/notifications/sms", tags=["SMS Notifications"])

@router.post("/webhook", response_model=SMSDeliveryWebhookResponse)
async def sms_delivery_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public webhook receiver for SMS Provider Delivery Receipts (DLR).
    Supports:
    - Twilio status callbacks (MessageSid, MessageStatus)
    - Fast2SMS DLR callbacks
    - Generic HTTP SMS Gateway callbacks
    - Carrier delivery webhooks

    Transitions status from SENT/QUEUED to DELIVERED or FAILED upon carrier acknowledgment.
    """
    body_data: Dict[str, Any] = {}
    
    # Try parsing JSON or Form data
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_data = await request.json()
        except Exception:
            body_data = {}
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            body_data = dict(form)
        except Exception:
            body_data = {}
    else:
        # Fallback to query params or json
        try:
            body_data = await request.json()
        except Exception:
            body_data = dict(request.query_params)

    # Extract provider message ID
    provider_msg_id = (
        body_data.get("provider_message_id")
        or body_data.get("message_sid")
        or body_data.get("MessageSid")
        or body_data.get("sms_id")
        or body_data.get("id")
        or body_data.get("request_id")
    )

    # Extract raw status
    raw_status = (
        body_data.get("status")
        or body_data.get("MessageStatus")
        or body_data.get("delivery_status")
        or ""
    ).lower().strip()

    err_reason = (
        body_data.get("error_message")
        or body_data.get("ErrorMessage")
        or body_data.get("failure_reason")
    )

    logger.info(f"[SMSWebhook] Received DLR for MessageID '{provider_msg_id}', Status '{raw_status}'")

    if not provider_msg_id:
        return SMSDeliveryWebhookResponse(
            status="ignored",
            message="No provider message ID found in payload.",
            updated_records=0
        )

    # Find matching NotificationLog record
    matching_logs = db.query(NotificationLog).filter(
        NotificationLog.provider_message_id == str(provider_msg_id)
    ).all()

    if not matching_logs:
        logger.warning(f"[SMSWebhook] No notification log matched provider_message_id: '{provider_msg_id}'")
        return SMSDeliveryWebhookResponse(
            status="not_found",
            message=f"No notification log matched message ID '{provider_msg_id}'.",
            updated_records=0
        )

    # Normalize status to standard enum strings
    new_status = "DELIVERED"
    if raw_status in ("failed", "undelivered", "rejected", "bounced"):
        new_status = "FAILED"
    elif raw_status in ("sent", "dispatched"):
        new_status = "SENT"
    elif raw_status in ("queued", "accepted", "sending"):
        new_status = "QUEUED"
    elif raw_status in ("delivered", "success", "confirmed", "d"):
        new_status = "DELIVERED"

    updated_count = 0
    now = datetime.utcnow()

    for log_item in matching_logs:
        old_status = log_item.status
        log_item.status = new_status
        if new_status == "DELIVERED":
            log_item.delivered_at = now
        elif new_status == "FAILED" and err_reason:
            log_item.failure_reason = str(err_reason)
        
        # Write AuditLog
        audit = AuditLog(
            event_type="PATIENT_NOTIFICATION",
            actor="SMSDeliveryWebhook",
            entity_type="NotificationLog",
            entity_id=str(log_item.id),
            action=f"SMS_{new_status}",
            details={
                "notification_log_id": log_item.id,
                "bill_id": log_item.bill_id,
                "provider": log_item.provider,
                "provider_message_id": log_item.provider_message_id,
                "masked_phone": log_item.masked_phone_number,
                "old_status": old_status,
                "new_status": new_status,
                "failure_reason": err_reason
            }
        )
        db.add(audit)
        updated_count += 1

    db.commit()
    logger.info(f"[SMSWebhook] Updated {updated_count} log(s) for message '{provider_msg_id}' to {new_status}.")

    return SMSDeliveryWebhookResponse(
        status="success",
        message=f"Successfully transitioned message '{provider_msg_id}' to {new_status}.",
        updated_records=updated_count
    )

@router.post("/simulate-delivery/{log_id}")
def simulate_sms_delivery(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value, UserRole.ADMIN.value]))
):
    """
    Simulates carrier delivery receipt callback for a queued/sent message.
    Updates NotificationLog to DELIVERED with delivered_at timestamp and creates audit log.
    Accessible to PHARMACIST and ADMIN.
    """
    log_item = db.query(NotificationLog).filter(NotificationLog.id == log_id).first()
    if not log_item:
        raise HTTPException(status_code=404, detail="Notification log not found.")

    old_status = log_item.status
    log_item.status = "DELIVERED"
    log_item.delivered_at = datetime.utcnow()

    audit = AuditLog(
        event_type="PATIENT_NOTIFICATION",
        actor=current_user.get("sub", "Pharmacist"),
        entity_type="NotificationLog",
        entity_id=str(log_item.id),
        action="SMS_DELIVERED",
        details={
            "notification_log_id": log_item.id,
            "bill_id": log_item.bill_id,
            "provider": log_item.provider,
            "provider_message_id": log_item.provider_message_id,
            "masked_phone": log_item.masked_phone_number,
            "old_status": old_status,
            "new_status": "DELIVERED"
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(log_item)

    return {
        "status": "DELIVERED",
        "notification_id": log_item.id,
        "bill_id": log_item.bill_id,
        "masked_phone": log_item.masked_phone_number,
        "provider": log_item.provider,
        "provider_message_id": log_item.provider_message_id,
        "delivered_at": log_item.delivered_at
    }

@router.get("/bill/{bill_id}")
def get_bill_sms_status(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value, UserRole.ADMIN.value]))
):
    """
    Get the SMS notification logs and status for a specific pharmacy bill.
    Accessible to PHARMACIST and ADMIN.
    """
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found.")

    logs = db.query(NotificationLog).filter(NotificationLog.bill_id == bill_id).order_by(NotificationLog.id.desc()).all()
    
    return {
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "patient_name": bill.patient_name,
        "total_notifications": len(logs),
        "notifications": [
            {
                "id": l.id,
                "status": l.status,
                "masked_phone": l.masked_phone_number,
                "provider": l.provider,
                "provider_message_id": l.provider_message_id,
                "message": l.message,
                "created_at": l.created_at,
                "sent_at": l.sent_at,
                "delivered_at": l.delivered_at,
                "failure_reason": l.failure_reason
            }
            for l in logs
        ]
    }

@router.get("/logs")
def get_sms_logs(
    bill_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value, UserRole.ADMIN.value]))
):
    """
    List recent SMS notification logs across pharmacy dispensing operations.
    Accessible to PHARMACIST and ADMIN.
    """
    query = db.query(NotificationLog)
    if bill_id:
        query = query.filter(NotificationLog.bill_id == bill_id)
    if status:
        query = query.filter(NotificationLog.status == status)

    logs = query.order_by(NotificationLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "bill_id": l.bill_id,
            "patient_id": l.patient_id,
            "channel": l.channel,
            "status": l.status,
            "masked_phone": l.masked_phone_number,
            "provider": l.provider,
            "provider_message_id": l.provider_message_id,
            "message": l.message,
            "created_at": l.created_at,
            "sent_at": l.sent_at,
            "delivered_at": l.delivered_at,
            "failure_reason": l.failure_reason
        }
        for l in logs
    ]
