export type CriticalityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type AlertSeverity = 'INFO' | 'WARNING' | 'CRITICAL' | 'EMERGENCY';
export type AlertType = 'SHORTAGE_PREDICTED' | 'CRITICAL_LOW' | 'EXPIRY_RISK' | 'SURPLUS_DETECTED' | 'ABNORMAL_CONSUMPTION';
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
export type ActionType = 'PURCHASE_ORDER' | 'STOCK_TRANSFER' | 'DISPOSAL' | 'SAFETY_STOCK_OVERRIDE';
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';
export type OrderStatus = 'DRAFT' | 'PROPOSED' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'ORDERED' | 'DELIVERED';
export type TransferStatus = 'PROPOSED' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'IN_TRANSIT' | 'COMPLETED';

export type TrustStatus = 'VALIDATED' | 'PENDING_REVIEW' | 'WARNING' | 'REJECTED';
export type UserRole = 'DATA_MANAGER' | 'PHARMACIST' | 'ADMIN';

export interface InventoryItem {
  id: number;
  medicine_id: number;
  medicine_code: str;
  medicine_name: string;
  generic_name: string;
  category: string;
  criticality: CriticalityLevel;
  unit: string;
  unit_cost: number;
  ward_id: number;
  ward_name: string;
  department_name: string;
  current_stock: number;
  reserved_stock: number;
  available_stock: number;
  min_level: number;
  max_level: number;
  safety_stock: number;
  reorder_point?: number;
  daily_consumption_avg: number;
  days_remaining: number;
  risk_level: RiskLevel;
  stock_status: 'NORMAL' | 'LOW_STOCK' | 'CRITICAL_LOW' | 'SURPLUS';
  nearest_expiry_date?: string;
  days_to_nearest_expiry?: number;
  last_restocked_at?: string;
  data_source?: string;
  risk_scenario?: string;
  trust_status?: TrustStatus;
  validated_by?: string;
  validated_at?: string;
  validation_notes?: string;
  last_modified_by?: string;
  last_modified_at?: string;
  supplier_name?: string;
  lead_time_days?: number;
  unit_price_inr?: number;
}

type str = string;

export interface ForecastPoint {
  date: string;
  historical?: number;
  predicted: number;
  lower_bound: number;
  upper_bound: number;
  projected_stock?: number;
}

export interface ForecastData {
  medicine_id: number;
  medicine_name: string;
  ward_id: number;
  ward_name: string;
  horizon_days: number;
  current_stock: number;
  total_predicted_demand: number;
  expected_daily_demand: number;
  estimated_stockout_days?: number;
  estimated_stockout_date?: string;
  confidence_score: number;
  mape_score?: number | null;
  mae_score?: number | null;
  rmse_score?: number | null;
  risk_level: RiskLevel;
  forecast_points: ForecastPoint[];
  model_used: string;
  reasoning: string;
  usage_source?: string;
  data_status?: string;
}

export interface AlertItem {
  id: number;
  alert_type: AlertType;
  severity: AlertSeverity;
  medicine_id?: number;
  medicine_name?: string;
  ward_id?: number;
  ward_name?: string;
  title: string;
  message: string;
  status: AlertStatus;
  recommended_action?: string;
  triggered_by_agent: string;
  created_at: string;
}

export interface ApprovalItem {
  id: number;
  action_type: ActionType;
  reference_id: number;
  medicine_id?: number;
  medicine_name?: string;
  requested_by_agent: string;
  risk_level: RiskLevel;
  justification: string;
  estimated_cost: number;
  requested_quantity: number;
  status: ApprovalStatus;
  decision_by?: string;
  decision_reason?: string;
  decided_at?: string;
  created_at: string;
  details?: Record<string, any>;
}

export interface StockTransferItem {
  id: number;
  transfer_number: string;
  medicine_id: number;
  medicine_name: string;
  from_ward_id: number;
  from_ward_name: string;
  to_ward_id: number;
  to_ward_name: string;
  quantity: number;
  reason: string;
  status: TransferStatus;
  risk_level: RiskLevel;
  approved_by?: string;
  initiated_by_agent: string;
  created_at: string;
  completed_at?: string;
}

export interface PurchaseOrderItem {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string;
  supplier_lead_time_days: number;
  supplier_reliability: number;
  total_amount: number;
  status: OrderStatus;
  priority: string;
  created_by_agent: string;
  approved_by?: string;
  order_date: string;
  expected_delivery_date?: string;
  items: Array<{
    id: number;
    medicine_id: number;
    medicine_name: string;
    quantity: number;
    unit_price: number;
    total_price: number;
  }>;
  notes?: string;
}

export interface DashboardSummary {
  total_medicines: number;
  total_stock_units: number;
  critical_stockout_alerts: number;
  expiring_batches_90d: number;
  pending_approvals: number;
  active_agent_runs: number;
  overall_health_score: number;
  autonomous_actions_24h: number;
  risk_radar: Array<{
    category: string;
    risk_score: number;
    stock_volume: number;
    status: string;
  }>;
  health_map: Array<{
    department: string;
    health_percent: number;
    critical_count: number;
    low_count: number;
    status: string;
  }>;
  recent_alerts: AlertItem[];
  pending_approvals_list: ApprovalItem[];
  agent_activity_summary: Array<{
    name: string;
    role: string;
    status: string;
    tasks_completed: number;
    current_task: string;
    color: string;
  }>;
  data_sources?: Array<{
    name: string;
    source_type: string;
    description?: string;
    record_count: number;
    last_imported?: string;
    status: string;
  }>;
}

export interface SimulationStep {
  timestamp: string;
  agent: string;
  action: string;
  detail: string;
  severity: string;
}

export interface SimulationResponse {
  scenario: string;
  status: string;
  message: string;
  medicine_name: string;
  affected_ward: string;
  initial_stock: number;
  spiked_daily_demand: number;
  days_to_stockout: number;
  steps: SimulationStep[];
}

export interface DataSourceItem {
  id: number;
  name: string;
  source_type: string;
  description?: string;
  record_count: number;
  last_imported?: string;
  status: string;
}

export interface DataQualityReport {
  records_inspected: number;
  records_used: number;
  mapped_medicines_count: number;
  total_medicines_count: number;
  unmapped_medicines_count: number;
  low_confidence_count: number;
  imported_daily_records: number;
  last_import_time?: string;
  import_status: string;
  latest_import_id?: string;
  mapped_medicines: Array<{
    medicine_id: number;
    medicine_code: string;
    medicine_name: string;
    aliases_count: number;
    sample_aliases: string[];
    historical_records_count: number;
  }>;
  unmapped_samples: string[];
}

export interface UsageHistoryItem {
  date: string;
  quantity_used: number;
  source: string;
  record_count: number;
}

export interface Branch {
  id: number;
  company_id: number;
  name: string;
  code: string;
  location?: string;
  status: string;
}

export interface Company {
  id: number;
  name: string;
  code: string;
  status: string;
  branches?: Branch[];
}

export interface User {
  id: number;
  username: string;
  role: UserRole;
  display_name: string;
  title?: string;
  company_id?: number;
  company_name?: string;
  branch_id?: number;
  branch_name?: string;
}

export interface DataAuditRecord {
  id: number;
  user: string;
  role: string;
  action: string;
  entity_type: string;
  record_id?: number;
  medicine_name?: string;
  ward_name?: string;
  old_value?: any;
  new_value?: any;
  reason: string;
  validation_result: string;
  source: string;
  timestamp: string;
}

export interface BatchValidationResult {
  total_records: number;
  valid_count: number;
  warning_count: number;
  rejected_count: number;
  valid_rows: any[];
  warnings: any[];
  errors: any[];
}

export interface BatchImportResponse {
  status: string;
  database: string;
  primary_table: string;
  message: string;
  total_submitted: number;
  imported_count: number;
  inserted_count: number;
  updated_count: number;
  rejected_count: number;
  warning_count: number;
  source: string;
  trust_status: string;
  timestamp: string;
  rejected_errors?: any[];
}

export interface BillItemDeduction {
  batch_id: number;
  batch_number: string;
  quantity: number;
  expiry_date?: string;
}

export interface BillItemDetail {
  id: number;
  medicine_id: number;
  inventory_id?: number;
  ward_id?: number;
  ward_name?: string;
  medicine_name: string;
  medicine_code: string;
  quantity: number;
  days_supply?: number;
  unit_price: number;
  total_price: number;
  previous_stock?: number;
  updated_stock?: number;
  batch_deductions?: BillItemDeduction[];
}

export interface SMSNotificationDetail {
  id?: number;
  status: 'QUEUED' | 'SENT' | 'DELIVERED' | 'FAILED' | 'NOT_CONFIGURED' | 'OPTED_OUT' | string;
  masked_phone?: string;
  provider?: string;
  provider_message_id?: string;
  message?: string;
  status_message?: string;
  failure_reason?: string;
  created_at?: string;
  sent_at?: string;
  delivered_at?: string;
}

export interface Bill {
  id: number;
  bill_number: string;
  company_id?: number;
  branch_id?: number;
  ward_id?: number;
  ward_name?: string;
  created_by: string;
  role: string;
  status: 'DRAFT' | 'SUCCESS' | 'FAILED' | 'CANCELLED';
  subtotal: number;
  total_amount: number;
  patient_id?: number;
  patient_name?: string;
  notes?: string;
  created_at: string;
  patient_phone?: string;
  notification_consent?: boolean;
  sms_notification?: SMSNotificationDetail;
  refill_reminders_count?: number;
  items: BillItemDetail[];
}

export interface BillCreatePayload {
  ward_id?: number;
  patient_id?: number;
  patient_name?: string;
  patient_phone?: string;
  notification_consent?: boolean;
  notes?: string;
  items: {
    medicine_id?: number;
    inventory_id?: number;
    ward_id?: number;
    quantity: number;
    days_supply?: number;
  }[];
}

export interface BillCancelResponse {
  message: string;
  bill_id: number;
  bill_number: string;
  status: string;
  reversed_items: {
    medicine_id: number;
    medicine_name: string;
    reversed_quantity: number;
    previous_stock: number;
    restored_stock: number;
  }[];
}

// Patient Refill Reminder Types
export interface Patient {
  id: number;
  patient_id: string;
  full_name: string;
  mobile_number: string;
  email?: string;
  notification_consent: boolean;
  company_id?: number;
  branch_id?: number;
  created_at: string;
}

export interface PatientCreatePayload {
  patient_id?: string;
  full_name: string;
  mobile_number: string;
  email?: string;
  notification_consent: boolean;
}

export interface NotificationLog {
  id: number;
  reminder_id?: number;
  bill_id?: number;
  patient_id?: number;
  channel: string;
  recipient: string;
  masked_phone_number?: string;
  message: string;
  provider?: string;
  provider_message_id?: string;
  status: string;
  created_at?: string;
  sent_at: string;
  delivered_at?: string;
  failure_reason?: string;
}

export interface MedicationReminder {
  id: number;
  patient_id: number;
  patient_name: string;
  patient_code: string;
  mobile_number: string;
  notification_consent: boolean;
  bill_id: number;
  bill_number: string;
  bill_item_id?: number;
  medicine_id: number;
  medicine_name: string;
  quantity: number;
  days_supply: number;
  bill_date: string;
  estimated_finish_date: string;
  reminder_date: string;
  status: 'PENDING' | 'SENT' | 'DELIVERED' | 'OPTED_OUT' | 'CANCELLED';
  notification_message?: string;
  channel: string;
  created_at: string;
  notification_logs?: NotificationLog[];
}

export interface ReminderProcessResult {
  target_date: string;
  total_checked: number;
  sent_count: number;
  opted_out_count: number;
  failed_count: number;
  already_processed_count: number;
  details: Array<{
    reminder_id: number;
    patient_name: string;
    medicine_name: string;
    status: string;
    reason?: string;
  }>;
}

export interface SMSGatewayConfig {
  active_provider: string;
  active_provider_id?: string;
  has_twilio: boolean;
  has_fast2sms: boolean;
  has_custom_gateway: boolean;
  twilio_phone?: string;
  twilio_from?: string;
  gateway_url?: string;
  default_sender?: string;
  supported_providers: string[];
}

export interface SMSGatewayUpdate {
  provider?: string;
  twilio_sid?: string;
  twilio_auth?: string;
  twilio_token?: string;
  twilio_from?: string;
  twilio_phone?: string;
  fast2sms_key?: string;
  gateway_url?: string;
  sender_id?: string;
}

export interface SMSConnectionTestResponse {
  success: boolean;
  message: string;
  provider: string;
}


