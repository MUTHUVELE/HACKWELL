import React, { useState, useEffect } from 'react';
import {
  Bell,
  Calendar,
  Clock,
  CheckCircle2,
  AlertCircle,
  Search,
  RefreshCw,
  Plus,
  X,
  MessageSquare,
  ShieldCheck,
  UserCheck,
  UserX,
  Send,
  Sparkles,
  ArrowRight,
  Filter,
  Radio,
  Settings,
  Phone,
  Check
} from 'lucide-react';
import { MedicationReminder, NotificationLog, Patient, ReminderProcessResult, SMSGatewayConfig } from '../types';
import { api } from '../services/api';

export const RemindersPage: React.FC = () => {
  const [reminders, setReminders] = useState<MedicationReminder[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Scheduler simulation state
  const [simulateDate, setSimulateDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [schedulerResult, setSchedulerResult] = useState<ReminderProcessResult | null>(null);

  // Selected reminder for log inspection modal
  const [selectedReminderForLogs, setSelectedReminderForLogs] = useState<MedicationReminder | null>(null);
  const [reminderLogs, setReminderLogs] = useState<NotificationLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // New patient modal state
  const [showPatientModal, setShowPatientModal] = useState(false);
  const [newPatientName, setNewPatientName] = useState('');
  const [newPatientMobile, setNewPatientMobile] = useState('');
  const [newPatientEmail, setNewPatientEmail] = useState('');
  const [newPatientConsent, setNewPatientConsent] = useState(true);
  const [creatingPatient, setCreatingPatient] = useState(false);
  const [patientModalError, setPatientModalError] = useState<string | null>(null);

  // Manual test send state
  const [testingId, setTestingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // SMS Gateway state
  const [smsConfig, setSmsConfig] = useState<SMSGatewayConfig | null>(null);
  const [showSmsModal, setShowSmsModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('medisentinel_direct');
  const [twilioSid, setTwilioSid] = useState('');
  const [twilioToken, setTwilioToken] = useState('');
  const [twilioPhone, setTwilioPhone] = useState('');
  const [fast2smsKey, setFast2smsKey] = useState('');
  const [gatewayUrl, setGatewayUrl] = useState('');
  const [savingSmsConfig, setSavingSmsConfig] = useState(false);
  const [smsModalSuccess, setSmsModalSuccess] = useState<string | null>(null);
  const [smsModalError, setSmsModalError] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionTestResult, setConnectionTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const normalizeProviderId = (providerStr?: string): string => {
    if (!providerStr) return 'medisentinel_direct';
    const lower = providerStr.toLowerCase();
    if (lower.includes('twilio')) return 'twilio';
    if (lower.includes('fast2sms') || lower.includes('fast')) return 'fast2sms';
    if (lower.includes('custom') || lower.includes('webhook')) return 'custom_gateway';
    return 'medisentinel_direct';
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [remsData, ptsData, cfgData] = await Promise.all([
        api.getReminders(),
        api.getPatients(),
        api.getSMSConfig().catch(() => null)
      ]);
      setReminders(remsData);
      setPatients(ptsData);
      if (cfgData) {
        setSmsConfig(cfgData);
        setSelectedProvider(cfgData.active_provider_id || normalizeProviderId(cfgData.active_provider));
        if (cfgData.twilio_phone) setTwilioPhone(cfgData.twilio_phone);
        if (cfgData.gateway_url) setGatewayUrl(cfgData.gateway_url);
      }
    } catch (err: any) {
      console.error('Failed to load refill reminders data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSmsConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSmsConfig(true);
    setSmsModalSuccess(null);
    setSmsModalError(null);
    setConnectionTestResult(null);
    try {
      const updated = await api.updateSMSConfig({
        provider: selectedProvider,
        twilio_sid: twilioSid.trim() || undefined,
        twilio_token: twilioToken.trim() || undefined,
        twilio_auth: twilioToken.trim() || undefined,
        twilio_phone: twilioPhone.trim() || undefined,
        twilio_from: twilioPhone.trim() || undefined,
        fast2sms_key: fast2smsKey.trim() || undefined,
        gateway_url: gatewayUrl.trim() || undefined,
      });
      setSmsConfig(updated);
      setSelectedProvider(updated.active_provider_id || normalizeProviderId(updated.active_provider));
      setSmsModalSuccess(`Currently Active Provider: ${updated.active_provider.toUpperCase()}`);
      setTimeout(() => setSmsModalSuccess(null), 4000);
    } catch (err: any) {
      console.error('Failed to update SMS configuration:', err);
      const detail = err.response?.data?.detail || err.message || 'Provider configuration incomplete.';
      setSmsModalError(detail);
    } finally {
      setSavingSmsConfig(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionTestResult(null);
    setSmsModalError(null);
    try {
      const result = await api.testSMSConnection({
        provider: selectedProvider,
        twilio_sid: twilioSid.trim() || undefined,
        twilio_token: twilioToken.trim() || undefined,
        twilio_auth: twilioToken.trim() || undefined,
        twilio_phone: twilioPhone.trim() || undefined,
        twilio_from: twilioPhone.trim() || undefined,
        fast2sms_key: fast2smsKey.trim() || undefined,
        gateway_url: gatewayUrl.trim() || undefined,
      });
      setConnectionTestResult({
        success: result.success,
        message: result.message
      });
    } catch (err: any) {
      setConnectionTestResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Connection test failed.'
      });
    } finally {
      setTestingConnection(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filter reminders
  const filteredReminders = reminders.filter((rem) => {
    const matchesStatus =
      statusFilter === 'ALL' || rem.status === statusFilter;
    const matchesSearch =
      searchQuery === '' ||
      rem.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rem.medicine_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rem.bill_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rem.mobile_number.includes(searchQuery);
    return matchesStatus && matchesSearch;
  });

  // Calculate metrics
  const totalCount = reminders.length;
  const pendingCount = reminders.filter((r) => r.status === 'PENDING').length;
  const deliveredCount = reminders.filter((r) => r.status === 'DELIVERED').length;
  const sentCount = reminders.filter((r) => r.status === 'SENT').length;
  const consentedPatients = patients.filter((p) => p.notification_consent).length;
  const consentRate =
    patients.length > 0
      ? Math.round((consentedPatients / patients.length) * 100)
      : 100;

  // Execute Scheduler Check
  const handleRunScheduler = async () => {
    setIsProcessing(true);
    setSchedulerResult(null);
    setActionMessage(null);
    try {
      const res = await api.processDueReminders(simulateDate);
      setSchedulerResult(res);
      await loadData();
    } catch (err: any) {
      console.error('Scheduler check failed:', err);
      setActionMessage(
        err.response?.data?.detail || 'Failed to execute reminder scheduler check.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  // Quick date jump
  const handleJumpDays = (days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    setSimulateDate(d.toISOString().split('T')[0]);
  };

  // Inspect logs for reminder
  const handleViewLogs = async (rem: MedicationReminder) => {
    setSelectedReminderForLogs(rem);
    setLoadingLogs(true);
    try {
      const logs = await api.getReminderLogs(rem.id);
      setReminderLogs(logs);
    } catch (err) {
      console.error('Failed to load reminder logs:', err);
      setReminderLogs(rem.notification_logs || []);
    } finally {
      setLoadingLogs(false);
    }
  };

  // Manual test trigger
  const handleTestSend = async (reminderId: number) => {
    setTestingId(reminderId);
    setActionMessage(null);
    try {
      const res = await api.sendSingleReminder(reminderId, true);
      setActionMessage(`Test dispatch simulated successfully: ${res.message || 'Sent'}`);
      await loadData();
      if (selectedReminderForLogs?.id === reminderId) {
        handleViewLogs(selectedReminderForLogs);
      }
    } catch (err: any) {
      setActionMessage(err.response?.data?.detail || 'Manual dispatch simulation failed.');
    } finally {
      setTestingId(null);
    }
  };

  // Create Patient
  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPatientName.trim() || !newPatientMobile.trim()) {
      setPatientModalError('Patient full name and mobile number are required.');
      return;
    }
    setCreatingPatient(true);
    setPatientModalError(null);
    try {
      await api.createPatient({
        full_name: newPatientName.trim(),
        mobile_number: newPatientMobile.trim(),
        email: newPatientEmail.trim() || undefined,
        notification_consent: newPatientConsent
      });
      setShowPatientModal(false);
      setNewPatientName('');
      setNewPatientMobile('');
      setNewPatientEmail('');
      setNewPatientConsent(true);
      await loadData();
    } catch (err: any) {
      setPatientModalError(err.response?.data?.detail || 'Failed to register patient.');
    } finally {
      setCreatingPatient(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/80 backdrop-blur-md border border-[#D9E8E3] rounded-3xl p-6 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-2xl bg-[#006B4F]/10 border border-[#006B4F]/20 flex items-center justify-center text-[#006B4F]">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold text-[#12332C]">
                Patient Medication Refill Reminders
              </h1>
              <p className="text-xs text-[#12332C]/65">
                Calculates finish dates from pharmacy bills and dispatches simulated replenishment reminders 7 days prior.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowSmsModal(true)}
            className="px-4 py-2 bg-[#006B4F]/10 border border-[#006B4F]/30 hover:border-[#006B4F] text-[#006B4F] text-xs font-semibold rounded-2xl flex items-center space-x-2 transition-all shadow-xs"
            title="Configure Real SMS Gateway & Providers"
          >
            <Radio className="w-3.5 h-3.5 text-[#006B4F]" />
            <span>Gateway: <strong>{smsConfig?.active_provider?.toUpperCase() || 'DIRECT'}</strong></span>
          </button>
          <button
            onClick={() => setShowPatientModal(true)}
            className="px-4 py-2 bg-white border border-[#D9E8E3] hover:border-[#006B4F] text-[#12332C] text-xs font-semibold rounded-2xl flex items-center space-x-2 transition-all shadow-xs"
          >
            <Plus className="w-4 h-4 text-[#006B4F]" />
            <span>Register Patient</span>
          </button>
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3 py-2 bg-[#006B4F]/10 hover:bg-[#006B4F]/15 text-[#006B4F] text-xs font-semibold rounded-2xl flex items-center space-x-1.5 transition-colors disabled:opacity-50"
            title="Refresh Ledger"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
        <div className="bg-white/85 backdrop-blur-md border border-[#D9E8E3] rounded-2xl p-4 shadow-sm">
          <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider block mb-1">
            Total Reminders
          </span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-[#12332C]">{totalCount}</span>
            <span className="text-[11px] text-gray-500">Tracked</span>
          </div>
        </div>

        <div className="bg-white/85 backdrop-blur-md border border-[#D9E8E3] rounded-2xl p-4 shadow-sm">
          <span className="text-[11px] font-semibold text-amber-600 uppercase tracking-wider block mb-1">
            Pending Due
          </span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-amber-600">{pendingCount}</span>
            <span className="text-[11px] text-gray-500">Awaiting Window</span>
          </div>
        </div>

        <div className="bg-white/85 backdrop-blur-md border border-emerald-200 bg-emerald-50/50 rounded-2xl p-4 shadow-sm">
          <span className="text-[11px] font-semibold text-emerald-800 uppercase tracking-wider block mb-1 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>Real SMS Delivered</span>
          </span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-emerald-800">{deliveredCount}</span>
            <span className="text-[11px] text-emerald-700 font-medium font-mono">DELIVERED</span>
          </div>
        </div>

        <div className="bg-white/85 backdrop-blur-md border border-[#D9E8E3] rounded-2xl p-4 shadow-sm">
          <span className="text-[11px] font-semibold text-[#006B4F] uppercase tracking-wider block mb-1">
            Dispatched (Simulated)
          </span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-[#006B4F]">{sentCount}</span>
            <span className="text-[11px] text-emerald-600 font-medium">Logged</span>
          </div>
        </div>

        <div className="bg-white/85 backdrop-blur-md border border-[#D9E8E3] rounded-2xl p-4 shadow-sm">
          <span className="text-[11px] font-semibold text-indigo-600 uppercase tracking-wider block mb-1">
            Consent Compliance
          </span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-indigo-700">{consentRate}%</span>
            <span className="text-[11px] text-gray-500">({consentedPatients}/{patients.length})</span>
          </div>
        </div>
      </div>

      {/* Interactive Scheduler Demonstration & Simulation Controller */}
      <div className="bg-gradient-to-r from-emerald-900/90 to-teal-900/90 text-white rounded-3xl p-5 shadow-md space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold text-white tracking-wide">
                Refill Reminder Automation & Simulation Controller
              </h2>
            </div>
            <p className="text-[11px] text-emerald-100/75">
              Simulate prospective calendar dates to evaluate upcoming reminder windows without waiting in real time.
            </p>
          </div>

          {/* Quick Date Jumps */}
          <div className="flex items-center space-x-2">
            <span className="text-[11px] text-emerald-200">Quick Test:</span>
            <button
              onClick={() => handleJumpDays(0)}
              className="px-2.5 py-1 text-[11px] bg-white/10 hover:bg-white/20 rounded-xl transition-colors"
            >
              Today
            </button>
            <button
              onClick={() => handleJumpDays(7)}
              className="px-2.5 py-1 text-[11px] bg-white/10 hover:bg-white/20 rounded-xl transition-colors"
            >
              +7 Days
            </button>
            <button
              onClick={() => handleJumpDays(23)}
              className="px-2.5 py-1 text-[11px] bg-white/10 hover:bg-white/20 rounded-xl transition-colors"
            >
              +23 Days
            </button>
          </div>
        </div>

        {/* Date Selector and Trigger */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/10">
          <div className="flex items-center space-x-2 bg-black/20 rounded-2xl px-3 py-1.5 border border-white/10">
            <Calendar className="w-3.5 h-3.5 text-emerald-300" />
            <span className="text-xs text-emerald-100">Simulate Calendar Date:</span>
            <input
              type="date"
              value={simulateDate}
              onChange={(e) => setSimulateDate(e.target.value)}
              className="bg-transparent text-xs font-mono font-bold text-white focus:outline-none cursor-pointer"
            />
          </div>

          <button
            onClick={handleRunScheduler}
            disabled={isProcessing}
            className="px-5 py-2 bg-amber-400 hover:bg-amber-300 text-gray-950 text-xs font-bold rounded-2xl flex items-center space-x-2 shadow-sm transition-all disabled:opacity-50"
          >
            <Clock className={`w-3.5 h-3.5 ${isProcessing ? 'animate-spin' : ''}`} />
            <span>{isProcessing ? 'Executing Scheduler...' : 'Run Scheduler Check'}</span>
          </button>
        </div>

        {/* Scheduler Result Banner */}
        {schedulerResult && (
          <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-3.5 text-xs text-emerald-100 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-white">
                Scheduler Check Completed for {schedulerResult.target_date}:
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-emerald-200">
                <span>Total Evaluated: <strong>{schedulerResult.total_checked}</strong></span>
                <span>• Dispatched (Simulated): <strong className="text-white">{schedulerResult.sent_count}</strong></span>
                <span>• Consent Filtered (Opted Out): <strong>{schedulerResult.opted_out_count}</strong></span>
                <span>• Already Processed: <strong>{schedulerResult.already_processed_count}</strong></span>
              </div>
            </div>
          </div>
        )}
      </div>

      {actionMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-2xl flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-emerald-600 hover:text-emerald-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Reminders Ledger Section */}
      <div className="bg-white/85 backdrop-blur-md border border-[#D9E8E3] rounded-3xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-[#D9E8E3]">
          {/* Status Tabs */}
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1">
            {['ALL', 'PENDING', 'DELIVERED', 'SENT', 'OPTED_OUT', 'CANCELLED'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                  statusFilter === st
                    ? 'bg-[#006B4F] text-white shadow-xs'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {st === 'ALL'
                  ? 'All Reminders'
                  : st === 'PENDING'
                  ? 'Pending Due'
                  : st === 'DELIVERED'
                  ? 'Delivered (Real SMS)'
                  : st === 'SENT'
                  ? 'Sent (Simulated)'
                  : st === 'OPTED_OUT'
                  ? 'Opted Out'
                  : 'Cancelled'}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative w-full md:w-64">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search patient, medicine, bill..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-[#F3FAF7] border border-[#D9E8E3] rounded-xl text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F]"
            />
          </div>
        </div>

        {/* Ledger Table */}
        {filteredReminders.length === 0 ? (
          <div className="py-12 text-center text-xs text-gray-500 space-y-2">
            <Clock className="w-8 h-8 text-gray-300 mx-auto" />
            <p>No refill reminders found matching the current filter.</p>
            <p className="text-[11px] text-gray-400">
              Prescribe medicines in the Billing section with "Days Supply" specified to generate reminders.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-gray-200 text-gray-500 font-semibold">
                  <th className="py-2.5 px-3">Patient</th>
                  <th className="py-2.5 px-3">Medicine & Supply</th>
                  <th className="py-2.5 px-3">Bill Number</th>
                  <th className="py-2.5 px-3">Estimated Finish</th>
                  <th className="py-2.5 px-3">Reminder Due</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredReminders.map((rem) => {
                  const isDelivered = rem.status === 'DELIVERED';
                  const isSent = rem.status === 'SENT';
                  const isPending = rem.status === 'PENDING';
                  const isOptedOut = rem.status === 'OPTED_OUT';
                  const isCancelled = rem.status === 'CANCELLED';

                  return (
                    <tr key={rem.id} className="hover:bg-gray-50/60 transition-colors">
                      {/* Patient Column */}
                      <td className="py-3 px-3">
                        <div className="space-y-0.5">
                          <div className="font-bold text-[#12332C]">{rem.patient_name}</div>
                          <div className="text-[11px] text-gray-500 font-mono">
                            {rem.patient_code} • {rem.mobile_number}
                          </div>
                          <div>
                            {rem.notification_consent ? (
                              <span className="inline-flex items-center space-x-1 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-md">
                                <UserCheck className="w-2.5 h-2.5" />
                                <span>SMS Consent Active</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center space-x-1 text-[10px] text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded-md">
                                <UserX className="w-2.5 h-2.5" />
                                <span>Opted Out</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Medicine & Days Supply */}
                      <td className="py-3 px-3">
                        <div className="space-y-0.5">
                          <div className="font-bold text-[#006B4F]">{rem.medicine_name}</div>
                          <div className="text-[11px] text-gray-600">
                            Qty: <strong className="font-mono">{rem.quantity}</strong> • Supply:{' '}
                            <strong className="font-mono">{rem.days_supply} days</strong>
                          </div>
                        </div>
                      </td>

                      {/* Bill Number */}
                      <td className="py-3 px-3">
                        <div className="space-y-0.5">
                          <span className="font-mono text-gray-700 font-semibold">{rem.bill_number}</span>
                          <div className="text-[10px] text-gray-500">
                            {new Date(rem.bill_date).toLocaleDateString()}
                          </div>
                        </div>
                      </td>

                      {/* Estimated Finish Date */}
                      <td className="py-3 px-3 font-mono text-gray-700">
                        {rem.estimated_finish_date}
                      </td>

                      {/* Reminder Due Date */}
                      <td className="py-3 px-3 font-mono text-gray-700 font-semibold">
                        {rem.reminder_date}
                      </td>

                      {/* Status Badge */}
                      <td className="py-3 px-3 text-center">
                        {isDelivered && (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>DELIVERED</span>
                          </span>
                        )}
                        {isSent && (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-teal-100 text-teal-800">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>SENT (Simulated)</span>
                          </span>
                        )}
                        {isPending && (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                            <Clock className="w-3 h-3" />
                            <span>PENDING</span>
                          </span>
                        )}
                        {isOptedOut && (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-gray-100 text-gray-700">
                            <UserX className="w-3 h-3" />
                            <span>OPTED OUT</span>
                          </span>
                        )}
                        {isCancelled && (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">
                            <X className="w-3 h-3" />
                            <span>CANCELLED</span>
                          </span>
                        )}
                      </td>

                      {/* Action Buttons */}
                      <td className="py-3 px-3 text-right">
                        <div className="inline-flex items-center space-x-1.5">
                          <button
                            onClick={() => handleViewLogs(rem)}
                            className="px-2.5 py-1 text-[11px] font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition-colors flex items-center space-x-1"
                            title="View notification logs"
                          >
                            <MessageSquare className="w-3 h-3 text-gray-500" />
                            <span>Logs</span>
                          </button>

                          {isPending && (
                            <button
                              onClick={() => handleTestSend(rem.id)}
                              disabled={testingId === rem.id}
                              className="px-2.5 py-1 text-[11px] font-semibold text-[#006B4F] bg-[#006B4F]/10 hover:bg-[#006B4F]/20 rounded-xl transition-colors flex items-center space-x-1 disabled:opacity-50"
                              title="Test simulate dispatch now"
                            >
                              <Send className="w-3 h-3" />
                              <span>{testingId === rem.id ? 'Sending...' : 'Test Send'}</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Logs Modal */}
      {selectedReminderForLogs && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <MessageSquare className="w-4 h-4 text-[#006B4F]" />
                <h3 className="text-sm font-bold text-[#12332C]">
                  Delivery Audit & SMS Preview
                </h3>
              </div>
              <button
                onClick={() => setSelectedReminderForLogs(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 bg-[#F3FAF7] p-3 rounded-2xl border border-[#D9E8E3] text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Patient:</span>
                <span className="font-bold text-[#12332C]">
                  {selectedReminderForLogs.patient_name} ({selectedReminderForLogs.mobile_number})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Prescribed Medicine:</span>
                <span className="font-bold text-[#006B4F]">
                  {selectedReminderForLogs.medicine_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Estimated Finish:</span>
                <span className="font-mono text-gray-700">
                  {selectedReminderForLogs.estimated_finish_date}
                </span>
              </div>
            </div>

            {/* Simulated SMS Message Preview Card */}
            <div>
              <label className="text-[11px] font-bold text-gray-600 block mb-1.5 uppercase tracking-wider">
                Simulated SMS Text Template
              </label>
              <div className="bg-emerald-950 text-emerald-100 p-3.5 rounded-2xl font-mono text-xs shadow-inner leading-relaxed border border-emerald-800">
                {selectedReminderForLogs.notification_message ||
                  `Hi ${selectedReminderForLogs.patient_name}, your recently purchased ${selectedReminderForLogs.medicine_name} may be nearing the end of its expected supply around ${selectedReminderForLogs.estimated_finish_date}. Please contact your pharmacy or healthcare provider if you need a refill.`}
              </div>
            </div>

            {/* Audit Logs */}
            <div className="space-y-2 pt-2">
              <label className="text-[11px] font-bold text-gray-600 block uppercase tracking-wider">
                Dispatch Log History
              </label>
              {loadingLogs ? (
                <div className="text-xs text-gray-500 py-4 text-center">Loading logs...</div>
              ) : reminderLogs.length === 0 ? (
                <div className="text-xs text-gray-500 py-3 text-center bg-gray-50 rounded-2xl">
                  No dispatch attempts logged yet for this reminder.
                </div>
              ) : (
                <div className="space-y-2">
                  {reminderLogs.map((log) => (
                    <div
                      key={log.id}
                      className="p-3 bg-gray-50 rounded-2xl border border-gray-100 text-xs space-y-1.5"
                    >
                      <div className="flex justify-between items-center">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-[11px] font-bold text-[#006B4F]">
                            {log.channel}
                          </span>
                          {log.status === 'DELIVERED' ? (
                            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                              <span>DELIVERED</span>
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-200 text-gray-700">
                              {log.status}
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {new Date(log.sent_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-600 font-mono flex items-center space-x-1">
                        <Phone className="w-2.5 h-2.5 text-gray-400" />
                        <span>Recipient: <strong>{log.recipient}</strong></span>
                      </div>
                      <p className="text-[11px] text-gray-700 bg-white p-2 rounded-xl border border-gray-100">{log.message}</p>
                      {log.failure_reason && (
                        <p className="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-1 rounded-lg border border-emerald-200 font-mono">
                          Provider Ref: {log.failure_reason}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-2">
              <button
                onClick={() => setSelectedReminderForLogs(null)}
                className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-2xl transition-colors"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Patient Modal */}
      {showPatientModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleCreatePatient}
            className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <UserCheck className="w-4 h-4 text-[#006B4F]" />
                <h3 className="text-sm font-bold text-[#12332C]">
                  Register New Patient for Refill Alerts
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowPatientModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {patientModalError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-2xl">
                {patientModalError}
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh Patel"
                  value={newPatientName}
                  onChange={(e) => setNewPatientName(e.target.value)}
                  className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Mobile Number (for SMS Alerts) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. +91 98401 23456"
                  value={newPatientMobile}
                  onChange={(e) => setNewPatientMobile(e.target.value)}
                  className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Email Address (Optional)
                </label>
                <input
                  type="email"
                  placeholder="e.g. ramesh@example.com"
                  value={newPatientEmail}
                  onChange={(e) => setNewPatientEmail(e.target.value)}
                  className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F]"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center space-x-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newPatientConsent}
                    onChange={(e) => setNewPatientConsent(e.target.checked)}
                    className="w-4 h-4 rounded text-[#006B4F] focus:ring-[#006B4F]"
                  />
                  <span className="text-xs text-gray-700 font-medium">
                    Patient grants explicit consent for automated SMS refill reminders
                  </span>
                </label>
                <p className="text-[10px] text-gray-400 mt-1 pl-6">
                  Complies with regulatory patient privacy; reminders are suppressed if unchecked.
                </p>
              </div>
            </div>

            <div className="pt-3 flex items-center space-x-3">
              <button
                type="button"
                onClick={() => setShowPatientModal(false)}
                className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-2xl transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingPatient}
                className="flex-1 py-2 bg-[#006B4F] hover:bg-[#00523C] text-white text-xs font-bold rounded-2xl transition-colors disabled:opacity-50"
              >
                {creatingPatient ? 'Registering...' : 'Save Patient'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* SMS Gateway Settings Modal */}
      {showSmsModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleSaveSmsConfig}
            className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <Radio className="w-4 h-4 text-[#006B4F]" />
                <h3 className="text-sm font-bold text-[#12332C]">
                  Real SMS Provider & Gateway Settings
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowSmsModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {smsModalSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-2xl flex items-center space-x-2">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{smsModalSuccess}</span>
              </div>
            )}

            {smsModalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-2xl flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{smsModalError}</span>
              </div>
            )}

            {connectionTestResult && (
              <div className={`p-3 border text-xs rounded-2xl flex items-center space-x-2 ${
                connectionTestResult.success
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}>
                {connectionTestResult.success ? (
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                )}
                <span>{connectionTestResult.message}</span>
              </div>
            )}

            <div className="p-3 bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 font-medium">Currently Active Provider:</span>
                <span className="font-mono font-bold text-[#006B4F] bg-white px-2.5 py-0.5 rounded-full border border-[#D9E8E3]">
                  {smsConfig?.active_provider?.toUpperCase() || 'MEDISENTINEL_DIRECT'}
                </span>
              </div>
              <p className="text-[11px] text-gray-500 leading-relaxed">
                When billing transactions complete or reminders reach their scheduled reminder date, this active provider dispatches real SMS to the patient phone number, and records the <strong>DELIVERED</strong> status in the MediSentinel Notification Log.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Select Active SMS Provider
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: 'medisentinel_direct', label: 'MediSentinel Direct', desc: 'Carrier-grade verified dispatch', isConfigured: true },
                    { id: 'fast2sms', label: 'Fast2SMS (India)', desc: 'DLT-free Quick SMS Route', isConfigured: smsConfig?.has_fast2sms },
                    { id: 'twilio', label: 'Twilio REST API', desc: 'Global carrier network', isConfigured: smsConfig?.has_twilio },
                    { id: 'custom_gateway', label: 'Custom HTTP Gateway', desc: 'Enterprise SMS webhook', isConfigured: smsConfig?.has_custom_gateway }
                  ].map((p) => (
                    <div
                      key={p.id}
                      onClick={() => {
                        setSelectedProvider(p.id);
                        setSmsModalError(null);
                        setConnectionTestResult(null);
                      }}
                      className={`p-3 rounded-2xl border cursor-pointer transition-all ${
                        selectedProvider === p.id
                          ? 'border-[#006B4F] bg-[#006B4F]/5 shadow-xs'
                          : 'border-gray-200 bg-white hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[#12332C]">{p.label}</span>
                        {selectedProvider === p.id ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#006B4F]" />
                        ) : p.isConfigured ? (
                          <span className="text-[9px] font-semibold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-md">Saved</span>
                        ) : null}
                      </div>
                      <span className="text-[10px] text-gray-500 block mt-0.5">{p.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedProvider === 'fast2sms' && (
                <div className="space-y-2 pt-2 border-t border-gray-100">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-gray-700 block">
                      Fast2SMS Authorization API Key
                    </label>
                    {smsConfig?.has_fast2sms && (
                      <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        ✓ Key Stored (Leave blank to keep)
                      </span>
                    )}
                  </div>
                  <input
                    type="password"
                    placeholder={smsConfig?.has_fast2sms ? "•••••••••••••••• (API Key Configured)" : "Enter Fast2SMS API Key"}
                    value={fast2smsKey}
                    onChange={(e) => setFast2smsKey(e.target.value)}
                    className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F] font-mono"
                  />
                  <p className="text-[10px] text-gray-500">
                    Dispatches directly to Indian +91 numbers via Fast2SMS quick transactional route.
                  </p>
                </div>
              )}

              {selectedProvider === 'twilio' && (
                <div className="space-y-3 pt-2 border-t border-gray-100">
                  {smsConfig?.has_twilio && (
                    <div className="flex items-center justify-end">
                      <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        ✓ Credentials Stored (Leave blank to keep)
                      </span>
                    </div>
                  )}
                  <div>
                    <label className="text-xs font-semibold text-gray-700 block mb-1">
                      Twilio Account SID
                    </label>
                    <input
                      type="text"
                      placeholder={smsConfig?.has_twilio ? "•••••••••••••••• (Account SID Configured)" : "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}
                      value={twilioSid}
                      onChange={(e) => setTwilioSid(e.target.value)}
                      className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F] font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-700 block mb-1">
                      Twilio Auth Token
                    </label>
                    <input
                      type="password"
                      placeholder={smsConfig?.has_twilio ? "•••••••••••••••• (Auth Token Configured)" : "Auth Token"}
                      value={twilioToken}
                      onChange={(e) => setTwilioToken(e.target.value)}
                      className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F] font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-700 block mb-1">
                      Twilio Sender Phone Number (E.164)
                    </label>
                    <input
                      type="text"
                      placeholder={smsConfig?.twilio_phone || "+1234567890"}
                      value={twilioPhone}
                      onChange={(e) => setTwilioPhone(e.target.value)}
                      className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F] font-mono"
                    />
                  </div>
                </div>
              )}

              {selectedProvider === 'custom_gateway' && (
                <div className="space-y-2 pt-2 border-t border-gray-100">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-gray-700 block">
                      Custom SMS Webhook URL
                    </label>
                    {smsConfig?.has_custom_gateway && (
                      <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        ✓ Webhook URL Stored
                      </span>
                    )}
                  </div>
                  <input
                    type="url"
                    placeholder={smsConfig?.gateway_url || "https://sms-provider.internal/api/send"}
                    value={gatewayUrl}
                    onChange={(e) => setGatewayUrl(e.target.value)}
                    className="w-full bg-[#F3FAF7] border border-[#D9E8E3] rounded-2xl px-3.5 py-2 text-xs text-[#12332C] focus:outline-none focus:ring-2 focus:ring-[#006B4F] font-mono"
                  />
                </div>
              )}
            </div>

            <div className="pt-3 flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setShowSmsModal(false)}
                className="py-2 px-3.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-2xl transition-colors"
              >
                Close
              </button>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testingConnection}
                className="py-2 px-3.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold rounded-2xl transition-colors disabled:opacity-50"
              >
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </button>
              <button
                type="submit"
                disabled={savingSmsConfig}
                className="flex-1 py-2 bg-[#006B4F] hover:bg-[#00523C] text-white text-xs font-bold rounded-2xl transition-colors disabled:opacity-50 shadow-xs"
              >
                {savingSmsConfig ? 'Saving...' : 'Apply Provider'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
