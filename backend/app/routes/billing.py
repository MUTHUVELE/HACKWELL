import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.entities import (
    Medicine, Ward, Inventory, InventoryBatch, Bill, BillItem,
    BillStatus, BatchStatus, AuditLog, DataAuditTrail, UserRole,
    Patient, MedicationReminder, ReminderStatus, NotificationLog
)
from app.schemas.schemas import (
    BillCreateRequest, BillResponse, BillItemDetailResponse, BillCancelResponse
)
from app.services.auth_service import require_role, get_current_user

logger = logging.getLogger("medisentinel.billing")

router = APIRouter(prefix="/api/billing", tags=["Billing"])

def _format_bill_response(bill: Bill, db: Session) -> Dict[str, Any]:
    """Helper to format a Bill entity into the BillResponse schema dictionary."""
    ward_name = bill.ward.name if bill.ward else (f"Ward {bill.ward_id}" if bill.ward_id else "Central Pharmacy")
    
    # Count any scheduled refill reminders for this bill
    reminders_count = db.query(MedicationReminder).filter(MedicationReminder.bill_id == bill.id).count()

    # Retrieve autonomous SMS delivery status for this bill
    sms_log = db.query(NotificationLog).filter(NotificationLog.bill_id == bill.id).order_by(NotificationLog.id.desc()).first()
    sms_detail = None
    if sms_log:
        status_msg = ""
        if sms_log.status == "DELIVERED":
            status_msg = f"Delivered via {sms_log.provider or 'Carrier'}"
        elif sms_log.status == "SENT":
            status_msg = f"Dispatched via {sms_log.provider or 'SMS Gateway'} (Ref: {sms_log.provider_message_id})"
        elif sms_log.status == "QUEUED":
            status_msg = f"Queued at {sms_log.provider or 'SMS Provider'} (Ref: {sms_log.provider_message_id})"
        elif sms_log.status == "NOT_CONFIGURED":
            status_msg = "SMS gateway credentials not configured."
        elif sms_log.status == "OPTED_OUT":
            status_msg = "Patient opted out of notifications."
        else:
            status_msg = f"Delivery failed: {sms_log.failure_reason or 'Provider error'}"

        sms_detail = {
            "id": sms_log.id,
            "status": sms_log.status,
            "masked_phone": sms_log.masked_phone_number,
            "provider": sms_log.provider,
            "provider_message_id": sms_log.provider_message_id,
            "message": sms_log.message,
            "status_message": status_msg,
            "failure_reason": sms_log.failure_reason,
            "created_at": sms_log.created_at,
            "sent_at": sms_log.sent_at,
            "delivered_at": sms_log.delivered_at
        }

    items_data = []
    for item in bill.items:
        med = item.medicine or db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
        ward_item = item.ward or (db.query(Ward).filter(Ward.id == item.ward_id).first() if item.ward_id else None)
        ward_item_name = ward_item.name if ward_item else (ward_name if not item.ward_id else f"Ward {item.ward_id}")
        items_data.append({
            "id": item.id,
            "medicine_id": item.medicine_id,
            "inventory_id": item.inventory_id,
            "ward_id": item.ward_id or bill.ward_id,
            "ward_name": ward_item_name,
            "medicine_name": med.name if med else f"Medicine #{item.medicine_id}",
            "medicine_code": med.code if med else "",
            "quantity": item.quantity,
            "days_supply": item.days_supply,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
            "previous_stock": item.previous_stock,
            "updated_stock": item.updated_stock,
            "batch_deductions": item.batch_deductions or []
        })

    return {
        "id": bill.id,
        "bill_number": bill.bill_number,
        "company_id": bill.company_id,
        "branch_id": bill.branch_id,
        "ward_id": bill.ward_id,
        "ward_name": ward_name,
        "created_by": bill.created_by,
        "role": bill.role,
        "status": bill.status.value if hasattr(bill.status, 'value') else str(bill.status),
        "subtotal": bill.subtotal,
        "total_amount": bill.total_amount,
        "patient_id": bill.patient_id,
        "patient_name": bill.patient_name,
        "patient_phone": bill.patient.mobile_number if bill.patient else None,
        "notification_consent": bill.patient.notification_consent if bill.patient else True,
        "sms_notification": sms_detail,
        "notes": bill.notes,
        "created_at": bill.created_at,
        "refill_reminders_count": reminders_count,
        "items": items_data
    }

@router.post("/bills", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
def create_bill(
    req: BillCreateRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value]))
):
    """
    Create a new medicine bill and atomically reduce operational inventory using FEFO.
    Strictly accessible only to PHARMACIST and ADMIN roles.
    Rejects insufficient stock, invalid quantities, or duplicate medicines.
    Ensures rollback on failure and records audit log entries.
    """
    if not req.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one medicine item is required for billing."
        )

    # Validate items and check for duplicate medicine items
    seen_medicines = set()
    seen_inventories = set()
    for item in req.items:
        if item.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantity for medicine must be a positive integer greater than 0."
            )
        if item.medicine_id is not None:
            if item.medicine_id in seen_medicines:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate medicine item (ID: {item.medicine_id}) found in bill. Combine quantities into a single item."
                )
            seen_medicines.add(item.medicine_id)
        if item.inventory_id is not None:
            if item.inventory_id in seen_inventories:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate medicine item (Inventory ID: {item.inventory_id}) found in bill. Combine quantities into a single item."
                )
            seen_inventories.add(item.inventory_id)

    # Determine default target ward
    target_ward_id = req.ward_id
    if not target_ward_id:
        default_ward = db.query(Ward).filter(Ward.active == True).order_by(Ward.id.asc()).first()
        target_ward_id = default_ward.id if default_ward else 1

    ward = db.query(Ward).filter(Ward.id == target_ward_id).first()
    ward_display_name = ward.name if ward else f"Ward {target_ward_id}"

    # Generate unique bill number
    timestamp_part = int(time.time())
    total_existing = db.query(Bill).count() + 1
    bill_number = f"BILL-{timestamp_part}-{total_existing:04d}"

    actor_name = current_user.get("display_name", current_user.get("username", "Chief Pharmacist"))
    actor_role = current_user.get("role", "PHARMACIST")
    company_id = current_user.get("company_id", 1)
    branch_id = current_user.get("branch_id", 1)

    # Resolve patient and phone number
    resolved_patient_name = req.patient_name
    resolved_patient_id = req.patient_id
    patient_phone = req.patient_phone.strip() if req.patient_phone else None

    if resolved_patient_id:
        pt = db.query(Patient).filter(Patient.id == resolved_patient_id).first()
        if pt:
            if not resolved_patient_name:
                resolved_patient_name = pt.full_name
            if patient_phone:
                pt.mobile_number = patient_phone
    elif patient_phone or resolved_patient_name:
        pt = None
        if patient_phone:
            pt = db.query(Patient).filter(Patient.mobile_number == patient_phone).first()
        if not pt and resolved_patient_name:
            pt = db.query(Patient).filter(Patient.full_name == resolved_patient_name).first()

        if pt:
            resolved_patient_id = pt.id
            if resolved_patient_name:
                pt.full_name = resolved_patient_name
            else:
                resolved_patient_name = pt.full_name
            if patient_phone:
                pt.mobile_number = patient_phone
        elif patient_phone:
            # Auto-register patient so refill reminders are scheduled for their phone
            new_pid = f"PID-{4000 + db.query(Patient).count() + 1}"
            new_pt = Patient(
                patient_id=new_pid,
                full_name=resolved_patient_name or "Walk-in Patient",
                mobile_number=patient_phone,
                notification_consent=True,
                company_id=company_id,
                branch_id=branch_id,
                created_at=datetime.utcnow()
            )
            db.add(new_pt)
            db.flush()
            resolved_patient_id = new_pt.id
            resolved_patient_name = new_pt.full_name

    # Create the Bill record (will be committed atomically with items and inventory updates)
    bill = Bill(
        bill_number=bill_number,
        company_id=company_id,
        branch_id=branch_id,
        ward_id=target_ward_id,
        created_by=actor_name,
        role=actor_role,
        status=BillStatus.SUCCESS,
        subtotal=0.0,
        total_amount=0.0,
        patient_id=resolved_patient_id,
        patient_name=resolved_patient_name,
        notes=req.notes,
        created_at=datetime.utcnow()
    )
    db.add(bill)
    db.flush()  # Populates bill.id

    subtotal = 0.0

    # Process each item with row-level locks
    for item in req.items:
        inv = None
        med = None
        item_ward_id = item.ward_id or target_ward_id

        # 1. Resolve Inventory by inventory_id if specified (highest precision)
        if item.inventory_id is not None:
            inv = db.query(Inventory).filter(Inventory.id == item.inventory_id).with_for_update().first()
            if not inv:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Inventory record with ID {item.inventory_id} not found."
                )
            med = inv.medicine or db.query(Medicine).filter(Medicine.id == inv.medicine_id).first()
            item_ward_id = inv.ward_id
        # 2. Resolve by medicine_id
        elif item.medicine_id is not None:
            med = db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
            if not med:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Medicine with ID {item.medicine_id} not found."
                )
            inv = db.query(Inventory).filter(
                Inventory.medicine_id == item.medicine_id,
                Inventory.ward_id == item_ward_id
            ).with_for_update().first()

            # Fallback if ward wasn't explicitly pinned and current ward doesn't have stock
            if (not inv or inv.current_stock < item.quantity) and not item.ward_id and not req.ward_id:
                fallback_inv = db.query(Inventory).filter(
                    Inventory.medicine_id == item.medicine_id,
                    Inventory.current_stock >= item.quantity
                ).order_by(Inventory.current_stock.desc()).with_for_update().first()
                if fallback_inv:
                    inv = fallback_inv
                    item_ward_id = inv.ward_id
        else:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either medicine_id or inventory_id must be provided for each item."
            )

        if not inv:
            db.rollback()
            med_label = med.name if med else f"Medicine #{item.medicine_id}"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Operational inventory not found for {med_label} in Ward {item_ward_id}."
            )

        current_avail = inv.current_stock if inv else 0
        if current_avail < item.quantity:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for {med.name}. Available: {current_avail}, Requested: {item.quantity}"
            )

        # FEFO Batch Deduction: query batches sorted by earliest expiry date first
        batches = db.query(InventoryBatch).filter(
            InventoryBatch.medicine_id == med.id,
            InventoryBatch.ward_id == inv.ward_id,
            InventoryBatch.status.in_([BatchStatus.ACTIVE, BatchStatus.NEAR_EXPIRY]),
            InventoryBatch.current_quantity > 0
        ).order_by(InventoryBatch.expiry_date.asc()).with_for_update().all()

        remaining_to_deduct = item.quantity
        batch_deductions = []
        primary_batch_id = None

        for batch in batches:
            if remaining_to_deduct <= 0:
                break
            deduct_amount = min(batch.current_quantity, remaining_to_deduct)
            batch.current_quantity -= deduct_amount
            if batch.current_quantity == 0:
                batch.status = BatchStatus.DEPLETED
            if primary_batch_id is None:
                primary_batch_id = batch.id
            batch_deductions.append({
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "quantity": deduct_amount,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None
            })
            remaining_to_deduct -= deduct_amount

        # Pricing calculation
        unit_price = med.unit_cost if (med.unit_cost and med.unit_cost > 0) else 10.0
        item_total = round(unit_price * item.quantity, 2)
        subtotal += item_total

        # Inventory reduction
        previous_stock = inv.current_stock
        inv.current_stock -= item.quantity
        updated_stock = inv.current_stock
        inv.days_of_stock = round(inv.current_stock / max(inv.avg_daily_usage, 1.0), 1)
        inv.last_modified_by = actor_name
        inv.last_modified_at = datetime.utcnow()

        item_ward = inv.ward or (db.query(Ward).filter(Ward.id == inv.ward_id).first() if inv.ward_id else None)
        item_ward_name = item_ward.name if item_ward else f"Ward {inv.ward_id}"

        # Create BillItem
        bill_item = BillItem(
            bill_id=bill.id,
            medicine_id=med.id,
            inventory_id=inv.id,
            ward_id=inv.ward_id,
            batch_id=primary_batch_id,
            quantity=item.quantity,
            days_supply=item.days_supply if (item.days_supply and item.days_supply > 0) else 30,
            unit_price=unit_price,
            total_price=item_total,
            previous_stock=previous_stock,
            updated_stock=updated_stock,
            batch_deductions=batch_deductions
        )
        db.add(bill_item)

        # AuditLog entry
        audit_entry = AuditLog(
            event_type="PHARMACY_BILLING",
            actor=actor_name,
            entity_type="Inventory",
            entity_id=str(inv.id),
            action="BILL_COMPLETED",
            details={
                "bill_number": bill_number,
                "medicine_id": med.id,
                "inventory_id": inv.id,
                "medicine_name": med.name,
                "medicine_code": med.code,
                "ward_id": inv.ward_id,
                "ward_name": item_ward_name,
                "quantity": item.quantity,
                "previous_stock": previous_stock,
                "new_stock": updated_stock,
                "unit_price": unit_price,
                "total_price": item_total,
                "role": actor_role,
                "branch_id": branch_id,
                "status": "SUCCESS"
            }
        )
        db.add(audit_entry)

        # DataAuditTrail entry
        trail_entry = DataAuditTrail(
            user=actor_name,
            role=actor_role,
            action="BILL_COMPLETED",
            entity_type="Inventory",
            record_id=inv.id,
            medicine_name=med.name,
            ward_name=item_ward_name,
            old_value={"current_stock": previous_stock},
            new_value={"current_stock": updated_stock, "billed_qty": item.quantity, "bill_number": bill_number},
            reason=f"Pharmacy Billing Dispense #{bill_number}",
            validation_result="VALIDATED",
            source="BILLING"
        )
        db.add(trail_entry)

    bill.subtotal = round(subtotal, 2)
    bill.total_amount = round(subtotal, 2)

    try:
        db.flush()
        # Verify that all inventory records in this bill have been correctly reduced in the database session
        for item in bill.items:
            check_inv = db.query(Inventory).filter(Inventory.id == item.inventory_id).first()
            if not check_inv or check_inv.current_stock != item.updated_stock:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Bill could not be completed because inventory update failed."
                )
        db.commit()
        db.refresh(bill)

        # Isolated reminder scheduling: reminder failure MUST NEVER impact successful bill or inventory reduction
        try:
            from app.services.patient_reminder_service import schedule_reminders_for_bill
            schedule_reminders_for_bill(bill.id, db)
        except Exception as rem_err:
            logger.error(f"Non-fatal error scheduling refill reminders for bill {bill.id}: {rem_err}", exc_info=True)

        # Autonomous Patient SMS Notification for Bill Completion
        # Isolated: SMS dispatch failure MUST NEVER reverse successful bill or inventory deduction
        try:
            from app.services.bill_sms_service import send_bill_completion_sms
            send_bill_completion_sms(bill.id, db, notification_consent=req.notification_consent)
        except Exception as sms_err:
            logger.error(f"Non-fatal error sending bill completion SMS for bill {bill.id}: {sms_err}", exc_info=True)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Billing transaction failed: {str(e)}"
        )

    return _format_bill_response(bill, db)

@router.get("/bills", response_model=List[BillResponse])
def get_bills(
    ward_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value]))
):
    """
    Fetch recent bills with itemized dispensing records.
    Accessible to PHARMACIST and ADMIN roles.
    """
    query = db.query(Bill)
    if ward_id:
        query = query.filter(Bill.ward_id == ward_id)
    
    bills = query.order_by(Bill.created_at.desc()).limit(limit).all()
    return [_format_bill_response(b, db) for b in bills]

@router.get("/bills/{id_or_number}", response_model=BillResponse)
def get_bill_detail(
    id_or_number: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value]))
):
    """
    Get detailed breakdown of a specific bill by ID or bill_number.
    """
    if id_or_number.isdigit():
        bill = db.query(Bill).filter(Bill.id == int(id_or_number)).first()
    else:
        bill = db.query(Bill).filter(Bill.bill_number == id_or_number).first()

    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill '{id_or_number}' not found."
        )

    return _format_bill_response(bill, db)

@router.post("/bills/{id}/send-sms")
def manually_approve_and_send_bill_sms(
    id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value, UserRole.ADMIN.value]))
):
    """
    Manually approve and dispatch an SMS confirmation for a specific bill on-demand.
    Guarantees SMS is only sent when pharmacist explicitly approves.
    """
    bill = db.query(Bill).filter(Bill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found.")
    
    from app.services.bill_sms_service import send_bill_completion_sms
    res = send_bill_completion_sms(bill.id, db, notification_consent=True, force=True)
    if not res:
        raise HTTPException(status_code=400, detail="Failed to dispatch SMS for this bill. Check patient mobile number.")
    return res

@router.post("/bills/{id}/cancel", response_model=BillCancelResponse)
def cancel_bill(
    id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role([UserRole.PHARMACIST.value]))
):
    """
    Cancel an existing SUCCESS bill and safely reverse the inventory deduction exactly once.
    """
    bill = db.query(Bill).filter(Bill.id == id).with_for_update().first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill with ID {id} not found."
        )

    if bill.status == BillStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill is already cancelled. Repeated reversal is prevented."
        )

    if bill.status != BillStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel bill with status '{bill.status.value}'."
        )

    actor_name = current_user.get("display_name", current_user.get("username", "Chief Pharmacist"))
    actor_role = current_user.get("role", "PHARMACIST")

    reversed_items = []

    # Reverse inventory for each item
    for item in bill.items:
        if item.inventory_id:
            inv = db.query(Inventory).filter(Inventory.id == item.inventory_id).with_for_update().first()
        else:
            inv = db.query(Inventory).filter(
                Inventory.medicine_id == item.medicine_id,
                Inventory.ward_id == (item.ward_id or bill.ward_id)
            ).with_for_update().first()

        med = item.medicine or db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
        med_name = med.name if med else f"Medicine #{item.medicine_id}"

        prev_stock = inv.current_stock if inv else 0
        if inv:
            inv.current_stock += item.quantity
            inv.days_of_stock = round(inv.current_stock / max(inv.avg_daily_usage, 1.0), 1)
            inv.last_modified_by = actor_name
            inv.last_modified_at = datetime.utcnow()
            new_stock = inv.current_stock
        else:
            new_stock = item.quantity

        # Restore batches if recorded
        if item.batch_deductions:
            for bd in item.batch_deductions:
                b_id = bd.get("batch_id")
                qty = bd.get("quantity", 0)
                if b_id and qty > 0:
                    batch = db.query(InventoryBatch).filter(InventoryBatch.id == b_id).with_for_update().first()
                    if batch:
                        batch.current_quantity += qty
                        if batch.status == BatchStatus.DEPLETED and batch.current_quantity > 0:
                            batch.status = BatchStatus.ACTIVE

        reversed_items.append({
            "medicine_id": item.medicine_id,
            "inventory_id": item.inventory_id,
            "medicine_name": med_name,
            "reversed_quantity": item.quantity,
            "previous_stock": prev_stock,
            "restored_stock": new_stock
        })

        # AuditLog cancellation record
        audit_entry = AuditLog(
            event_type="PHARMACY_BILLING",
            actor=actor_name,
            entity_type="Inventory",
            entity_id=str(inv.id) if inv else None,
            action="BILL_CANCELLED",
            details={
                "bill_number": bill.bill_number,
                "medicine_id": item.medicine_id,
                "inventory_id": inv.id if inv else None,
                "medicine_name": med_name,
                "reversed_quantity": item.quantity,
                "previous_stock": prev_stock,
                "restored_stock": new_stock,
                "role": actor_role,
                "status": "CANCELLED"
            }
        )
        db.add(audit_entry)

        # DataAuditTrail entry
        trail_ward_name = inv.ward.name if (inv and inv.ward) else (bill.ward.name if bill.ward else f"Ward {bill.ward_id}")
        trail_entry = DataAuditTrail(
            user=actor_name,
            role=actor_role,
            action="BILL_CANCELLED",
            entity_type="Inventory",
            record_id=inv.id if inv else None,
            medicine_name=med_name,
            ward_name=trail_ward_name,
            old_value={"current_stock": prev_stock},
            new_value={"current_stock": new_stock, "reversal_qty": item.quantity, "bill_number": bill.bill_number},
            reason=f"Cancellation of Bill #{bill.bill_number}",
            validation_result="VALIDATED",
            source="BILLING"
        )
        db.add(trail_entry)

    bill.status = BillStatus.CANCELLED

    # Cancel any active pending reminders associated with this bill
    try:
        pending_rems = db.query(MedicationReminder).filter(
            MedicationReminder.bill_id == bill.id,
            MedicationReminder.status == ReminderStatus.PENDING
        ).all()
        for pr in pending_rems:
            pr.status = ReminderStatus.CANCELLED
    except Exception as rem_cancel_err:
        logger.warning(f"Error updating reminders for cancelled bill {bill.id}: {rem_cancel_err}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bill cancellation failed: {str(e)}"
        )

    return {
        "message": f"Bill {bill.bill_number} cancelled successfully and stock reversed.",
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "status": bill.status.value,
        "reversed_items": reversed_items
    }
