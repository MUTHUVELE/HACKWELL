import axios from 'axios';
import {
  DashboardSummary,
  InventoryItem,
  ForecastData,
  AlertItem,
  ApprovalItem,
  StockTransferItem,
  PurchaseOrderItem,
  SimulationResponse,
  DataSourceItem,
  DataQualityReport,
  Company,
  Branch,
  Bill,
  BillCreatePayload,
  BillCancelResponse,
  Patient,
  PatientCreatePayload,
  MedicationReminder,
  NotificationLog,
  ReminderProcessResult,
  SMSGatewayConfig,
  SMSGatewayUpdate,
  SMSConnectionTestResponse
} from '../types';


const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Attach JWT token and demo role headers to every outgoing request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('medisentinel_token');
  const role = localStorage.getItem('medisentinel_role');
  const user = localStorage.getItem('medisentinel_user');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (role) {
    config.headers['X-User-Role'] = role;
  }
  if (user) {
    config.headers['X-User-Name'] = user;
  }
  return config;
});

export const api = {
  // Dashboard & System
  getHealth: async () => {
    const res = await client.get('/api/health');
    return res.data;
  },
  getDashboardSummary: async (): Promise<DashboardSummary> => {
    const res = await client.get<DashboardSummary>('/api/dashboard/summary');
    return res.data;
  },
  getAnalytics: async () => {
    const res = await client.get('/api/analytics');
    return res.data;
  },

  // Inventory
  getInventory: async (params?: { ward_id?: number; category?: string; criticality?: string; search?: string; risk_level?: string }): Promise<InventoryItem[]> => {
    const res = await client.get<InventoryItem[]>('/api/inventory', { params });
    return res.data;
  },
  getInventoryDetail: async (id: number) => {
    const res = await client.get(`/api/inventory/${id}`);
    return res.data;
  },

  // Forecasts
  getForecast: async (medicineId?: number, wardId?: number, horizonDays: number = 14): Promise<ForecastData> => {
    const res = await client.get<ForecastData>('/api/forecasts', {
      params: { medicine_id: medicineId, ward_id: wardId, horizon_days: horizonDays }
    });
    return res.data;
  },

  // Alerts
  getAlerts: async (severity?: string): Promise<AlertItem[]> => {
    const res = await client.get<AlertItem[]>('/api/alerts', { params: { severity } });
    return res.data;
  },
  resolveAlert: async (id: number) => {
    const res = await client.post(`/api/alerts/${id}/resolve`);
    return res.data;
  },

  // Transfers
  getTransfers: async (): Promise<StockTransferItem[]> => {
    const res = await client.get<StockTransferItem[]>('/api/transfers');
    return res.data;
  },
  executeTransfer: async (id: number, executedBy: string = 'Chief Pharmacist') => {
    const res = await client.post(`/api/transfers/${id}/execute`, null, { params: { executed_by: executedBy } });
    return res.data;
  },

  // Procurement
  getPurchaseOrders: async (): Promise<PurchaseOrderItem[]> => {
    const res = await client.get<PurchaseOrderItem[]>('/api/procurement/orders');
    return res.data;
  },
  executePurchaseOrder: async (id: number, executedBy: string = 'Chief Pharmacist') => {
    const res = await client.post(`/api/procurement/${id}/execute`, null, { params: { executed_by: executedBy } });
    return res.data;
  },

  // Human-in-the-Loop Approvals
  getApprovals: async (status?: string): Promise<ApprovalItem[]> => {
    const res = await client.get<ApprovalItem[]>('/api/approvals', { params: { status } });
    return res.data;
  },
  decideApproval: async (id: number, decision: 'APPROVE' | 'REJECT', reason: string, decisionBy: string = 'Chief Pharmacist') => {
    const res = await client.post(`/api/approvals/${id}/decide`, {
      decision,
      reason,
      decision_by: decisionBy
    });
    return res.data;
  },

  // Waste Guard
  getExpiringBatches: async (horizonDays: number = 90) => {
    const res = await client.get('/api/waste/expiring', { params: { horizon_days: horizonDays } });
    return res.data;
  },

  // Multi-Agent Architecture
  getAgents: async () => {
    const res = await client.get('/api/agents');
    return res.data;
  },
  getAgentRuns: async () => {
    const res = await client.get('/api/agents/runs');
    return res.data;
  },
  triggerAgentAnalyze: async (medicineId?: number, wardId?: number, triggerReason?: string) => {
    const res = await client.post('/api/agents/analyze', null, {
      params: { medicine_id: medicineId, ward_id: wardId, trigger_reason: triggerReason }
    });
    return res.data;
  },

  // Hackathon Simulation Hero Flow
  runDengueSimulation: async (): Promise<SimulationResponse> => {
    const res = await client.post<SimulationResponse>('/api/simulation/dengue');
    return res.data;
  },
  resetSimulation: async () => {
    const res = await client.post('/api/simulation/reset');
    return res.data;
  },

  // Grounded AI Assistant Chat
  sendChatMessage: async (message: string, contextMedicineId?: number) => {
    const res = await client.post('/api/agent/chat', {
      message,
      context_medicine_id: contextMedicineId
    });
    return res.data;
  },

  // Data Sources & Provenance
  getDataSources: async (): Promise<DataSourceItem[]> => {
    const res = await client.get<DataSourceItem[]>('/api/data-sources');
    return res.data;
  },
  getDataQuality: async (): Promise<DataQualityReport> => {
    const res = await client.get<DataQualityReport>('/api/data-quality');
    return res.data;
  },
  getUsageHistory: async (medicineId: number) => {
    const res = await client.get(`/api/usage-history/${medicineId}`);
    return res.data;
  },
  triggerMimicImport: async (dataDir?: string) => {
    const res = await client.post('/api/data/import/mimic', null, { params: { data_dir: dataDir } });
    return res.data;
  },

  // Authentication & RBAC
  login: async (payload: { demo_role?: string; username?: string; password?: string; role?: string; company_id?: number; branch_id?: number }) => {
    const res = await client.post('/api/auth/login', payload);
    if (res.data?.token) {
      localStorage.setItem('medisentinel_token', res.data.token);
      localStorage.setItem('medisentinel_role', res.data.user.role);
      localStorage.setItem('medisentinel_user', res.data.user.username);
      localStorage.setItem('medisentinel_display_name', res.data.user.display_name);
      if (res.data.user.company_id) localStorage.setItem('medisentinel_company_id', String(res.data.user.company_id));
      if (res.data.user.company_name) localStorage.setItem('medisentinel_company_name', res.data.user.company_name);
      if (res.data.user.branch_id) localStorage.setItem('medisentinel_branch_id', String(res.data.user.branch_id));
      if (res.data.user.branch_name) localStorage.setItem('medisentinel_branch_name', res.data.user.branch_name);
    }
    return res.data;
  },
  getCompanies: async (): Promise<Company[]> => {
    const res = await client.get<Company[]>('/api/auth/companies');
    return res.data;
  },
  getBranches: async (companyId: number): Promise<Branch[]> => {
    const res = await client.get<Branch[]>(`/api/auth/companies/${companyId}/branches`);
    return res.data;
  },
  register: async (payload: {
    full_name: string;
    username: string;
    email: string;
    password: string;
    confirm_password: string;
    role: string;
    company_id?: number;
    branch_id?: number;
  }) => {
    const res = await client.post('/api/auth/register', payload);
    return res.data;
  },
  getMe: async () => {
    const res = await client.get('/api/auth/me');
    return res.data;
  },
  getUsers: async () => {
    const res = await client.get('/api/auth/users');
    return res.data;
  },

  // Operational Data Governance & Validation
  updateStock: async (id: number, newStock: number, reason: string, overrideWarning: boolean = false) => {
    const res = await client.put(`/api/inventory/${id}/stock`, {
      new_stock: newStock,
      reason,
      override_warning: overrideWarning
    });
    return res.data;
  },
  validateBatch: async (rows: any[]) => {
    const res = await client.post('/api/inventory/validate-batch', { rows });
    return res.data;
  },
  importBatch: async (rows: any[], reason: string = 'Batch CSV Ingestion by Data Manager') => {
    const res = await client.post('/api/inventory/import-batch', { rows, reason });
    return res.data;
  },
  getDataAuditTrail: async (params?: { user?: string; role?: string; action?: string; validation_result?: string; limit?: number }) => {
    const res = await client.get('/api/audit-trail/data', { params });
    return res.data;
  },

  // Pharmacy Billing & Operational Dispensing
  getBills: async (wardId?: number): Promise<Bill[]> => {
    const res = await client.get<Bill[]>('/api/billing/bills', { params: { ward_id: wardId } });
    return res.data;
  },
  getBillById: async (idOrNumber: string | number): Promise<Bill> => {
    const res = await client.get<Bill>(`/api/billing/bills/${idOrNumber}`);
    return res.data;
  },
  createBill: async (payload: BillCreatePayload): Promise<Bill> => {
    const res = await client.post<Bill>('/api/billing/bills', payload);
    return res.data;
  },
  cancelBill: async (billId: number): Promise<BillCancelResponse> => {
    const res = await client.post<BillCancelResponse>(`/api/billing/bills/${billId}/cancel`);
    return res.data;
  },
  sendBillSMS: async (billId: number): Promise<any> => {
    const res = await client.post(`/api/billing/bills/${billId}/send-sms`);
    return res.data;
  },

  // Patient Refill Reminders
  getPatients: async (): Promise<Patient[]> => {
    const res = await client.get<Patient[]>('/api/reminders/patients');
    return res.data;
  },
  createPatient: async (payload: PatientCreatePayload): Promise<Patient> => {
    const res = await client.post<Patient>('/api/reminders/patients', payload);
    return res.data;
  },
  getReminders: async (params?: { status?: string; patient_id?: number }): Promise<MedicationReminder[]> => {
    const res = await client.get<MedicationReminder[]>('/api/reminders', { params });
    return res.data;
  },
  getReminderLogs: async (reminderId?: number): Promise<NotificationLog[]> => {
    const res = reminderId 
      ? await client.get<NotificationLog[]>(`/api/reminders/${reminderId}/logs`)
      : await client.get<NotificationLog[]>('/api/reminders/logs');
    return res.data;
  },
  processDueReminders: async (simulateDate?: string): Promise<ReminderProcessResult> => {
    const res = await client.post<ReminderProcessResult>('/api/reminders/process', null, {
      params: simulateDate ? { simulate_date: simulateDate } : {}
    });
    return res.data;
  },
  sendSingleReminder: async (reminderId: number, force?: boolean): Promise<any> => {
    const res = await client.post(`/api/reminders/${reminderId}/send`, null, {
      params: { force }
    });
    return res.data;
  },
  getSMSConfig: async (): Promise<SMSGatewayConfig> => {
    const res = await client.get<SMSGatewayConfig>('/api/reminders/sms-config');
    return res.data;
  },
  updateSMSConfig: async (payload: SMSGatewayUpdate): Promise<SMSGatewayConfig> => {
    const res = await client.post<SMSGatewayConfig>('/api/reminders/sms-config', payload);
    return res.data;
  },
  testSMSConnection: async (payload: SMSGatewayUpdate): Promise<SMSConnectionTestResponse> => {
    const res = await client.post<SMSConnectionTestResponse>('/api/reminders/sms-config/test', payload);
    return res.data;
  },

  // Bill Autonomous SMS Notifications
  getBillSMSNotification: async (billId: number): Promise<any> => {
    const res = await client.get(`/api/notifications/sms/bill/${billId}`);
    return res.data;
  },
  simulateSMSDelivery: async (logId: number): Promise<any> => {
    const res = await client.post(`/api/notifications/sms/simulate-delivery/${logId}`);
    return res.data;
  },
  getSMSLogs: async (params?: { bill_id?: number; status?: string; limit?: number }): Promise<NotificationLog[]> => {
    const res = await client.get<NotificationLog[]>('/api/notifications/sms/logs', { params });
    return res.data;
  }
};

