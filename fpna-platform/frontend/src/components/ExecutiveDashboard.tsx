import React, { useState, useEffect } from 'react';
import {
  Database, Calculator, Users, FileSpreadsheet, Upload,
  DollarSign, TrendingUp, BarChart2, Layers, Check,
  ChevronRight, ChevronUp, ChevronDown, Loader2,
} from 'lucide-react';
import { analysisAPI, budgetPlanningAPI } from '../services/api';

const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const fmtAmt = (num: number): string => {
  if (num === null || num === undefined) return '-';
  const abs = Math.abs(num);
  if (abs >= 1e12) return (num / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9) return (num / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return (num / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (num / 1e3).toFixed(1) + 'K';
  return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const Sparkline = ({ data, color }: { data: number[]; color: string }) => {
  const max = Math.max(...data.map(Math.abs), 1);
  return (
    <div className="flex items-end gap-px h-8">
      {data.map((v, i) => (
        <div key={i} className={`flex-1 ${color} rounded-sm min-h-[2px] opacity-70`}
          style={{ height: `${Math.max(Math.abs(v) / max * 100, 5)}%` }} />
      ))}
    </div>
  );
};

interface Props {
  theme: string;
  onNavigate: (page: string) => void;
}

const ExecutiveDashboard: React.FC<Props> = ({ theme, onNavigate }) => {
  const [kpis, setKpis] = useState<any>(null);
  const [monthlyTrend, setMonthlyTrend] = useState<any>(null);
  const [workflowStatus, setWorkflowStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [fiscalYear] = useState(2026);
  const isDark = theme === 'dark';

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [kpiData, trendData, wfStatus] = await Promise.all([
          analysisAPI.getDashboardKPIs(fiscalYear).catch(() => null),
          analysisAPI.getMonthlyTrend(fiscalYear).catch(() => null),
          budgetPlanningAPI.getWorkflowStatus(fiscalYear).catch(() => null),
        ]);
        setKpis(kpiData);
        setMonthlyTrend(trendData);
        setWorkflowStatus(wfStatus);
      } catch (err) {
        console.error('Dashboard load failed:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [fiscalYear]);

  const sc = kpis?.status_counts || {};
  const cardBg = isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200';
  const textP = isDark ? 'text-slate-50' : 'text-slate-900';
  const textS = isDark ? 'text-slate-400' : 'text-slate-500';

  const pipelineSteps = [
    { key: 'source', label: 'Source', icon: <Database className="w-5 h-5" />, done: (workflowStatus?.total_plans || 0) > 0 },
    { key: 'baseline', label: 'Baseline', icon: <Calculator className="w-5 h-5" />, done: (workflowStatus?.total_plans || 0) > 0 },
    { key: 'assign', label: 'Assign', icon: <Users className="w-5 h-5" />, done: (kpis?.departments || 0) > 1 },
    { key: 'entry', label: 'Entry', icon: <FileSpreadsheet className="w-5 h-5" />, done: (sc.submitted || 0) + (sc.dept_approved || 0) + (sc.cfo_approved || 0) + (sc.ceo_approved || 0) + (sc.exported || 0) > 0 },
    { key: 'approve', label: 'Approve', icon: <Check className="w-5 h-5" />, done: (sc.cfo_approved || 0) + (sc.ceo_approved || 0) + (sc.exported || 0) > 0 },
    { key: 'export', label: 'Export', icon: <Upload className="w-5 h-5" />, done: (sc.exported || 0) > 0 },
  ];

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className={`text-2xl font-bold ${textP}`}>Executive Dashboard</h1>
          <p className={`text-sm ${textS}`}>FP&A Budget Planning Overview - FY {fiscalYear}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => onNavigate('budget-planning')}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium">
            <Calculator className="w-4 h-4" /> Budget Planning
          </button>
          <button onClick={() => onNavigate('budget-analysis')}
            className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium border ${isDark ? 'bg-slate-800 border-slate-700 text-slate-100' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}>
            <BarChart2 className="w-4 h-4" /> Analysis
          </button>
        </div>
      </div>

      {/* Pipeline Progress */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <h2 className={`text-sm font-semibold mb-4 ${textP}`}>Budget Planning Pipeline</h2>
        <div className="flex items-center gap-1">
          {pipelineSteps.map((s, i) => (
            <React.Fragment key={s.key}>
              <div className="flex-1 flex flex-col items-center">
                <div className={`w-11 h-11 rounded-full flex items-center justify-center transition-colors ${
                  s.done ? 'bg-emerald-100 text-emerald-600' : isDark ? 'bg-slate-800 text-slate-500' : 'bg-gray-100 text-gray-400'
                }`}>{s.icon}</div>
                <span className={`mt-1.5 text-xs font-medium ${s.done ? 'text-emerald-600' : textS}`}>{s.label}</span>
              </div>
              {i < pipelineSteps.length - 1 && (
                <div className={`flex-1 h-0.5 max-w-[40px] ${s.done ? 'bg-emerald-300' : isDark ? 'bg-slate-700' : 'bg-gray-200'}`} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className={`rounded-xl border p-4 ${cardBg}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-medium ${textS}`}>Plan Total (FY {fiscalYear})</span>
            <div className="p-1.5 bg-indigo-100 rounded-lg"><DollarSign className="w-4 h-4 text-indigo-600" /></div>
          </div>
          <p className={`text-2xl font-bold ${textP}`}>{fmtAmt(kpis?.total_adjusted || 0)}</p>
          {kpis?.yoy_change_pct !== undefined && (
            <p className={`text-xs mt-1 flex items-center gap-1 ${kpis.yoy_change_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
              {kpis.yoy_change_pct >= 0 ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {kpis.yoy_change_pct >= 0 ? '+' : ''}{kpis.yoy_change_pct}% vs prior year
            </p>
          )}
        </div>

        <div className={`rounded-xl border p-4 ${cardBg}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-medium ${textS}`}>Driver Impact</span>
            <div className="p-1.5 bg-blue-100 rounded-lg"><TrendingUp className="w-4 h-4 text-blue-600" /></div>
          </div>
          <p className={`text-2xl font-bold ${(kpis?.driver_impact || 0) >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>
            {(kpis?.driver_impact || 0) >= 0 ? '+' : ''}{fmtAmt(kpis?.driver_impact || 0)}
          </p>
          <p className={`text-xs mt-1 ${textS}`}>Adjusted - Baseline</p>
        </div>

        <div className={`rounded-xl border p-4 ${cardBg}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-medium ${textS}`}>Departments</span>
            <div className="p-1.5 bg-purple-100 rounded-lg"><Users className="w-4 h-4 text-purple-600" /></div>
          </div>
          <p className={`text-2xl font-bold ${textP}`}>{kpis?.departments || 0}</p>
          <p className={`text-xs mt-1 ${textS}`}>{kpis?.budget_groups || 0} budget groups</p>
        </div>

        <div className={`rounded-xl border p-4 ${cardBg}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-medium ${textS}`}>Driver Coverage</span>
            <div className="p-1.5 bg-amber-100 rounded-lg"><Layers className="w-4 h-4 text-amber-600" /></div>
          </div>
          <p className={`text-2xl font-bold ${textP}`}>{kpis?.driver_coverage_pct || 0}%</p>
          <div className={`w-full rounded-full h-1.5 mt-2 ${isDark ? 'bg-slate-700' : 'bg-gray-200'}`}>
            <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${kpis?.driver_coverage_pct || 0}%` }} />
          </div>
        </div>
      </div>

      {/* Row 2: Status + Monthly Trend */}
      <div className="grid grid-cols-3 gap-4">
        <div className={`rounded-xl border p-4 ${cardBg}`}>
          <h3 className={`text-sm font-semibold mb-3 ${textP}`}>Plan Status</h3>
          <div className="space-y-2.5">
            {[
              { label: 'Draft', key: 'draft', color: 'bg-gray-400', text: 'text-gray-600' },
              { label: 'Submitted', key: 'submitted', color: 'bg-blue-500', text: 'text-blue-600' },
              { label: 'Dept Approved', key: 'dept_approved', color: 'bg-teal-500', text: 'text-teal-600' },
              { label: 'CFO Approved', key: 'cfo_approved', color: 'bg-emerald-500', text: 'text-emerald-600' },
              { label: 'CEO Approved', key: 'ceo_approved', color: 'bg-indigo-500', text: 'text-indigo-600' },
              { label: 'Exported', key: 'exported', color: 'bg-purple-500', text: 'text-purple-600' },
            ].map(s => {
              const count = sc[s.key] || 0;
              const total = Math.max(kpis?.plan_count || 1, 1);
              return (
                <div key={s.key} className="flex items-center gap-3">
                  <span className={`text-xs w-24 ${textS}`}>{s.label}</span>
                  <div className={`flex-1 rounded-full h-2 overflow-hidden ${isDark ? 'bg-slate-800' : 'bg-gray-100'}`}>
                    <div className={`h-full rounded-full ${s.color}`} style={{ width: `${Math.max(count / total * 100, count > 0 ? 4 : 0)}%` }} />
                  </div>
                  <span className={`text-xs font-bold w-6 text-right ${s.text}`}>{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className={`col-span-2 rounded-xl border p-4 ${cardBg}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={`text-sm font-semibold ${textP}`}>Monthly Trend</h3>
            <div className="flex gap-3">
              {monthlyTrend?.years && Object.keys(monthlyTrend.years).map((yr: string, i: number) => (
                <span key={yr} className={`flex items-center gap-1 text-xs ${textS}`}>
                  <div className={`w-2.5 h-2 rounded-sm ${i === 0 ? 'bg-gray-300' : i === 1 ? 'bg-blue-400' : 'bg-indigo-600'}`} />
                  FY {yr}
                </span>
              ))}
            </div>
          </div>
          {monthlyTrend?.years ? (
            <div className="space-y-3">
              {Object.entries(monthlyTrend.years).map(([yr, data]: [string, any], i: number) => (
                <div key={yr}>
                  <div className={`text-xs mb-1 ${textS}`}>
                    FY {yr} {Number(yr) === fiscalYear && <span className="text-indigo-500 font-medium">(Plan)</span>}
                  </div>
                  <Sparkline data={data} color={i === 0 ? 'bg-gray-300' : i === 1 ? 'bg-blue-400' : 'bg-indigo-500'} />
                </div>
              ))}
              <div className={`flex justify-between text-[10px] mt-1 ${textS}`}>
                {MONTHS_SHORT.map(m => <span key={m}>{m}</span>)}
              </div>
            </div>
          ) : (
            <div className={`text-center py-8 ${textS}`}>No trend data yet</div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { page: 'data-integration', icon: <Database className="w-5 h-5 text-blue-600" />, bg: 'bg-blue-50', label: 'Data Integration', sub: 'DWH connections' },
          { page: 'budget-planning', icon: <Calculator className="w-5 h-5 text-emerald-600" />, bg: 'bg-emerald-50', label: 'Budget Planning', sub: '7-step workflow' },
          { page: 'budget-analysis', icon: <BarChart2 className="w-5 h-5 text-indigo-600" />, bg: 'bg-indigo-50', label: 'Analysis', sub: 'Delta & variance' },
          { page: 'approvals', icon: <Users className="w-5 h-5 text-amber-600" />, bg: 'bg-amber-50', label: 'Approvals', sub: 'Review & approve' },
          { page: 'variance-report', icon: <TrendingUp className="w-5 h-5 text-purple-600" />, bg: 'bg-purple-50', label: 'Fact vs Plan', sub: 'Variance report' },
        ].map(a => (
          <button key={a.page} onClick={() => onNavigate(a.page)}
            className={`rounded-xl border p-3 text-left transition-colors ${isDark ? 'bg-slate-900 border-slate-800 hover:bg-slate-800' : 'bg-white border-gray-200 hover:bg-gray-50'}`}>
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-lg ${a.bg}`}>{a.icon}</div>
              <div>
                <p className={`font-medium text-sm ${textP}`}>{a.label}</p>
                <p className={`text-xs ${textS}`}>{a.sub}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ExecutiveDashboard;
