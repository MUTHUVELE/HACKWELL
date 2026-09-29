from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import (
    CriticalityLevel, DepartmentType, BatchStatus, OrderStatus,
    PriorityLevel, TransferStatus, RiskLevel, AlertSeverity,
    AlertType, AlertStatus, ActionType, ApprovalStatus, BillStatus
)


# Base Models
class MedicineBase(BaseModel):
    code: str
    name: str
    generic_name: str
    category: str
    unit: str = "units"
    criticality: CriticalityLevel = CriticalityLevel.MEDIUM
    shelf_life_days: int = 365
    reorder_threshold: int = 50
    safety_stock: int = 30
    unit_cost: float = 10.0
    active: bool = True

class MedicineResponse(MedicineBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class WardResponse(BaseModel):
    id: int
    code: str
    name: str
    department_id: int
    bed_count: int
    active: bool
    model_config = ConfigDict(from_attributes=True)

class DepartmentResponse(BaseModel):
    id: int
    code: str
    name: str
    type: str
    floor: str
    active: bool
    wards: List[WardResponse] = []
    model_config = ConfigDict(from_attributes=True)

class BatchResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: Optional[str] = None
    ward_id: int
    ward_name: Optional[str] = None
    batch_number: str
    initial_quantity: int
    current_quantity: int
    unit_cost: float
    manufacturing_date: date
    expiry_date: date
    days_to_expiry: int
    status: BatchStatus
    model_config = ConfigDict(from_attributes=True)

class InventoryItemResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_code: str
    medicine_name: str
    generic_name: str
    category: str
    criticality: CriticalityLevel
    unit: str
    unit_cost: float
    ward_id: int
    ward_name: str
    department_name: str
    current_stock: int
    reserved_stock: int
    available_stock: int
    min_level: int
    max_level: int
    safety_stock: int
    reorder_point: Optional[int] = 50
    daily_consumption_avg: float
    days_remaining: float
    risk_level: RiskLevel
    stock_status: str  # NORMAL, LOW, CRITICAL_LOW, SURPLUS
    nearest_expiry_date: Optional[date] = None
    days_to_nearest_expiry: Optional[int] = None
    last_restocked_at: Optional[datetime] = None
    data_source: str = "SYNTHETIC"
    risk_scenario: Optional[str] = "NORMAL"
    trust_status: str = "VALIDATED"
    validated_by: Optional[str] = "SYSTEM_SEED"
    validated_at: Optional[datetime] = None
    validation_notes: Optional[str] = None
    last_modified_by: Optional[str] = None
    last_modified_at: Optional[datetime] = None
    supplier_name: Optional[str] = None
    lead_time_days: Optional[int] = None
    unit_price_inr: Optional[float] = None

class ForecastPoint(BaseModel):
    date: str
    historical: Optional[float] = None
    predicted: float
    lower_bound: float
    upper_bound: float
    projected_stock: Optional[float] = None

class ForecastResponse(BaseModel):
    medicine_id: int
    medicine_name: str
    ward_id: int
    ward_name: str
    horizon_days: int
    current_stock: int
    total_predicted_demand: float
    expected_daily_demand: float
    estimated_stockout_days: Optional[float]
    estimated_stockout_date: Optional[str]
    confidence_score: float
    mape_score: Optional[float] = None
    mae_score: Optional[float] = None
    rmse_score: Optional[float] = None
    risk_level: RiskLevel
    forecast_points: List[ForecastPoint]
    model_used: str
    reasoning: str
    usage_source: str = "MIMIC-Derived"
    data_status: str = "sufficient"

class AlertResponse(BaseModel):
    id: int
    alert_type: AlertType
    severity: AlertSeverity
    medicine_id: Optional[int] = None
    medicine_name: Optional[str] = None
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None
    title: str
    message: str
    status: AlertStatus
    recommended_action: Optional[str] = None
    triggered_by_agent: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class StockTransferResponse(BaseModel):
    id: int
    transfer_number: str
    medicine_id: int
    medicine_name: str
    from_ward_id: int
    from_ward_name: str
    to_ward_id: int
    to_ward_name: str
    quantity: int
    reason: str
    status: TransferStatus
    risk_level: RiskLevel
    approved_by: Optional[str]
    initiated_by_agent: str
    created_at: datetime
    completed_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

class POItemResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str
    quantity: int
    unit_price: float
    total_price: float
    model_config = ConfigDict(from_attributes=True)

class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: str
    supplier_lead_time_days: int
    supplier_reliability: float
    total_amount: float
    status: OrderStatus
    priority: PriorityLevel
    created_by_agent: str
    approved_by: Optional[str]
    order_date: datetime
    expected_delivery_date: Optional[date]
    items: List[POItemResponse]
    notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)

class ApprovalResponse(BaseModel):
    id: int
    action_type: ActionType
    reference_id: int
    medicine_id: Optional[int]
    medicine_name: Optional[str]
    requested_by_agent: str
    risk_level: RiskLevel
    justification: str
    estimated_cost: float
    requested_quantity: int
    status: ApprovalStatus
    decision_by: Optional[str]
    decision_reason: Optional[str]
    decided_at: Optional[datetime]
    created_at: datetime
    details: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)

class ApprovalActionRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    decision_by: str = "Chief Pharmacist"
    reason: Optional[str] = "Approved via clinical inventory protocol"

class DashboardSummaryResponse(BaseModel):
    total_medicines: int
    total_stock_units: int
    critical_stockout_alerts: int
    expiring_batches_90d: int
    pending_approvals: int
    active_agent_runs: int
    overall_health_score: float
    autonomous_actions_24h: int
    risk_radar: List[Dict[str, Any]]
    health_map: List[Dict[str, Any]]
    recent_alerts: List[AlertResponse]
    pending_approvals_list: List[ApprovalResponse]
    agent_activity_summary: List[Dict[str, Any]]
    data_sources: Optional[List[Dict[str, Any]]] = None

class SimulationStep(BaseModel):
    timestamp: str
    agent: str
    action: str
    detail: str
    severity: str = "INFO"

class SimulationResponse(BaseModel):
    scenario: str
    status: str
    message: str
    medicine_name: str
    affected_ward: str
    initial_stock: int
    spiked_daily_demand: float
    days_to_stockout: float
    steps: List[SimulationStep]
    transfer_created: Optional[StockTransferResponse] = None
    po_created: Optional[PurchaseOrderResponse] = None
    approval_created: Optional[ApprovalResponse] = None

class ChatMessageRequest(BaseModel):
    message: str
    context_medicine_id: Optional[int] = None

class ChatMessageResponse(BaseModel):
    reply: str
    intent: str
    tools_called: List[str]
    data: Optional[Dict[str, Any]] = None
    agent_reasoning: str

class DataSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    description: Optional[str] = None
    record_count: int
    last_imported: Optional[datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)

class DataQualitySummaryResponse(BaseModel):
    records_inspected: int
    records_used: int
    mapped_medicines_count: int
    total_medicines_count: int
    unmapped_medicines_count: int
    low_confidence_count: int
    imported_daily_records: int
    last_import_time: Optional[datetime] = None
    import_status: str
    latest_import_id: Optional[str] = None
    mapped_medicines: List[Dict[str, Any]] = []
    unmapped_samples: List[str] = []

class MedicationUsageHistoryItem(BaseModel):
    date: str
    quantity_used: float
    source: str
    record_count: int

class MedicationUsageHistoryResponse(BaseModel):
    medicine_id: int
    medicine_name: str
    medicine_code: str
    total_records: int
    usage_source: str
    history: List[MedicationUsageHistoryItem]

# Organization & Hierarchy Schemas
class BranchResponse(BaseModel):
    id: int
    company_id: int
    name: str
    code: str
    location: Optional[str] = None
    status: str = "ACTIVE"
    model_config = ConfigDict(from_attributes=True)

class CompanyResponse(BaseModel):
    id: int
    name: str
    code: str
    status: str = "ACTIVE"
    branches: Optional[List[BranchResponse]] = None
    model_config = ConfigDict(from_attributes=True)

# Data Governance, Validation & Auth Schemas
class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    title: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    demo_role: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[int] = None
    branch_id: Optional[int] = None

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class RegisterRequest(BaseModel):
    full_name: str
    username: str
    email: str
    password: str
    confirm_password: str
    role: str
    company_id: Optional[int] = None
    branch_id: Optional[int] = None

class RegisterResponse(BaseModel):
    message: str = "Registration successful. You can now sign in."
    username: str
    role: str
    company_id: Optional[int] = None
    branch_id: Optional[int] = None


class StockUpdateRequest(BaseModel):
    new_stock: int
    reason: str
    override_warning: bool = False

class BatchValidationRow(BaseModel):
    medicine_code: str
    medicine_name: Optional[str] = None
    ward_code: str
    ward_name: Optional[str] = None
    current_stock: int
    min_level: Optional[int] = 20
    max_level: Optional[int] = 200
    safety_stock: Optional[int] = 30
    reorder_point: Optional[int] = 50
    avg_daily_usage: Optional[float] = 10.0
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    received_date: Optional[str] = None

class BatchValidationResponse(BaseModel):
    total_records: int
    valid_count: int
    warning_count: int
    rejected_count: int
    valid_rows: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

class DataAuditTrailResponse(BaseModel):
    id: int
    user: str
    role: str
    action: str
    entity_type: str
    record_id: Optional[int] = None
    medicine_name: Optional[str] = None
    ward_name: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    reason: str
    validation_result: str
    source: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class BillItemInput(BaseModel):
    medicine_id: Optional[int] = None
    inventory_id: Optional[int] = None
    ward_id: Optional[int] = None
    quantity: int
    days_supply: Optional[int] = None

class BillCreateRequest(BaseModel):
    ward_id: Optional[int] = None
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    notes: Optional[str] = None
    notification_consent: bool = False
    items: List[BillItemInput]

class BillItemDetailResponse(BaseModel):
    id: int
    medicine_id: int
    inventory_id: Optional[int] = None
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None
    medicine_name: str
    medicine_code: str
    quantity: int
    days_supply: Optional[int] = None
    unit_price: float
    total_price: float
    previous_stock: Optional[int] = None
    updated_stock: Optional[int] = None
    batch_deductions: Optional[List[Dict[str, Any]]] = None
    model_config = ConfigDict(from_attributes=True)

class SMSNotificationDetail(BaseModel):
    id: Optional[int] = None
    status: str
    masked_phone: Optional[str] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    message: Optional[str] = None
    status_message: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class BillResponse(BaseModel):
    id: int
    bill_number: str
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None
    created_by: str
    role: str
    status: str
    subtotal: float
    total_amount: float
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    notification_consent: Optional[bool] = True
    sms_notification: Optional[SMSNotificationDetail] = None
    notes: Optional[str] = None
    created_at: datetime
    refill_reminders_count: Optional[int] = 0
    items: List[BillItemDetailResponse] = []
    model_config = ConfigDict(from_attributes=True)

class BillCancelResponse(BaseModel):
    message: str
    bill_id: int
    bill_number: str
    status: str
    reversed_items: List[Dict[str, Any]] = []

# Patient Refill Reminder Schemas
class PatientCreate(BaseModel):
    patient_id: Optional[str] = None
    full_name: str
    mobile_number: str
    email: Optional[str] = None
    notification_consent: bool = True

class PatientResponse(BaseModel):
    id: int
    patient_id: str
    full_name: str
    mobile_number: str
    email: Optional[str] = None
    notification_consent: bool
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class NotificationLogResponse(BaseModel):
    id: int
    reminder_id: Optional[int] = None
    bill_id: Optional[int] = None
    patient_id: Optional[int] = None
    channel: str
    recipient: str
    masked_phone_number: Optional[str] = None
    message: str
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class MedicationReminderResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    mobile_number: str
    notification_consent: bool
    bill_id: int
    bill_number: str
    bill_item_id: Optional[int] = None
    medicine_id: int
    medicine_name: str
    quantity: int
    days_supply: int
    bill_date: datetime
    estimated_finish_date: date
    reminder_date: date
    status: str
    notification_message: Optional[str] = None
    channel: str = "SMS"
    created_at: datetime
    notification_logs: List[NotificationLogResponse] = []
    model_config = ConfigDict(from_attributes=True)

class ReminderProcessRequest(BaseModel):
    simulate_date: Optional[str] = None
    target_date: Optional[str] = None
    date: Optional[str] = None
    force_all: Optional[bool] = False
    force: Optional[bool] = False

class ReminderSendRequest(BaseModel):
    channel: Optional[str] = "SMS"
    force: Optional[bool] = False

class ReminderProcessResult(BaseModel):
    target_date: str
    total_checked: int
    sent_count: int
    opted_out_count: int
    failed_count: int
    already_processed_count: int
    details: List[Dict[str, Any]] = []

class SMSGatewayConfig(BaseModel):
    active_provider: str
    active_provider_id: Optional[str] = None
    has_twilio: bool
    twilio_from: Optional[str] = None
    has_fast2sms: bool
    has_custom_gateway: bool
    gateway_url: Optional[str] = None
    default_channel: str = "SMS"
    supported_providers: List[str] = []

class SMSGatewayUpdate(BaseModel):
    twilio_sid: Optional[str] = None
    twilio_auth: Optional[str] = None
    twilio_token: Optional[str] = None
    twilio_from: Optional[str] = None
    twilio_phone: Optional[str] = None
    fast2sms_key: Optional[str] = None
    gateway_url: Optional[str] = None
    provider: Optional[str] = None

class SMSConnectionTestResponse(BaseModel):
    success: bool
    message: str
    provider: str

class SMSDeliveryWebhookPayload(BaseModel):
    provider_message_id: Optional[str] = None
    message_sid: Optional[str] = None
    MessageSid: Optional[str] = None
    status: Optional[str] = None
    MessageStatus: Optional[str] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None

class SMSDeliveryWebhookResponse(BaseModel):
    status: str
    message: str
    updated_records: int = 0




