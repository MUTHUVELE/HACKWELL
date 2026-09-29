import React from 'react';
import {
  LayoutDashboard,
  Bell,
  Boxes,
  TrendingUp,
  ShieldCheck,
  ShoppingCart,
  ArrowLeftRight,
  Trash2,
  Bot,
  Zap,
  BarChart3,
  History,
  Star,
  Database,
  Receipt,
  CalendarClock
} from 'lucide-react';

export type ActiveTab =
  | 'dashboard'
  | 'alerts'
  | 'inventory'
  | 'forecasts'
  | 'approvals'
  | 'procurement'
  | 'distribution'
  | 'waste'
  | 'agents'
  | 'simulation'
  | 'analytics'
  | 'audit'
  | 'data-quality'
  | 'billing'
  | 'reminders';

interface SidebarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  pendingApprovalsCount: number;
  criticalAlertsCount: number;
  currentRole: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  pendingApprovalsCount,
  criticalAlertsCount,
  currentRole
}) => {
  const isPharmacistOrAdmin =
    currentRole.toUpperCase().includes('PHARMACIST') ||
    currentRole.toUpperCase().includes('ADMIN');

  const workspaceItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'billing', label: 'Billing', icon: Receipt },
    { id: 'reminders', label: 'Refill Reminders', icon: CalendarClock },
    { id: 'approvals', label: 'Approvals', icon: ShieldCheck, badge: pendingApprovalsCount, badgeColor: 'bg-[#16A34A]/25 text-emerald-300' },
    { id: 'alerts', label: 'Live Alerts', icon: Bell, badge: criticalAlertsCount, badgeColor: 'bg-[#DC2626]/30 text-rose-200' },
    { id: 'inventory', label: 'Inventory', icon: Boxes },
    { id: 'forecasts', label: 'Forecasts', icon: TrendingUp },
  ];


  const operationsItems = [
    { id: 'procurement', label: 'Procurement', icon: ShoppingCart },
    { id: 'distribution', label: 'Transfers', icon: ArrowLeftRight },
    { id: 'waste', label: 'Waste Guard', icon: Trash2 },
    { id: 'agents', label: 'Agent Network', icon: Bot },
    { id: 'simulation', label: 'Dengue Outbreak', icon: Zap, highlight: true },
    { id: 'data-quality', label: 'Data Quality', icon: Database },
    { id: 'analytics', label: 'Pilot Targets', icon: BarChart3 },
    { id: 'audit', label: 'Audit Ledger', icon: History },
  ];

  const renderNavButton = (item: any) => {
    const Icon = item.icon;
    const isActive = activeTab === item.id;

    return (
      <button
        key={item.id}
        onClick={() => setActiveTab(item.id as ActiveTab)}
        className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-2xl text-xs font-medium transition-all relative group ${
          isActive
            ? 'bg-[#006B4F] text-white shadow-sm border border-emerald-500/30'
            : item.highlight
            ? 'text-[#F4B400] hover:text-white hover:bg-white/[0.08]'
            : 'text-[#D9E8E3]/85 hover:text-white hover:bg-white/[0.08]'
        }`}
      >
        {/* Active Left Indicator Pill */}
        {isActive && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-5 bg-[#F4B400] rounded-r-full shadow-sm"></span>
        )}

        <div className="flex items-center space-x-3 ml-1">
          <Icon className={`w-4 h-4 transition-colors ${
            isActive
              ? 'text-white'
              : item.highlight
              ? 'text-[#F4B400] animate-pulse'
              : 'text-[#D9E8E3]/70 group-hover:text-white'
          }`} />
          <span className="tracking-wide text-xs">{item.label}</span>
        </div>

        {item.badge !== undefined && item.badge > 0 && (
          <span className={`px-2 py-0.5 text-[10px] font-mono rounded-full font-bold ${item.badgeColor}`}>
            {item.badge}
          </span>
        )}

        {item.highlight && !item.badge && (
          <span className="px-2 py-0.5 text-[9px] rounded-full font-bold uppercase bg-[#F4B400] text-[#12332C] shadow-sm">
            SURGE
          </span>
        )}
      </button>
    );
  };

  return (
    <aside className="w-60 bg-[#004D3A] border-r border-[#003B2C] flex flex-col h-full select-none justify-between p-4">
      <div className="space-y-6">
        {/* Brand Header matching reference logo style */}
        <div className="px-2 py-1 flex items-center space-x-3">
          <div className="w-9 h-9 rounded-2xl bg-[#006B4F] border border-emerald-400/30 flex items-center justify-center shadow-md">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-white fill-current" preserveAspectRatio="xMidYMid meet">
              <path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3zm1 14h-2v-2h2v2zm0-4h-2V7h2v5z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center space-x-1">
              <span className="font-extrabold tracking-tight text-base text-white">MediSentinel</span>
              <span className="w-1.5 h-1.5 rounded-full bg-[#008F83]"></span>
            </div>
            <p className="text-[10px] text-[#D9E8E3]/75 font-medium">Autonomous Pharmacy AI</p>
          </div>
        </div>

        {/* Section 1: Workspace */}
        <div className="space-y-1">
          <div className="px-3 text-[11px] font-semibold text-[#D9E8E3]/60 tracking-wider uppercase">
            Workspace
          </div>
          <div className="space-y-1">
            {workspaceItems.map(renderNavButton)}
          </div>
        </div>

        {/* Section 2: Operations */}
        <div className="space-y-1">
          <div className="px-3 text-[11px] font-semibold text-[#D9E8E3]/60 tracking-wider uppercase">
            Operations
          </div>
          <div className="space-y-1">
            {operationsItems.map(renderNavButton)}
          </div>
        </div>
      </div>

      {/* Bottom User Card matching reference card */}
      <div className="pt-4 border-t border-[#003B2C]">
        <div className="bg-[#003B2C] border border-[#004D3A] rounded-2xl p-2.5 flex items-center justify-between shadow-sm">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#006B4F] border border-white/20 flex items-center justify-center text-white text-xs font-bold shrink-0">
              SP
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-white truncate">Dr. Sarah Alston</div>
              <div className="text-[10px] text-[#D9E8E3]/70 truncate">{currentRole.split(' ')[0]}</div>
            </div>
          </div>
          <div className="flex items-center space-x-1 bg-[#F4B400]/15 px-1.5 py-0.5 rounded-full border border-[#F4B400]/30 text-[#F4B400] text-[10px] font-semibold">
            <Star className="w-2.5 h-2.5 fill-current" />
            <span>5.0</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
