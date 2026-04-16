import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, BarChart2, PieChart,
  ArrowUpRight, ArrowDownRight, Minus,
  RefreshCw, Download, Filter, Layers,
  GitCompare, Activity, Target, AlertCircle, Loader2,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import { analysisAPI } from '../services/api';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const fmt = (v: number): string => {
  if (v === null || v === undefined) return '-';
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const pctFmt = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

const DeltaIndicator = ({ value, size = 'sm' }: { value: number; size?: string }) => {
  const cls = size === 'lg' ? 'text-base font-bold' : 'text-xs font-medium';
  if (value > 0) return <span className={`flex items-center gap-0.5 text-emerald-600 ${cls}`}><ArrowUpRight className="w-3.5 h-3.5" />{pctFmt(value)}</span>;
  if (value < 0) return <span className={`flex items-center gap-0.5 text-red-500 ${cls}`}><ArrowDownRight className="w-3.5 h-3.5" />{pctFmt(value)}</span>;
  return <span className={`flex items-center gap-0.5 text-gray-400 ${cls}`}><Minus className="w-3.5 h-3.5" />0%</span>;
};

const MiniBar = ({ value, max, color }: { value: number; max: number; color: string }) => {
  const pct = max !== 0 ? Math.min(Math.abs(value) / Math.abs(max) * 100, 100) : 0;
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
};

// Sparkline (pure CSS bars)
const Sparkline = ({ data, color = 'bg-blue-500' }: { data: number[]; color?: string }) => {
  const max = Math.max(...data.map(Math.abs), 1);
  return (
    <div className="flex items-end gap-px h-10">
      {data.map((v, i) => (
        <div key={i} className="flex-1 flex flex-col justify-end">
          <div className={`${color} rounded-sm min-h-[2px] opacity-80`} style={{ height: `${Math.max(Math.abs(v) / max * 100, 4)}%` }} title={`${MONTHS[i]}: ${fmt(v)}`} />
        </div>
      ))}
    </div>
  );
};

type Tab = 'yoy' | 'plan-delta' | 'drivers';

export const AnalysisDashboard = () => {
  const [fiscalYear, setFiscalYear] = useState(2026);
  const [activeTab, setActiveTab] = useState<Tab>('yoy');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [yoyData, setYoyData] = useState<any>(null);
  const [planDelta, setPlanDelta] = useState<any>(null);
  const [monthlyTrend, setMonthlyTrend] = useState<any>(null);
  const [sortField, setSortField] = useState<string>('total_change');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set());

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [yoy, pd, mt] = await Promise.all([
        analysisAPI.getYoYDelta(fiscalYear),
        analysisAPI.getPlanDelta(fiscalYear),
        analysisAPI.getMonthlyTrend(fiscalYear),
      ]);
      setYoyData(yoy);
      setPlanDelta(pd);
      setMonthlyTrend(mt);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load analysis data');
    } finally {
      setLoading(false);
    }
  }, [fiscalYear]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const toggleSort = (field: string) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortIcon = ({ field }: { field: string }) => sortField === field
    ? (sortDir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />)
    : <ChevronDown className="w-3 h-3 opacity-30" />;

  const sorted = (arr: any[]) => {
    return [...arr].sort((a, b) => {
      const av = a[sortField] || 0;
      const bv = b[sortField] || 0;
      return sortDir === 'desc' ? bv - av : av - bv;
    });
  };

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'yoy', label: 'Year-over-Year Delta', icon: <GitCompare className="w-4 h-4" /> },
    { id: 'plan-delta', label: 'Plan vs Historical', icon: <Target className="w-4 h-4" /> },
    { id: 'drivers', label: 'Driver Contribution', icon: <Activity className="w-4 h-4" /> },
  ];

  // Grand totals for header cards
  const gt = planDelta?.grand_totals || {};

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budget Analysis</h1>
          <p className="text-sm text-gray-500 mt-0.5">Year-over-year deltas, plan variance decomposition, and driver contribution</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={fiscalYear} onChange={e => setFiscalYear(Number(e.target.value))} className="border rounded-lg px-3 py-2 text-sm bg-white">
            {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>FY {y}</option>)}
          </select>
          <button onClick={loadAll} disabled={loading} className="p-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-5 gap-4">
            <div className="bg-white rounded-xl border p-4">
              <div className="text-xs text-gray-500 mb-1">Prior Year (FY {fiscalYear - 1})</div>
              <div className="text-xl font-bold text-gray-900">{fmt(gt.prior_year_actual || 0)}</div>
              <div className="text-xs text-gray-400 mt-1">Historical actual</div>
            </div>
            <div className="bg-white rounded-xl border p-4">
              <div className="text-xs text-gray-500 mb-1">Plan Baseline</div>
              <div className="text-xl font-bold text-gray-900">{fmt(gt.plan_baseline || 0)}</div>
              <div className="flex items-center gap-1 mt-1">
                <DeltaIndicator value={gt.prior_year_actual ? ((gt.plan_baseline - gt.prior_year_actual) / Math.abs(gt.prior_year_actual) * 100) : 0} />
                <span className="text-xs text-gray-400">organic</span>
              </div>
            </div>
            <div className="bg-white rounded-xl border p-4 ring-2 ring-indigo-100">
              <div className="text-xs text-indigo-600 font-medium mb-1">Plan Adjusted (FY {fiscalYear})</div>
              <div className="text-xl font-bold text-indigo-700">{fmt(gt.plan_adjusted || 0)}</div>
              <DeltaIndicator value={gt.total_variance_pct || 0} size="lg" />
            </div>
            <div className="bg-white rounded-xl border p-4">
              <div className="text-xs text-gray-500 mb-1">Organic Change</div>
              <div className={`text-xl font-bold ${(gt.organic_change || 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{fmt(gt.organic_change || 0)}</div>
              <div className="text-xs text-gray-400 mt-1">Baseline shift from prior</div>
            </div>
            <div className="bg-white rounded-xl border p-4">
              <div className="text-xs text-gray-500 mb-1">Driver Impact</div>
              <div className={`text-xl font-bold ${(gt.driver_impact || 0) >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>{fmt(gt.driver_impact || 0)}</div>
              <div className="text-xs text-gray-400 mt-1">Driver adjustments total</div>
            </div>
          </div>

          {/* Monthly Trend Sparklines */}
          {monthlyTrend?.years && (
            <div className="bg-white rounded-xl border p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700">Monthly Trend Comparison</h3>
                <div className="flex gap-4">
                  {Object.keys(monthlyTrend.years).map((yr: string, i: number) => (
                    <span key={yr} className="flex items-center gap-1.5 text-xs text-gray-500">
                      <div className={`w-3 h-2 rounded-sm ${i === 0 ? 'bg-gray-300' : i === 1 ? 'bg-blue-400' : 'bg-indigo-600'}`} />
                      FY {yr}
                    </span>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-6">
                {Object.entries(monthlyTrend.years).map(([yr, data]: [string, any], i: number) => (
                  <div key={yr}>
                    <div className="text-xs text-gray-400 mb-1 font-medium">FY {yr} {Number(yr) === fiscalYear && <span className="text-indigo-500">(Plan)</span>}</div>
                    <Sparkline data={data} color={i === 0 ? 'bg-gray-300' : i === 1 ? 'bg-blue-400' : 'bg-indigo-600'} />
                    <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                      {MONTHS.map(m => <span key={m}>{m}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {tabs.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === t.id ? 'bg-white shadow text-indigo-700' : 'text-gray-600 hover:text-gray-900'
                }`}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          {/* TAB: Year-over-Year Delta */}
          {activeTab === 'yoy' && yoyData && (
            <div className="bg-white rounded-xl border overflow-hidden">
              <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-800">Year-over-Year Delta by Budget Group</h3>
                  <p className="text-xs text-gray-500">3-year historical + plan year with absolute & percentage deltas</p>
                </div>
                <div className="flex items-center gap-1 text-xs text-gray-400">
                  {yoyData.years_analyzed?.map((y: string) => <span key={y} className="px-2 py-0.5 bg-white border rounded">{y}</span>)}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Budget Group</th>
                      {yoyData.years_analyzed?.map((y: string) => (
                        <th key={y} className="text-right px-3 py-2 font-medium text-gray-600">{y}</th>
                      ))}
                      {Object.keys(yoyData.groups?.[0]?.deltas || {}).map((dk: string) => (
                        <th key={dk} className="text-right px-3 py-2 font-medium text-gray-600">
                          <span className="text-xs">Δ {dk.replace('_to_', '→')}</span>
                        </th>
                      ))}
                      <th className="text-right px-3 py-2 font-medium text-gray-600">CAGR</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Driver</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {yoyData.groups?.map((g: any) => (
                      <tr key={g.budgeting_group_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-gray-800 text-xs leading-tight">{g.budgeting_group_name}</div>
                        </td>
                        {yoyData.years_analyzed?.map((y: string) => (
                          <td key={y} className="px-3 py-2.5 text-right text-xs font-mono text-gray-700">
                            {fmt(g.amounts?.[y] || 0)}
                          </td>
                        ))}
                        {Object.entries(g.deltas || {}).map(([dk, dv]: [string, any]) => (
                          <td key={dk} className="px-3 py-2.5 text-right">
                            <DeltaIndicator value={dv.percent} />
                          </td>
                        ))}
                        <td className="px-3 py-2.5 text-right">
                          {g.cagr !== null ? (
                            <span className={`text-xs font-bold ${g.cagr >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{pctFmt(g.cagr)}</span>
                          ) : <span className="text-xs text-gray-300">-</span>}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {g.driver_code ? (
                            <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded text-[10px] font-mono">{g.driver_code}</span>
                          ) : <span className="text-gray-300">-</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {yoyData.grand_totals && (
                    <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                      <tr>
                        <td className="px-4 py-2 font-bold text-gray-900 text-xs">TOTAL</td>
                        {yoyData.years_analyzed?.map((y: string) => (
                          <td key={y} className="px-3 py-2 text-right font-bold text-xs font-mono text-gray-900">{fmt(yoyData.grand_totals[y] || 0)}</td>
                        ))}
                        <td colSpan={Object.keys(yoyData.groups?.[0]?.deltas || {}).length + 2} />
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          )}

          {/* TAB: Plan vs Historical */}
          {activeTab === 'plan-delta' && planDelta && (
            <div className="space-y-4">
              {/* Waterfall-style decomposition */}
              <div className="bg-white rounded-xl border p-5">
                <h3 className="font-semibold text-gray-800 mb-4">Variance Decomposition: FY {fiscalYear - 1} → FY {fiscalYear} Plan</h3>
                <div className="flex items-end gap-2 h-32">
                  {/* Prior Year bar */}
                  <div className="flex flex-col items-center flex-1">
                    <div className="text-xs text-gray-500 mb-1">FY {fiscalYear - 1}</div>
                    <div className="w-full bg-gray-300 rounded-t h-28" />
                    <div className="text-xs font-bold mt-1">{fmt(gt.prior_year_actual)}</div>
                  </div>
                  {/* Organic Change */}
                  <div className="flex flex-col items-center flex-1">
                    <div className="text-xs text-gray-500 mb-1">Organic Δ</div>
                    <div className={`w-full rounded-t ${(gt.organic_change || 0) >= 0 ? 'bg-emerald-300' : 'bg-red-300'}`}
                      style={{ height: `${Math.max(Math.abs(gt.organic_change || 0) / Math.max(Math.abs(gt.prior_year_actual || 1), 1) * 112, 8)}px` }} />
                    <div className={`text-xs font-bold mt-1 ${(gt.organic_change || 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {(gt.organic_change || 0) >= 0 ? '+' : ''}{fmt(gt.organic_change || 0)}
                    </div>
                  </div>
                  {/* Driver Impact */}
                  <div className="flex flex-col items-center flex-1">
                    <div className="text-xs text-gray-500 mb-1">Driver Impact</div>
                    <div className={`w-full rounded-t ${(gt.driver_impact || 0) >= 0 ? 'bg-blue-300' : 'bg-amber-300'}`}
                      style={{ height: `${Math.max(Math.abs(gt.driver_impact || 0) / Math.max(Math.abs(gt.prior_year_actual || 1), 1) * 112, 8)}px` }} />
                    <div className={`text-xs font-bold mt-1 ${(gt.driver_impact || 0) >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>
                      {(gt.driver_impact || 0) >= 0 ? '+' : ''}{fmt(gt.driver_impact || 0)}
                    </div>
                  </div>
                  {/* = separator */}
                  <div className="flex flex-col items-center w-6">
                    <div className="text-lg text-gray-400 font-bold">=</div>
                  </div>
                  {/* Plan Adjusted */}
                  <div className="flex flex-col items-center flex-1">
                    <div className="text-xs text-indigo-600 font-medium mb-1">Plan FY {fiscalYear}</div>
                    <div className="w-full bg-indigo-400 rounded-t h-28" />
                    <div className="text-xs font-bold mt-1 text-indigo-700">{fmt(gt.plan_adjusted)}</div>
                  </div>
                </div>
              </div>

              {/* Group-level breakdown */}
              <div className="bg-white rounded-xl border overflow-hidden">
                <div className="px-5 py-3 border-b bg-gray-50">
                  <h3 className="font-semibold text-gray-800">Budget Group Variance Breakdown</h3>
                  <p className="text-xs text-gray-500">Prior year vs plan with organic change, driver impact, and proportion of total variance</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Budget Group</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600 cursor-pointer" onClick={() => toggleSort('prior_year_actual')}>FY {fiscalYear-1} <SortIcon field="prior_year_actual" /></th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Baseline</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600 cursor-pointer" onClick={() => toggleSort('plan_adjusted')}>Plan FY {fiscalYear} <SortIcon field="plan_adjusted" /></th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600 cursor-pointer" onClick={() => toggleSort('total_change')}>Total Δ <SortIcon field="total_change" /></th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Δ %</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Organic</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Driver</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600 cursor-pointer" onClick={() => toggleSort('proportion_pct')}>Proportion <SortIcon field="proportion_pct" /></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {sorted(planDelta.groups || []).map((g: any) => {
                        const maxVar = Math.max(...(planDelta.groups || []).map((x: any) => Math.abs(x.total_change)));
                        return (
                          <tr key={g.budgeting_group_id} className="hover:bg-gray-50">
                            <td className="px-4 py-2.5">
                              <div className="font-medium text-gray-800 text-xs leading-tight">{g.budgeting_group_name}</div>
                              {g.driver_code && <div className="text-[10px] text-indigo-500 font-mono">{g.driver_code} @{g.driver_rate}%</div>}
                            </td>
                            <td className="px-3 py-2.5 text-right text-xs font-mono text-gray-600">{fmt(g.prior_year_actual)}</td>
                            <td className="px-3 py-2.5 text-right text-xs font-mono text-gray-500">{fmt(g.plan_baseline)}</td>
                            <td className="px-3 py-2.5 text-right text-xs font-mono font-semibold text-gray-800">{fmt(g.plan_adjusted)}</td>
                            <td className={`px-3 py-2.5 text-right text-xs font-mono font-bold ${g.total_change >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                              {g.total_change >= 0 ? '+' : ''}{fmt(g.total_change)}
                            </td>
                            <td className="px-3 py-2.5 text-right"><DeltaIndicator value={g.total_change_pct} /></td>
                            <td className={`px-3 py-2.5 text-right text-xs font-mono ${g.organic_change >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                              {fmt(g.organic_change)}
                            </td>
                            <td className={`px-3 py-2.5 text-right text-xs font-mono ${g.driver_impact >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>
                              {fmt(g.driver_impact)}
                            </td>
                            <td className="px-3 py-2.5">
                              <div className="flex items-center gap-2">
                                <MiniBar value={g.total_change} max={maxVar} color={g.total_change >= 0 ? 'bg-emerald-400' : 'bg-red-400'} />
                                <span className="text-xs text-gray-500 w-12 text-right">{g.proportion_pct}%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot className="bg-gray-50 border-t-2 border-gray-200 font-bold text-xs">
                      <tr>
                        <td className="px-4 py-2 text-gray-900">TOTAL</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-900">{fmt(gt.prior_year_actual)}</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-700">{fmt(gt.plan_baseline)}</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-900">{fmt(gt.plan_adjusted)}</td>
                        <td className={`px-3 py-2 text-right font-mono ${(gt.total_variance||0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{fmt(gt.total_variance)}</td>
                        <td className="px-3 py-2 text-right"><DeltaIndicator value={gt.total_variance_pct || 0} /></td>
                        <td className={`px-3 py-2 text-right font-mono ${(gt.organic_change||0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{fmt(gt.organic_change)}</td>
                        <td className={`px-3 py-2 text-right font-mono ${(gt.driver_impact||0) >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>{fmt(gt.driver_impact)}</td>
                        <td className="px-3 py-2 text-right text-gray-500">100%</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB: Driver Contribution */}
          {activeTab === 'drivers' && planDelta && (
            <div className="space-y-4">
              <div className="bg-white rounded-xl border overflow-hidden">
                <div className="px-5 py-3 border-b bg-gray-50">
                  <h3 className="font-semibold text-gray-800">Driver Contribution to Plan Variance</h3>
                  <p className="text-xs text-gray-500">Aggregated by driver: how much each driver type explains the total change from prior year to plan</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Driver</th>
                        <th className="text-center px-3 py-2 font-medium text-gray-600">Type</th>
                        <th className="text-center px-3 py-2 font-medium text-gray-600">Groups</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Prior Total</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Plan Total</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Total Δ</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Δ %</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Organic</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Driver Effect</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-600">Proportion</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {planDelta.driver_breakdown?.map((d: any, idx: number) => {
                        const maxVar = Math.max(...(planDelta.driver_breakdown || []).map((x: any) => Math.abs(x.total_change)));
                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-3">
                              <span className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded text-xs font-mono font-medium">
                                {d.driver_code}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-center">
                              {d.driver_type ? (
                                <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{d.driver_type}</span>
                              ) : '-'}
                            </td>
                            <td className="px-3 py-3 text-center font-mono text-xs">{d.groups_count}</td>
                            <td className="px-3 py-3 text-right text-xs font-mono text-gray-600">{fmt(d.total_prior)}</td>
                            <td className="px-3 py-3 text-right text-xs font-mono font-semibold text-gray-800">{fmt(d.total_plan)}</td>
                            <td className={`px-3 py-3 text-right text-xs font-mono font-bold ${d.total_change >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                              {d.total_change >= 0 ? '+' : ''}{fmt(d.total_change)}
                            </td>
                            <td className="px-3 py-3 text-right"><DeltaIndicator value={d.total_change_pct} /></td>
                            <td className={`px-3 py-3 text-right text-xs font-mono ${d.organic_total >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                              {fmt(d.organic_total)}
                            </td>
                            <td className={`px-3 py-3 text-right text-xs font-mono ${d.driver_impact_total >= 0 ? 'text-blue-600' : 'text-amber-600'}`}>
                              {fmt(d.driver_impact_total)}
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex items-center gap-2">
                                <MiniBar value={d.total_change} max={maxVar} color={d.total_change >= 0 ? 'bg-indigo-400' : 'bg-red-400'} />
                                <span className="text-xs text-gray-500 w-12 text-right">{d.proportion_pct}%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Visual proportion */}
              <div className="bg-white rounded-xl border p-5">
                <h3 className="font-semibold text-gray-800 mb-3">Variance Proportion by Driver</h3>
                <div className="flex rounded-lg overflow-hidden h-8">
                  {planDelta.driver_breakdown?.filter((d: any) => d.proportion_pct !== 0).map((d: any, idx: number) => {
                    const colors = ['bg-indigo-500', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-rose-500', 'bg-teal-500', 'bg-orange-500'];
                    return (
                      <div key={idx} className={`${colors[idx % colors.length]} relative group`}
                        style={{ width: `${Math.max(Math.abs(d.proportion_pct), 2)}%` }}
                        title={`${d.driver_code}: ${d.proportion_pct}%`}>
                        <div className="absolute inset-0 flex items-center justify-center text-white text-[10px] font-bold opacity-90 truncate px-1">
                          {Math.abs(d.proportion_pct) >= 5 && d.driver_code}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="flex flex-wrap gap-3 mt-3">
                  {planDelta.driver_breakdown?.filter((d: any) => d.proportion_pct !== 0).map((d: any, idx: number) => {
                    const colors = ['bg-indigo-500', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-rose-500', 'bg-teal-500', 'bg-orange-500'];
                    return (
                      <span key={idx} className="flex items-center gap-1.5 text-xs text-gray-600">
                        <div className={`w-2.5 h-2.5 rounded-sm ${colors[idx % colors.length]}`} />
                        {d.driver_code} ({d.proportion_pct}%)
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default AnalysisDashboard;
