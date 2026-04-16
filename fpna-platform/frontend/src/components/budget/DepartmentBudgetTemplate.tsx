import React, { useState, useEffect, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Edit2,
  Save,
  X,
  TrendingUp,
  TrendingDown,
  Layers,
  Send,
  Check,
  Loader2,
  AlertCircle,
  Info,
  Lock,
  HelpCircle,
  Table2,
  LayoutGrid,
  Filter,
  User,
  Sparkles,
} from 'lucide-react';
import { budgetPlanningAPI, driversAPI } from '../../services/api';

interface MonthlyData {
  jan: number;
  feb: number;
  mar: number;
  apr: number;
  may: number;
  jun: number;
  jul: number;
  aug: number;
  sep: number;
  oct: number;
  nov: number;
  dec: number;
}

interface BudgetGroup {
  id: number;
  budgeting_group_id: number | null;
  fpna_product_key?: string | null;
  product_key?: string | null;
  product_label_en?: string | null;
  budgeting_group_name: string;
  baseline_total: number;
  adjusted_total: number;
  variance: number;
  variance_pct: number;
  driver_code: string | null;
  driver_name: string | null;
  driver_type: string | null;
  driver_rate: number | null;
  formula_description: string | null;
  is_locked: boolean;
  locked_by_cfo: boolean;
  cfo_lock_reason: string | null;
  monthly_baseline: MonthlyData;
  monthly_adjusted: MonthlyData;
  adjustment_notes: string | null;
  last_edited_at: string | null;
  last_edited_by: string | null;
}

function planGroupCacheKey(g: BudgetGroup): string {
  const pk = g.fpna_product_key || g.product_key;
  if (pk) return `p:${pk}`;
  if (g.budgeting_group_id != null) return `b:${g.budgeting_group_id}`;
  return `id:${g.id}`;
}

interface BSGroupLevel {
  bs_group: string;
  bs_group_name: string;
  groups: BudgetGroup[];
  total_baseline: number;
  total_adjusted: number;
}

interface BSClass {
  bs_flag: number;
  bs_class_name: string;
  bs_groups: BSGroupLevel[];
  total_baseline: number;
  total_adjusted: number;
}

interface DepartmentTemplate {
  plan_id: number;
  fiscal_year: number;
  department: {
    id: number;
    code: string;
    name: string;
    is_baseline_only: boolean;
  };
  status: string;
  version: number;
  total_baseline: number;
  total_adjusted: number;
  total_variance: number;
  total_variance_pct: number;
  hierarchy: BSClass[];
}

interface DriverOption {
  assignment_id: number;
  driver_id: number;
  driver_code: string;
  driver_name: string;
  driver_type: string | null;
  description: string | null;
  formula: string | null;
  formula_description: string | null;
  default_value: number | null;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  is_default: boolean;
}

interface Props {
  departmentId: number;
  fiscalYear: number;
  onStatusChange?: () => void;
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'] as const;
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const DRIVER_TYPE_COLORS: Record<string, string> = {
  yield_rate: 'bg-green-100 text-green-700',
  cost_rate: 'bg-red-100 text-red-700',
  growth_rate: 'bg-blue-100 text-blue-700',
  provision_rate: 'bg-amber-100 text-amber-700',
  inflation_rate: 'bg-purple-100 text-purple-700',
  plan_adjustment: 'bg-slate-100 text-slate-800',
  dwh_yoy: 'bg-teal-100 text-teal-800',
  custom: 'bg-gray-100 text-gray-700',
};

const DRIVER_TYPE_LABELS: Record<string, string> = {
  yield_rate: 'Yield Rate',
  cost_rate: 'Cost Rate',
  growth_rate: 'Growth Rate',
  provision_rate: 'Provision Rate',
  inflation_rate: 'Inflation Rate',
  fx_rate: 'FX Rate',
  headcount: 'Headcount',
  plan_adjustment: 'Plan Δ',
  dwh_yoy: 'DWH YoY',
  custom: 'Custom',
};

// FP&A formula descriptions shown in driver tooltip
const DRIVER_FORMULA_DESC: Record<string, string> = {
  growth_rate:
    'Projected Balance = Baseline × (1 + Rate%). ' +
    'Applied to balance-sheet items (loans, deposits, investments). ' +
    'Rate = expected YoY portfolio growth (e.g. 30%).',
  yield_rate:
    'Monthly Income = Avg Balance × Rate% ÷ 12. ' +
    'Applied to interest income P&L accounts. ' +
    'Rate = annual asset yield on earning assets.',
  cost_rate:
    'Monthly Expense = Avg Liability × Rate% ÷ 12. ' +
    'Applied to interest expense P&L accounts. ' +
    'Rate = annual funding cost rate on interest-bearing liabilities.',
  provision_rate:
    'Provision = Loan Balance × Rate%. ' +
    'Applied to credit-loss / impairment accounts. ' +
    'Rate = expected default / provision coverage ratio.',
  inflation_rate:
    'Adjusted = Baseline × (1 + Rate%). ' +
    'Applied to operating costs affected by price inflation. ' +
    'Rate = expected annual inflation for this cost category.',
  fx_rate:
    'FX conversion driver. ' +
    'Rate = target exchange rate for the planning period.',
  headcount:
    'Cost driven by headcount changes. ' +
    'Rate = % change in FTE (full-time equivalents).',
  custom:
    'Adjusted = Baseline × (1 + Rate%). ' +
    'Use for any other percentage-based assumption.',
};

const formatCurrency = (num: number): string => {
  if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(1)}T`;
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toFixed(0);
};

/** P&L monthly grid — matches API month_keys (baseline/adjusted field names). */
const PL_MONTH_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'] as const;
const PL_MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** KPI strip + table footer rows (keys match API `summary` / `summary_monthly.adjusted`). */
const PL_KPI_TABLE_FOOTERS: Array<{
  summaryKey: string;
  label: string;
  stickyBg: string;
  borderCls: string;
}> = [
  { summaryKey: 'net_interest_income', label: 'Net Interest Income (NII) — FY total', stickyBg: 'bg-emerald-50', borderCls: 'border-emerald-300' },
  { summaryKey: 'non_interest_income', label: 'Non-Interest Income — FY total', stickyBg: 'bg-sky-50', borderCls: 'border-sky-300' },
  { summaryKey: 'opex', label: 'Operating expenses (OPEX) — FY total', stickyBg: 'bg-orange-50', borderCls: 'border-orange-300' },
  { summaryKey: 'provisions', label: 'Provisions — FY total', stickyBg: 'bg-red-50', borderCls: 'border-red-200' },
  { summaryKey: 'net_income', label: 'Net Income — FY total', stickyBg: 'bg-indigo-50', borderCls: 'border-indigo-300' },
];

/** Mirrors backend `_kpi_signed_scalar` for rolled-up P&L buckets. */
function kpiSignedScalar(x: number): number {
  const v = Number(x) || 0;
  return v < 0 ? Math.abs(v) : v;
}

function bucketMonthSum(rows: any[], plFlag: number, field: 'monthly_baseline' | 'monthly_adjusted', mk: string): number {
  return rows
    .filter((r) => Number(r.p_l_flag) === plFlag)
    .reduce((s, r) => s + Number(r[field]?.[mk] ?? 0), 0);
}

/**
 * When `summary_monthly` is missing from the API, derive footer Jan–Dec from the same grid rows
 * (plan group × flag or by-flag rollup) using the same composition as `get_department_pl_data`.
 */
function buildSummaryMonthlyFromDisplayRows(rows: any[]): {
  baseline: Record<string, Record<string, number>>;
  adjusted: Record<string, Record<string, number>>;
} | null {
  if (!rows?.length) return null;
  const baseline: Record<string, Record<string, number>> = {};
  const adjusted: Record<string, Record<string, number>> = {};
  for (const k of ['net_interest_income', 'non_interest_income', 'opex', 'provisions', 'net_income']) {
    baseline[k] = {};
    adjusted[k] = {};
  }
  for (const mk of PL_MONTH_KEYS) {
    for (const [out, field] of [
      [baseline, 'monthly_baseline' as const],
      [adjusted, 'monthly_adjusted' as const],
    ] as const) {
      const i1 = kpiSignedScalar(bucketMonthSum(rows, 1, field, mk));
      const e2 = kpiSignedScalar(bucketMonthSum(rows, 2, field, mk));
      const nii = i1 - e2;
      const n4 = kpiSignedScalar(bucketMonthSum(rows, 4, field, mk));
      const n5 = kpiSignedScalar(bucketMonthSum(rows, 5, field, mk));
      const n7 = kpiSignedScalar(bucketMonthSum(rows, 7, field, mk));
      const n3 = kpiSignedScalar(bucketMonthSum(rows, 3, field, mk));
      const n8 = kpiSignedScalar(bucketMonthSum(rows, 8, field, mk));
      const ni = nii + n4 - n5 - n7 - n3 - n8;
      out.net_interest_income[mk] = nii;
      out.non_interest_income[mk] = n4;
      out.opex[mk] = n7;
      out.provisions[mk] = n3;
      out.net_income[mk] = ni;
    }
  }
  return { baseline, adjusted };
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800',
    submitted: 'bg-blue-100 text-blue-800',
    dept_approved: 'bg-yellow-100 text-yellow-800',
    cfo_approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    exported: 'bg-purple-100 text-purple-800',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status.toUpperCase().replace('_', ' ')}
    </span>
  );
};

const DriverTooltip: React.FC<{ driver: DriverOption }> = ({ driver }) => {
  const formulaDesc = driver.formula_description
    || (driver.driver_type ? DRIVER_FORMULA_DESC[driver.driver_type] : null);
  return (
    <div className="absolute z-50 w-80 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-2">
      <div className="font-semibold mb-1 text-sm">{driver.driver_name}</div>
      {driver.driver_type && (
        <div className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium mb-2 ${DRIVER_TYPE_COLORS[driver.driver_type] || 'bg-gray-700 text-gray-200'}`}>
          {DRIVER_TYPE_LABELS[driver.driver_type] || driver.driver_type}
        </div>
      )}
      {driver.description && <p className="text-gray-300 mb-2">{driver.description}</p>}
      {formulaDesc && (
        <div className="mb-2 p-2 bg-gray-800 rounded">
          <div className="text-gray-400 mb-1 font-medium">How it works:</div>
          <span className="text-green-300">{formulaDesc}</span>
        </div>
      )}
      <div className="flex flex-wrap gap-2 text-gray-400">
        {driver.default_value !== null && (
          <span className="bg-gray-800 px-1.5 py-0.5 rounded">
            Default: {driver.default_value}{driver.unit}
          </span>
        )}
        {driver.min_value !== null && (
          <span className="bg-gray-800 px-1.5 py-0.5 rounded">
            Min: {driver.min_value}{driver.unit}
          </span>
        )}
        {driver.max_value !== null && (
          <span className="bg-gray-800 px-1.5 py-0.5 rounded">
            Max: {driver.max_value}{driver.unit}
          </span>
        )}
      </div>
      <div className="absolute w-2 h-2 bg-gray-900 rotate-45 left-1/2 -translate-x-1/2 -bottom-1"></div>
    </div>
  );
};

const DepartmentBudgetTemplate: React.FC<Props> = ({ departmentId, fiscalYear, onStatusChange }) => {
  const [template, setTemplate] = useState<DepartmentTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Expansion state for 3 levels
  const [expandedClasses, setExpandedClasses] = useState<Set<number>>(new Set());
  const [expandedBSGroups, setExpandedBSGroups] = useState<Set<string>>(new Set());
  const [expandedBudgetGroups, setExpandedBudgetGroups] = useState<Set<number>>(new Set());
  
  // Editing state
  const [editingGroup, setEditingGroup] = useState<number | null>(null);
  const [editData, setEditData] = useState<{ driver_id: number | null; driver_rate: number | null; notes: string }>({ driver_id: null, driver_rate: null, notes: '' });
  const [saving, setSaving] = useState(false);
  
  // Driver options for the currently editing group
  const [driverOptions, setDriverOptions] = useState<DriverOption[]>([]);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [hoveredDriver, setHoveredDriver] = useState<number | null>(null);
  
  // Drill-down state
  const [drillDownGroup, setDrillDownGroup] = useState<BudgetGroup | null>(null);
  const [drillDownData, setDrillDownData] = useState<any>(null);
  const [drillDownLoading, setDrillDownLoading] = useState(false);

  // Inline Level 3 (COA account) drill-down state per budgeting group
  const [groupDetails, setGroupDetails] = useState<Record<number, any[]>>({});
  const [groupDetailsLoading, setGroupDetailsLoading] = useState<Set<number>>(new Set());
  const [groupDetailsError, setGroupDetailsError] = useState<Record<number, string | null>>({});

  // Top-level planning tab
  const [planTab, setPlanTab] = useState<'bs' | 'pl'>('bs');

  // P&L data
  const [plData, setPlData] = useState<any>(null);
  const [plLoading, setPlLoading] = useState(false);
  const [plError, setPlError] = useState<string | null>(null);
  // AI scenario overlay for P&L tab
  const [aiScenarios, setAiScenarios] = useState<any[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('');
  const [applyingHistoricYoy, setApplyingHistoricYoy] = useState(false);

  const plMonthlyDisplayRows = useMemo(() => {
    if (!plData) return [];
    const g = plData.pl_monthly_groups;
    if (Array.isArray(g) && g.length > 0) return g;
    return Array.isArray(plData.pl_monthly_by_flag) ? plData.pl_monthly_by_flag : [];
  }, [plData]);

  /** Footer month columns: API `summary_monthly` or same math from grid rows (never Σ/12 — that lied vs Σ Baseline). */
  const derivedSummaryMonthly = useMemo(
    () => buildSummaryMonthlyFromDisplayRows(plMonthlyDisplayRows),
    [plMonthlyDisplayRows],
  );

  // Data Entry Table view
  const [viewMode, setViewMode] = useState<'table' | 'hierarchy'>('table');
  const [sliceBsClass, setSliceBsClass] = useState<number | ''>('');
  const [sliceBsGroup, setSliceBsGroup] = useState<string>('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [dirtyGroupIds, setDirtyGroupIds] = useState<Set<number>>(new Set());
  const [editingCell, setEditingCell] = useState<{ groupId: number; field: 'driver' | 'rate' | 'comment' } | null>(null);
  const [inlineEdit, setInlineEdit] = useState<{ driver_id: number | null; driver_rate: number | null; notes: string }>({ driver_id: null, driver_rate: null, notes: '' });
  const [driverOptionsMap, setDriverOptionsMap] = useState<Record<string, DriverOption[]>>({});

  useEffect(() => {
    loadTemplate();
  }, [departmentId, fiscalYear]);

  const loadTemplate = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await budgetPlanningAPI.getDepartmentTemplate(departmentId, fiscalYear);
      setTemplate(data);
      // Expand all classes by default
      if (data?.hierarchy) {
        setExpandedClasses(new Set(data.hierarchy.map((c: BSClass) => c.bs_flag)));
        // Expand all BS groups by default
        const allBSGroups = new Set<string>();
        data.hierarchy.forEach((c: BSClass) => {
          c.bs_groups.forEach((bg: BSGroupLevel) => {
            allBSGroups.add(`${c.bs_flag}-${bg.bs_group}`);
          });
        });
        setExpandedBSGroups(allBSGroups);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load template');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyHistoricYoy = async () => {
    const ys = plData?.yoy_suggestions?.source_years;
    const hint =
      ys?.year_old != null && ys?.year_new != null
        ? `This will set each FP&A P&L product group to its historic YoY (${ys.year_old}→${ys.year_new}) on the bank baseline plan.`
        : 'This will set each FP&A P&L product group to its historic YoY on the bank baseline plan.';
    if (!window.confirm(`${hint} Current adjusted amounts on those groups will be overwritten. Continue?`)) return;
    try {
      setApplyingHistoricYoy(true);
      const res = await budgetPlanningAPI.applyPlHistoricYoy(fiscalYear);
      if (res.status === 'success') {
        await loadPLData(selectedScenario || undefined);
        await loadTemplate();
        onStatusChange?.();
      } else {
        window.alert((res as any).message || res.status || 'Could not apply historic YoY');
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || err.message || 'Request failed');
    } finally {
      setApplyingHistoricYoy(false);
    }
  };

  const loadPLData = async (scenario?: string) => {
    try {
      setPlLoading(true);
      setPlError(null);
      const data = await budgetPlanningAPI.getDepartmentPLData(departmentId, fiscalYear, scenario || undefined);
      setPlData(data);
    } catch (err: any) {
      setPlError(err.response?.data?.detail || err.message || 'Failed to load P&L data');
    } finally {
      setPlLoading(false);
    }
  };

  // Load available AI scenarios when switching to P&L tab
  const loadAiScenarios = async () => {
    try {
      const res = await fetch(`/api/v1/ai/projections?fiscal_year=${fiscalYear}`);
      if (res.ok) {
        const data = await res.json();
        // Deduplicate by scenario_name
        const seen = new Set<string>();
        const unique = data.filter((s: any) => {
          if (seen.has(s.scenario_name)) return false;
          seen.add(s.scenario_name);
          return true;
        });
        setAiScenarios(unique);
      }
    } catch { /* ignore */ }
  };

  // Reset P&L data when department changes
  useEffect(() => {
    setPlData(null);
    setPlError(null);
    setPlanTab('bs');
    setSelectedScenario('');
  }, [departmentId]);

  // Load P&L data when switching to P&L tab
  useEffect(() => {
    if (planTab === 'pl' && !plData && !plLoading) {
      loadPLData(selectedScenario || undefined);
      loadAiScenarios();
    }
  }, [planTab, departmentId]);

  // Reload P&L data when scenario or fiscal year changes (so API additions e.g. yoy_suggestions appear)
  useEffect(() => {
    if (planTab === 'pl') {
      loadPLData(selectedScenario || undefined);
    }
  }, [selectedScenario, fiscalYear]);

  const toggleClass = (bsFlag: number) => {
    const newExpanded = new Set(expandedClasses);
    if (newExpanded.has(bsFlag)) {
      newExpanded.delete(bsFlag);
    } else {
      newExpanded.add(bsFlag);
    }
    setExpandedClasses(newExpanded);
  };

  const toggleBSGroup = (bsFlag: number, bsGroup: string) => {
    const key = `${bsFlag}-${bsGroup}`;
    const newExpanded = new Set(expandedBSGroups);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedBSGroups(newExpanded);
  };

  const toggleBudgetGroup = (groupId: number) => {
    const newExpanded = new Set(expandedBudgetGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
      setExpandedBudgetGroups(newExpanded);
    } else {
      newExpanded.add(groupId);
      setExpandedBudgetGroups(newExpanded);
      // When expanding a budgeting group, load its COA account details for inline Level 3 view
      loadGroupDetailsInline(groupId);
    }
  };

  const loadDriversForGroup = async (group: BudgetGroup) => {
    try {
      setLoadingDrivers(true);
      const pk = group.fpna_product_key || group.product_key;
      let response;
      if (pk) {
        response = await driversAPI.getDriversForProduct(pk);
      } else if (group.budgeting_group_id != null) {
        response = await driversAPI.getDriversForGroup(group.budgeting_group_id);
      } else {
        setDriverOptions([]);
        return;
      }
      setDriverOptions(response.drivers || []);
    } catch (err) {
      console.error('Failed to load drivers:', err);
      setDriverOptions([]);
    } finally {
      setLoadingDrivers(false);
    }
  };

  const handleEditGroup = async (group: BudgetGroup) => {
    setEditingGroup(group.id);
    setEditData({
      driver_id: null,
      driver_rate: group.driver_rate,
      notes: group.adjustment_notes || '',
    });
    await loadDriversForGroup(group);
  };

  const handleDriverSelect = (driverId: number) => {
    const driver = driverOptions.find(d => d.driver_id === driverId);
    setEditData({
      ...editData,
      driver_id: driverId,
      driver_rate: driver?.default_value || editData.driver_rate,
    });
  };

  const handleSaveGroup = async (groupId: number) => {
    try {
      setSaving(true);
      const selectedDriver = driverOptions.find(d => d.driver_id === editData.driver_id);
      await budgetPlanningAPI.updateGroupAdjustment(departmentId, groupId, {
        driver_code: selectedDriver?.driver_code,
        driver_name: selectedDriver?.driver_name,
        driver_rate: editData.driver_rate || undefined,
        notes: editData.notes || undefined,
      });
      await loadTemplate();
      setEditingGroup(null);
      setDriverOptions([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingGroup(null);
    setEditData({ driver_id: null, driver_rate: null, notes: '' });
    setDriverOptions([]);
  };

  const handleDrillDown = async (group: BudgetGroup) => {
    setDrillDownGroup(group);
    setDrillDownLoading(true);
    try {
      const data = await budgetPlanningAPI.getGroupDetails(departmentId, group.id);
      setDrillDownData(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load details');
    } finally {
      setDrillDownLoading(false);
    }
  };

  const loadGroupDetailsInline = async (groupId: number) => {
    // Avoid refetching if we already have details or a request in-flight
    if (groupDetails[groupId] || groupDetailsLoading.has(groupId)) {
      return;
    }
    setGroupDetailsLoading((prev) => {
      const next = new Set(prev);
      next.add(groupId);
      return next;
    });
    try {
      const data = await budgetPlanningAPI.getGroupDetails(departmentId, groupId);
      setGroupDetails((prev) => ({
        ...prev,
        [groupId]: data?.details || [],
      }));
      setGroupDetailsError((prev) => ({
        ...prev,
        [groupId]: null,
      }));
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to load account details';
      setGroupDetailsError((prev) => ({
        ...prev,
        [groupId]: message,
      }));
    } finally {
      setGroupDetailsLoading((prev) => {
        const next = new Set(prev);
        next.delete(groupId);
        return next;
      });
    }
  };

  const handleSubmit = async () => {
    try {
      setSaving(true);
      await budgetPlanningAPI.submitPlan(departmentId, fiscalYear);
      await loadTemplate();
      onStatusChange?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit plan');
    } finally {
      setSaving(false);
    }
  };

  const handleApproveDept = async () => {
    try {
      setSaving(true);
      await budgetPlanningAPI.approvePlanDept(departmentId, fiscalYear);
      await loadTemplate();
      onStatusChange?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve plan');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2 text-red-700">
        <AlertCircle className="w-5 h-5" />
        {error}
        <button onClick={() => setError(null)} className="ml-auto p-1 hover:bg-red-100 rounded">
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  if (!template) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-2 text-blue-700">
        <Info className="w-5 h-5" />
        No budget plan found for this department and fiscal year.
      </div>
    );
  }

  const canEdit = template.status === 'draft' || template.status === 'rejected';
  const canSubmit = template.status === 'draft' || template.status === 'rejected';
  const canApproveDept = template.status === 'submitted';
  const isSubmittedOrApproved = ['submitted', 'dept_approved', 'cfo_approved', 'exported'].includes(template.status);

  // Flatten hierarchy for table view and slice
  type FlatRow = { group: BudgetGroup; bs_class_name: string; bs_group: string; bs_group_name: string; bs_flag: number };
  const flatRows: FlatRow[] = [];
  template.hierarchy.forEach((bsClass) => {
    bsClass.bs_groups.forEach((bsGroup) => {
      bsGroup.groups.forEach((group) => {
        flatRows.push({
          group,
          bs_class_name: bsClass.bs_class_name,
          bs_group: bsGroup.bs_group,
          bs_group_name: bsGroup.bs_group_name,
          bs_flag: bsClass.bs_flag,
        });
      });
    });
  });

  const filteredRows = flatRows.filter((r) => {
    if (sliceBsClass !== '' && r.bs_flag !== sliceBsClass) return false;
    if (sliceBsGroup && r.bs_group !== sliceBsGroup) return false;
    return true;
  });

  // Group rows by budgeting_group_name for drill-down
  type GroupedRow = { name: string; rows: FlatRow[]; totalBaseline: number; totalAdjusted: number };
  const groupedRows: GroupedRow[] = [];
  const groupMap = new Map<string, FlatRow[]>();
  for (const r of filteredRows) {
    const key = r.group.budgeting_group_name;
    if (!groupMap.has(key)) groupMap.set(key, []);
    groupMap.get(key)!.push(r);
  }
  for (const [name, rows] of groupMap) {
    groupedRows.push({
      name,
      rows,
      totalBaseline: rows.reduce((s, r) => s + (r.group.baseline_total || 0), 0),
      totalAdjusted: rows.reduce((s, r) => s + (r.group.adjusted_total || 0), 0),
    });
  }
  const toggleGroupExpand = (name: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  const uniqueBsClasses = Array.from(new Set(template.hierarchy.map((c) => c.bs_flag)));
  const uniqueBsGroups = sliceBsClass !== ''
    ? template.hierarchy.find((c) => c.bs_flag === sliceBsClass)?.bs_groups.map((g) => g.bs_group) || []
    : Array.from(new Set(flatRows.map((r) => r.bs_group)));

  const loadDriversForGroupCached = async (group: BudgetGroup): Promise<DriverOption[]> => {
    const ck = planGroupCacheKey(group);
    if (driverOptionsMap[ck]) return driverOptionsMap[ck];
    try {
      const pk = group.fpna_product_key || group.product_key;
      const response = pk
        ? await driversAPI.getDriversForProduct(pk)
        : group.budgeting_group_id != null
          ? await driversAPI.getDriversForGroup(group.budgeting_group_id)
          : { drivers: [] };
      const drivers = (response.drivers || []) as DriverOption[];
      setDriverOptionsMap((prev) => ({ ...prev, [ck]: drivers }));
      return drivers;
    } catch {
      return [];
    }
  };

  const handleCellSave = async (groupId: number) => {
    const row = flatRows.find((r) => r.group.id === groupId);
    const group = row?.group;
    if (!group || saving) return;
    const opts = driverOptionsMap[planGroupCacheKey(group)] || [];
    const selectedDriver = opts.find((d) => d.driver_id === inlineEdit.driver_id);
    try {
      setSaving(true);
      await budgetPlanningAPI.updateGroupAdjustment(departmentId, groupId, {
        driver_code: selectedDriver?.driver_code ?? group.driver_code ?? undefined,
        driver_name: selectedDriver?.driver_name ?? group.driver_name ?? undefined,
        driver_rate: inlineEdit.driver_rate ?? undefined,
        notes: inlineEdit.notes || undefined,
      });
      setDirtyGroupIds((prev) => {
        const next = new Set(prev);
        next.delete(groupId);
        return next;
      });
      setEditingCell(null);
      await loadTemplate();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleCellEdit = async (groupId: number, field: 'driver' | 'rate' | 'comment', group: BudgetGroup) => {
    setEditingCell({ groupId, field });
    const opts: DriverOption[] = field === 'driver' ? await loadDriversForGroupCached(group) : [];
    const matchId = opts.find((d) => d.driver_code === group.driver_code || d.driver_name === group.driver_name)?.driver_id ?? null;
    setInlineEdit({
      driver_id: matchId,
      driver_rate: group.driver_rate,
      notes: group.adjustment_notes || '',
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent, groupId: number, field: string) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCellSave(groupId);
    }
    if (e.key === 'Tab' && !e.shiftKey) {
      // Let browser handle tab to next focusable
    }
  };

  const calcVariancePct = (baseline: number, adjusted: number): number => {
    if (baseline === 0) return 0;
    return ((adjusted - baseline) / Math.abs(baseline)) * 100;
  };

  const renderDrillDownContent = () => {
    if (drillDownLoading) {
      return (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      );
    }

    const hasDriver = drillDownGroup?.driver_code;

    if (drillDownData?.details) {
      return (
        <div className="space-y-2">
          {hasDriver && drillDownGroup && (
            <div className="flex items-center gap-3 px-3 py-2 bg-blue-50 rounded-lg border border-blue-200 text-xs">
              <span className="font-medium text-blue-700">Applied driver:</span>
              <span className="text-blue-900">{drillDownGroup.driver_name}</span>
              {drillDownGroup.driver_type && (
                <span className={`px-1.5 py-0.5 rounded font-semibold ${DRIVER_TYPE_COLORS[drillDownGroup.driver_type] || 'bg-gray-100 text-gray-700'}`}>
                  {DRIVER_TYPE_LABELS[drillDownGroup.driver_type] || drillDownGroup.driver_type}
                </span>
              )}
              {drillDownGroup.driver_rate != null && (
                <span className="font-mono text-blue-800">{drillDownGroup.driver_rate}%</span>
              )}
              {drillDownGroup.formula_description && (
                <span className="text-blue-600 italic">{drillDownGroup.formula_description}</span>
              )}
            </div>
          )}

          {hasDriver && drillDownGroup && (
            <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-lg border p-3">
              <div className="text-xs font-semibold text-gray-600 mb-2">Monthly Baseline vs Adjusted</div>
              <div className="grid grid-cols-12 gap-1">
                {MONTHS.map((m, idx) => {
                  const b = drillDownGroup.monthly_baseline?.[m] || 0;
                  const a = drillDownGroup.monthly_adjusted?.[m] || 0;
                  const diff = a - b;
                  const pct = b !== 0 ? ((diff / Math.abs(b)) * 100).toFixed(1) : '0.0';
                  return (
                    <div key={m} className="text-center">
                      <div className="text-[10px] font-medium text-gray-500 mb-1">{MONTH_LABELS[idx]}</div>
                      <div className="text-[10px] font-mono text-gray-500">{formatCurrency(b)}</div>
                      <div className="text-[10px] font-mono text-blue-700 font-medium">{formatCurrency(a)}</div>
                      <div className={`text-[10px] font-mono font-semibold ${diff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {diff >= 0 ? '+' : ''}{pct}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <table className="w-full text-sm">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">COA Code</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Account Name</th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">Total</th>
                {MONTH_LABELS.map((m) => (
                  <th key={m} className="px-2 py-2 text-right font-medium text-gray-600 text-xs">
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {drillDownData.details.map((detail: any) => (
                <tr key={detail.coa_code} className="border-t hover:bg-blue-50/30">
                  <td className="px-3 py-2 font-mono text-blue-600">{detail.coa_code}</td>
                  <td className="px-3 py-2 truncate max-w-[200px]" title={detail.coa_name}>
                    {detail.coa_name}
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-medium">
                    {formatCurrency(detail.baseline_total)}
                  </td>
                  {MONTHS.map((m) => (
                    <td key={m} className="px-2 py-2 text-right font-mono text-xs text-gray-600">
                      {formatCurrency(detail.monthly_baseline?.[m] || 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return (
      <div className="text-center py-8 text-gray-500">
        No account details available
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-lg border p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">{template.department.name}</h2>
            <p className="text-sm text-gray-500">
              Code: {template.department.code} | FY {template.fiscal_year} | Version {template.version}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <StatusBadge status={template.status} />
              {template.department.is_baseline_only && (
                <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                  Baseline Only
                </span>
              )}
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-xs text-gray-500">Baseline</div>
              <div className="text-lg font-semibold">{formatCurrency(template.total_baseline)}</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <div className="text-xs text-gray-500">Adjusted</div>
              <div className="text-lg font-semibold text-blue-700">{formatCurrency(template.total_adjusted)}</div>
            </div>
            <div className={`rounded-lg p-3 text-center ${template.total_variance >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="text-xs text-gray-500">Variance</div>
              <div className={`text-lg font-semibold ${template.total_variance >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                {template.total_variance >= 0 ? '+' : ''}{template.total_variance_pct.toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 mt-4 pt-4 border-t">
          {canSubmit && !template.department.is_baseline_only && (
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Submit for Approval
            </button>
          )}
          {canApproveDept && (
            <button
              onClick={handleApproveDept}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              Approve (Dept Head)
            </button>
          )}
        </div>
      </div>

      {/* BS / P&L Planning Tab Switcher */}
      <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-xl w-fit">
        <button
          onClick={() => setPlanTab('bs')}
          className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${planTab === 'bs' ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <Layers className="w-4 h-4 inline mr-1.5 -mt-0.5" />
          BS Planning
        </button>
        <button
          onClick={() => setPlanTab('pl')}
          className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${planTab === 'pl' ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <TrendingUp className="w-4 h-4 inline mr-1.5 -mt-0.5" />
          P&L Planning
        </button>
      </div>

      {/* ===================== BS PLANNING TAB ===================== */}
      {planTab === 'bs' && (<>

      {/* View toggle + Slice filters */}
      <div className="flex flex-wrap items-center gap-4 py-3 px-4 bg-gray-50 rounded-lg border">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">View:</span>
          <button
            onClick={() => setViewMode('table')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${viewMode === 'table' ? 'bg-primary-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-100'}`}
          >
            <Table2 className="w-4 h-4" />
            BS Data Entry
          </button>
          <button
            onClick={() => setViewMode('hierarchy')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${viewMode === 'hierarchy' ? 'bg-primary-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-100'}`}
          >
            <LayoutGrid className="w-4 h-4" />
            Hierarchy
          </button>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={sliceBsClass}
            onChange={(e) => {
              setSliceBsClass(e.target.value === '' ? '' : Number(e.target.value));
              setSliceBsGroup('');
            }}
            className="px-2 py-1.5 border border-gray-300 rounded text-sm"
          >
            <option value="">All BS Classes</option>
            {uniqueBsClasses.map((f) => {
              const c = template.hierarchy.find((x) => x.bs_flag === f);
              return (
                <option key={f} value={f}>{c?.bs_class_name ?? `Class ${f}`}</option>
              );
            })}
          </select>
          <select
            value={sliceBsGroup}
            onChange={(e) => setSliceBsGroup(e.target.value)}
            className="px-2 py-1.5 border border-gray-300 rounded text-sm"
          >
            <option value="">All BS Groups</option>
            {uniqueBsGroups.map((g) => {
              const label = template.hierarchy
                .flatMap((c) => c.bs_groups)
                .find((x) => x.bs_group === g);
              const text =
                g === 'UNASSIGNED'
                  ? `Unassigned – ${label?.bs_group_name || 'No BS group'}`
                  : label
                  ? `${g} - ${label.bs_group_name}`
                  : g;
              return (
                <option key={g} value={g}>{text}</option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Data Entry Table (Excel-like) */}
      {viewMode === 'table' && (
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 border-b border-gray-200">
                  <th className="text-left p-3 font-semibold text-gray-700">Group</th>
                  <th className="text-right p-3 font-semibold text-gray-700 w-28">Baseline</th>
                  <th className="text-left p-3 font-semibold text-gray-700 w-40">Driver</th>
                  <th className="text-right p-3 font-semibold text-gray-700 w-24">Adjust %</th>
                  <th className="text-right p-3 font-semibold text-gray-700 w-28">Adjusted</th>
                  <th className="text-left p-3 font-semibold text-gray-700 min-w-[180px]">Comment</th>
                  <th className="text-left p-3 font-semibold text-gray-700 w-32">Last updated by</th>
                  <th className="w-20" />
                </tr>
              </thead>
              <tbody>
                {groupedRows.map((grp) => {
                  const isMulti = grp.rows.length > 1;
                  const isExpanded = expandedGroups.has(grp.name);
                  const visibleRows = isMulti && !isExpanded ? [] : grp.rows;

                  return (
                    <React.Fragment key={grp.name}>
                      {/* Summary row for multi-child groups (always shown) or single-child header */}
                      {isMulti && (
                        <tr
                          className="border-b border-gray-200 bg-gray-50/70 cursor-pointer hover:bg-gray-100/70"
                          onClick={() => toggleGroupExpand(grp.name)}
                        >
                          <td className="p-2">
                            <div className="flex items-center gap-2">
                              {isExpanded
                                ? <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" />
                                : <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
                              }
                              <div>
                                <span className="font-semibold text-gray-900">{grp.name}</span>
                                <span className="ml-2 text-xs text-gray-400">({grp.rows.length} sub-groups)</span>
                              </div>
                            </div>
                          </td>
                          <td className="p-2 text-right font-mono font-semibold text-gray-800">{formatCurrency(grp.totalBaseline)}</td>
                          <td className="p-2 text-gray-400 text-xs" colSpan={2}>—</td>
                          <td className="p-2 text-right font-mono font-semibold text-blue-700">{formatCurrency(grp.totalAdjusted)}</td>
                          <td colSpan={3} />
                        </tr>
                      )}
                      {/* Detail rows */}
                      {(isMulti ? visibleRows : grp.rows).map(({ group, bs_class_name, bs_group_name }) => {
                  const isDirty = dirtyGroupIds.has(group.id);
                  const rowBg = isDirty
                    ? 'bg-amber-50'
                    : isSubmittedOrApproved
                    ? 'bg-emerald-50/50'
                    : '';
                  const opts = driverOptionsMap[planGroupCacheKey(group)] || [];
                  const isEditing = editingCell?.groupId === group.id;

                  return (
                    <tr
                      key={group.id}
                      className={`border-b border-gray-100 hover:bg-gray-50/80 ${rowBg}`}
                    >
                      <td className={`p-2 ${isMulti ? 'pl-8' : ''}`}>
                        <div className="font-medium text-gray-900">{isMulti ? bs_group_name : group.budgeting_group_name}</div>
                        <div className="text-xs text-gray-500">{bs_class_name} → {bs_group_name}</div>
                      </td>
                      <td className="p-2 text-right font-mono text-gray-700">{formatCurrency(group.baseline_total)}</td>
                      <td className="p-1">
                        {group.is_locked ? (
                          <span className="text-gray-400 text-xs">Locked</span>
                        ) : isEditing && editingCell?.field === 'driver' ? (
                          <select
                            autoFocus
                            value={inlineEdit.driver_id ?? ''}
                            onChange={(e) => {
                              const id = e.target.value ? parseInt(e.target.value, 10) : null;
                              const d = opts.find((x) => x.driver_id === id);
                              setInlineEdit((p) => ({ ...p, driver_id: id, driver_rate: d?.default_value ?? p.driver_rate }));
                              setDirtyGroupIds((p) => new Set(p).add(group.id));
                            }}
                            onBlur={() => handleCellSave(group.id)}
                            onKeyDown={(e) => handleKeyDown(e, group.id, 'driver')}
                            className="w-full px-2 py-1 border border-primary-300 rounded focus:ring-2 focus:ring-primary-500"
                          >
                            <option value="">—</option>
                            {opts.map((d) => (
                              <option key={d.driver_id} value={d.driver_id}>{d.driver_name}</option>
                            ))}
                          </select>
                        ) : canEdit ? (
                          <button
                            type="button"
                            onClick={() => handleCellEdit(group.id, 'driver', group)}
                            className="w-full text-left px-2 py-1 rounded border border-transparent hover:border-gray-300 hover:bg-white text-gray-700"
                          >
                            <div className="flex items-center gap-1.5">
                              <span>{group.driver_name || '—'}</span>
                              {group.driver_type && (
                                <span className={`px-1 py-0.5 rounded text-[10px] font-semibold ${DRIVER_TYPE_COLORS[group.driver_type] || 'bg-gray-100 text-gray-700'}`}>
                                  {DRIVER_TYPE_LABELS[group.driver_type] || group.driver_type}
                                </span>
                              )}
                            </div>
                          </button>
                        ) : (
                          <div className="flex items-center gap-1.5 text-gray-600">
                            <span>{group.driver_name || '—'}</span>
                            {group.driver_type && (
                              <span className={`px-1 py-0.5 rounded text-[10px] font-semibold ${DRIVER_TYPE_COLORS[group.driver_type] || 'bg-gray-100 text-gray-700'}`}>
                                {DRIVER_TYPE_LABELS[group.driver_type] || group.driver_type}
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="p-1">
                        {group.is_locked ? (
                          <span className="text-gray-400">—</span>
                        ) : isEditing && editingCell?.field === 'rate' ? (
                          <input
                            type="number"
                            step="0.1"
                            autoFocus
                            value={inlineEdit.driver_rate ?? ''}
                            onChange={(e) => {
                              const v = e.target.value === '' ? null : parseFloat(e.target.value);
                              setInlineEdit((p) => ({ ...p, driver_rate: v }));
                              setDirtyGroupIds((p) => new Set(p).add(group.id));
                            }}
                            onBlur={() => handleCellSave(group.id)}
                            onKeyDown={(e) => handleKeyDown(e, group.id, 'rate')}
                            className="w-full px-2 py-1 border border-primary-300 rounded text-right focus:ring-2 focus:ring-primary-500"
                          />
                        ) : canEdit ? (
                          <button
                            type="button"
                            onClick={() => handleCellEdit(group.id, 'rate', group)}
                            className="w-full text-right px-2 py-1 rounded border border-transparent hover:border-gray-300 hover:bg-white font-mono"
                            title={group.formula_description || undefined}
                          >
                            {group.driver_rate != null ? `${group.driver_rate}%` : '—'}
                          </button>
                        ) : (
                          <span className="font-mono text-gray-600" title={group.formula_description || undefined}>
                            {group.driver_rate != null ? `${group.driver_rate}%` : '—'}
                          </span>
                        )}
                      </td>
                      <td className="p-2 text-right font-mono font-medium text-blue-700">{formatCurrency(group.adjusted_total)}</td>
                      <td className="p-1">
                        {group.is_locked ? (
                          <span className="text-gray-400 text-xs">—</span>
                        ) : isEditing && editingCell?.field === 'comment' ? (
                          <input
                            type="text"
                            autoFocus
                            value={inlineEdit.notes}
                            onChange={(e) => {
                              setInlineEdit((p) => ({ ...p, notes: e.target.value }));
                              setDirtyGroupIds((p) => new Set(p).add(group.id));
                            }}
                            onBlur={() => handleCellSave(group.id)}
                            onKeyDown={(e) => handleKeyDown(e, group.id, 'comment')}
                            placeholder="Why we adjust baseline..."
                            className="w-full px-2 py-1 border border-primary-300 rounded focus:ring-2 focus:ring-primary-500"
                          />
                        ) : canEdit ? (
                          <button
                            type="button"
                            onClick={() => handleCellEdit(group.id, 'comment', group)}
                            className="w-full text-left px-2 py-1 rounded border border-transparent hover:border-gray-300 hover:bg-white text-gray-600 truncate max-w-[200px]"
                            title={group.adjustment_notes || 'Add comment...'}
                          >
                            {group.adjustment_notes ? group.adjustment_notes : <span className="text-gray-400">Add comment...</span>}
                          </button>
                        ) : (
                          <span className="text-gray-600 truncate max-w-[200px] block" title={group.adjustment_notes || ''}>
                            {group.adjustment_notes || '—'}
                          </span>
                        )}
                      </td>
                      <td className="p-2 text-gray-500 text-xs">
                        {group.last_edited_by ? (
                          <span className="flex items-center gap-1" title={group.last_edited_at || ''}>
                            <User className="w-3.5 h-3.5" />
                            {group.last_edited_by}
                            {group.last_edited_at && (
                              <span className="text-gray-400">({new Date(group.last_edited_at).toLocaleDateString()})</span>
                            )}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="p-1">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleDrillDown(group)}
                            className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"
                            title="Drill-down: monthly / accounts"
                          >
                            <Layers className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                      </tr>
                    );
                  })}
                </React.Fragment>
                );
              })}
              </tbody>
            </table>
          </div>
          {filteredRows.length === 0 && (
            <div className="text-center py-8 text-gray-500">No groups match the selected filters.</div>
          )}
          <div className="px-4 py-2 bg-gray-50 border-t text-xs text-gray-500 flex items-center gap-4">
            <span className={isSubmittedOrApproved ? 'text-emerald-600' : ''}>
              {isSubmittedOrApproved ? 'Submitted / approved' : 'Draft — save each row (Enter or blur). Orange = unsaved.'}
            </span>
            {dirtyGroupIds.size > 0 && (
              <span className="text-amber-600 font-medium">{dirtyGroupIds.size} unsaved row(s)</span>
            )}
          </div>
        </div>
      )}

      {/* Hierarchy View (3 visible levels: BS Class → Budgeting Group → COA details) */}
      {viewMode === 'hierarchy' && (
        <div className="space-y-4">
          {template.hierarchy.map((bsClass) => (
            <div key={bsClass.bs_flag} className="bg-white rounded-lg border overflow-hidden">
              {/* Level 1: BS Class Header */}
              <button
                onClick={() => toggleClass(bsClass.bs_flag)}
                className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-gray-100 to-gray-50 hover:from-gray-200 hover:to-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {expandedClasses.has(bsClass.bs_flag) ? (
                    <ChevronDown className="w-5 h-5 text-gray-600" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-600" />
                  )}
                  <span className="font-bold text-gray-900 text-lg">{bsClass.bs_class_name}</span>
                  <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">Level 1</span>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  <span className="text-gray-500">
                    Baseline:{' '}
                    <span className="font-semibold text-gray-900">
                      {formatCurrency(bsClass.total_baseline)}
                    </span>
                  </span>
                  <span className="text-gray-500">
                    Adjusted:{' '}
                    <span className="font-semibold text-blue-700">
                      {formatCurrency(bsClass.total_adjusted)}
                    </span>
                  </span>
                  <span
                    className={`font-semibold ${
                      calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted) >= 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}
                  >
                    {calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted) >= 0 ? '+' : ''}
                    {calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted).toFixed(1)}%
                  </span>
                </div>
              </button>

              {/* Level 2: Budgeting Groups (flattened – no BS group header) */}
              {expandedClasses.has(bsClass.bs_flag) && (
                <div className="border-t bg-white">
                  {bsClass.bs_groups.flatMap((bsGroup) =>
                    bsGroup.groups.map((group) => (
                      <div key={group.id} className="border-b last:border-b-0">
                        <div className="flex items-center justify-between p-3 pl-10 hover:bg-blue-50/30 transition-colors">
                          <div className="flex items-center gap-3 flex-1">
                            <button
                              onClick={() => toggleBudgetGroup(group.id)}
                              className="p-0.5 hover:bg-gray-200 rounded"
                            >
                              {expandedBudgetGroups.has(group.id) ? (
                                <ChevronDown className="w-4 h-4 text-gray-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              )}
                            </button>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-700">
                                {group.budgeting_group_name}
                              </span>
                              <span className="text-xs text-blue-500 bg-blue-100 px-1.5 py-0.5 rounded">
                                Level 2
                              </span>
                              {group.is_locked && (
                                <span
                                  className="flex items-center gap-1 px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded"
                                  title={group.cfo_lock_reason || 'Locked'}
                                >
                                  <Lock className="w-3 h-3" />
                                  {group.locked_by_cfo ? 'CFO Locked' : 'Locked'}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <div className="text-xs text-gray-400">Baseline</div>
                              <div className="font-mono text-gray-600">
                                {formatCurrency(group.baseline_total)}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-xs text-gray-400">Adjusted</div>
                              <div className="font-mono text-blue-600 font-medium">
                                {formatCurrency(group.adjusted_total)}
                              </div>
                            </div>
                            <div className="text-right w-16">
                              <div className="text-xs text-gray-400">Variance</div>
                              <div
                                className={`flex items-center justify-end gap-0.5 font-medium ${
                                  group.variance >= 0 ? 'text-green-600' : 'text-red-600'
                                }`}
                              >
                                {group.variance >= 0 ? (
                                  <TrendingUp className="w-3 h-3" />
                                ) : (
                                  <TrendingDown className="w-3 h-3" />
                                )}
                                <span>
                                  {group.variance >= 0 ? '+' : ''}
                                  {group.variance_pct.toFixed(1)}%
                                </span>
                              </div>
                            </div>

                            {/* Driver Display/Edit */}
                            <div className="w-40">
                              {editingGroup === group.id ? (
                                <div className="space-y-1">
                                  {loadingDrivers ? (
                                    <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                                  ) : (
                                    <>
                                      <select
                                        value={editData.driver_id || ''}
                                        onChange={(e) => handleDriverSelect(parseInt(e.target.value))}
                                        className="w-full px-2 py-1 text-xs border rounded"
                                      >
                                        <option value="">Select driver...</option>
                                        {driverOptions.map((d) => (
                                          <option key={d.driver_id} value={d.driver_id}>
                                            {d.driver_name} {d.is_default ? '(default)' : ''}
                                          </option>
                                        ))}
                                      </select>
                                      <input
                                        type="number"
                                        step="0.1"
                                        value={editData.driver_rate || ''}
                                        onChange={(e) =>
                                          setEditData({
                                            ...editData,
                                            driver_rate: parseFloat(e.target.value) || null,
                                          })
                                        }
                                        className="w-full px-2 py-1 text-xs border rounded"
                                        placeholder="Rate %"
                                      />
                                    </>
                                  )}
                                </div>
                              ) : group.driver_rate ? (
                                <div className="relative">
                                  <div
                                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium cursor-help ${
                                      group.driver_rate >= 0
                                        ? 'bg-green-100 text-green-700'
                                        : 'bg-red-100 text-red-700'
                                    }`}
                                    onMouseEnter={() => setHoveredDriver(group.id)}
                                    onMouseLeave={() => setHoveredDriver(null)}
                                  >
                                    <span>{group.driver_name || group.driver_code}</span>
                                    <span>
                                      {group.driver_rate > 0 ? '+' : ''}
                                      {group.driver_rate}%
                                    </span>
                                    <HelpCircle className="w-3 h-3 opacity-50" />
                                  </div>
                                  {hoveredDriver === group.id && group.driver_name && (
                                    <div className="absolute z-50 w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-1">
                                      <div className="font-semibold">{group.driver_name}</div>
                                      <div className="text-gray-300">
                                        Rate: {group.driver_rate}%
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <span className="text-gray-400 text-xs">No driver</span>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-1 w-20 justify-end">
                              {editingGroup === group.id ? (
                                <>
                                  <button
                                    onClick={() => handleSaveGroup(group.id)}
                                    disabled={saving}
                                    className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                                    title="Save"
                                  >
                                    {saving ? (
                                      <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                      <Save className="w-4 h-4" />
                                    )}
                                  </button>
                                  <button
                                    onClick={handleCancelEdit}
                                    className="p-1.5 text-gray-600 hover:bg-gray-100 rounded"
                                    title="Cancel"
                                  >
                                    <X className="w-4 h-4" />
                                  </button>
                                </>
                              ) : (
                                <>
                                  {canEdit && !group.is_locked && (
                                    <button
                                      onClick={() => handleEditGroup(group)}
                                      className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"
                                      title="Edit Driver"
                                    >
                                      <Edit2 className="w-4 h-4" />
                                    </button>
                                  )}
                                  <button
                                    onClick={() => handleDrillDown(group)}
                                    className="p-1.5 text-gray-600 hover:bg-gray-100 rounded"
                                    title="View Accounts (Level 3)"
                                  >
                                    <Layers className="w-4 h-4" />
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Level 3: COA Accounts (Inline Expansion) */}
                        {expandedBudgetGroups.has(group.id) && (
                          <div className="bg-gray-50 border-t pl-20 pr-4 py-2 space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="text-xs text-gray-500 flex items-center gap-1">
                                <span className="bg-gray-200 px-1.5 py-0.5 rounded">Level 3</span>
                                COA Accounts under this budgeting group
                              </div>
                              <button
                                type="button"
                                onClick={() => loadGroupDetailsInline(group.id)}
                                className="text-[11px] text-blue-600 hover:text-blue-800 hover:underline disabled:text-gray-400"
                                disabled={groupDetailsLoading.has(group.id)}
                              >
                                Refresh accounts
                              </button>
                            </div>

                            {groupDetailsLoading.has(group.id) && (
                              <div className="flex items-center gap-2 text-xs text-gray-500 py-1">
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
                                <span>Loading COA accounts…</span>
                              </div>
                            )}

                            {groupDetailsError[group.id] && !groupDetailsLoading.has(group.id) && (
                              <div className="text-xs text-red-600 py-1">
                                {groupDetailsError[group.id]}
                              </div>
                            )}

                            {groupDetails[group.id] && groupDetails[group.id].length > 0 && !groupDetailsLoading.has(group.id) && (
                              <div className="max-h-56 overflow-auto rounded border border-gray-200 bg-white">
                                <table className="w-full text-xs">
                                  <thead className="bg-gray-100">
                                    <tr>
                                      <th className="px-2 py-1 text-left font-medium text-gray-600 w-24">COA</th>
                                      <th className="px-2 py-1 text-left font-medium text-gray-600">Account Name</th>
                                      <th className="px-2 py-1 text-right font-medium text-gray-600 w-28">Baseline</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {groupDetails[group.id].map((detail: any) => (
                                      <tr key={detail.coa_code} className="border-t hover:bg-blue-50/40">
                                        <td className="px-2 py-1 font-mono text-blue-700">{detail.coa_code}</td>
                                        <td className="px-2 py-1 truncate max-w-xs" title={detail.coa_name}>
                                          {detail.coa_name}
                                        </td>
                                        <td className="px-2 py-1 text-right font-mono text-gray-700">
                                          {formatCurrency(detail.baseline_total)}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}

                            {!groupDetails[group.id] &&
                              !groupDetailsLoading.has(group.id) &&
                              !groupDetailsError[group.id] && (
                                <div className="text-xs text-gray-400 italic">
                                  Expand to load COA accounts for this group.
                                </div>
                              )}

                            {groupDetails[group.id] &&
                              groupDetails[group.id].length === 0 &&
                              !groupDetailsLoading.has(group.id) &&
                              !groupDetailsError[group.id] && (
                                <div className="text-xs text-gray-400 italic">
                                  No COA accounts found for this budgeting group.
                                </div>
                              )}

                            <div className="text-[11px] text-gray-400 flex items-center gap-1 pt-1">
                              For full monthly breakdown by account, use the
                              <Layers className="w-3 h-3 inline" /> drill-down button on the group row (Level 4).
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      </>)}

      {/* ===================== P&L PLANNING TAB ===================== */}
      {planTab === 'pl' && (
        <div className="space-y-4">
          {plLoading && (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 text-primary-600 animate-spin" />
              <span className="ml-2 text-gray-500">Loading P&L data...</span>
            </div>
          )}
          {plError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              <AlertCircle className="w-4 h-4 inline mr-2" />
              {plError}
            </div>
          )}
          {plData && !plLoading && (
            <>
              {/* Bank-wide P&L note */}
              {plData.is_bank_wide && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                  <Info className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-amber-700">
                    <span className="font-medium">Bank-wide P&L View:</span> Income statement data is shown at the consolidated bank level.
                    Individual departments manage balance sheet items whose drivers affect these P&L accounts.
                  </div>
                </div>
              )}

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-700 space-y-2">
                <p>
                  <span className="font-medium text-slate-800">Adjusted &amp; variance</span> default to{' '}
                  <strong>DWH BaselineData YoY by p_l_flag</strong> (e.g. 2024→2025 for a FY2026 plan), so each P&L category can differ.
                  If many lines shared the same % before, they were scaled from <strong>one budget group ratio</strong>.{' '}
                  <span className="font-medium text-teal-800">Apply historic YoY</span> updates baseline plan groups. The table below is <strong>monthly by planning group</strong> (no COA drill-down).
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleApplyHistoricYoy}
                    disabled={applyingHistoricYoy}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 disabled:opacity-50"
                  >
                    {applyingHistoricYoy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
                    Apply historic YoY to baseline P&L plan (CFO)
                  </button>
                  <span className="text-xs text-slate-500">Sets each FP&A product (REV_INTEREST, OPEX, …) separately from BaselineData.</span>
                </div>
              </div>
              {/* AI Scenario selector */}
              {aiScenarios.length > 0 && (
                <div className="flex flex-col gap-2 bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-2.5">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Sparkles className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                    <span className="text-sm font-medium text-indigo-700">AI Scenario:</span>
                    <select
                      value={selectedScenario}
                      onChange={e => setSelectedScenario(e.target.value)}
                      className="text-sm border border-indigo-300 rounded-lg px-3 py-1.5 bg-white text-indigo-800 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                    >
                      <option value="">None (baseline only)</option>
                      {aiScenarios.map(s => (
                        <option key={s.scenario_name} value={s.scenario_name}>
                          {s.scenario_name.charAt(0).toUpperCase() + s.scenario_name.slice(1)} — {Math.round(s.confidence)}% confidence
                        </option>
                      ))}
                    </select>
                    {selectedScenario && plData?.has_ai_scenario && (
                      <span className="text-xs text-indigo-500">
                        {plData.scenario_name} scenario applied
                      </span>
                    )}
                  </div>
                  {plData?.ai_stale_warning && selectedScenario && (
                    <p className="text-xs text-amber-800 bg-amber-100/80 border border-amber-200 rounded px-2 py-1.5">
                      This saved AI run looks inconsistent with the current plan (e.g. very large % vs adjusted). Regenerate the projection from the AI Assistant — new runs use historic YoY anchoring.
                    </p>
                  )}
                </div>
              )}

              {plData?.yoy_suggestions?.warnings?.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900">
                  {plData.yoy_suggestions.warnings.join(' ')}
                </div>
              )}

              {/* P&L Summary Cards */}
              <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
                {[
                  { label: 'Net Interest Income', key: 'net_interest_income', color: 'emerald' },
                  { label: 'Non-Int Income', key: 'non_interest_income', color: 'blue' },
                  { label: 'OPEX', key: 'opex', color: 'orange' },
                  { label: 'Provisions', key: 'provisions', color: 'red' },
                  { label: 'Net Income', key: 'net_income', color: 'indigo' },
                ].map(({ label, key, color }) => {
                  const s = plData.summary?.[key];
                  const bl = s?.baseline || 0;
                  const adj = s?.adjusted || 0;
                  const pct = bl !== 0 ? ((adj - bl) / Math.abs(bl)) * 100 : 0;
                  return (
                    <div key={key} className="bg-white rounded-lg border p-3">
                      <div className="text-xs text-gray-500">{label}</div>
                      <div className="text-base font-bold mt-1">{formatCurrency(adj)}</div>
                      <div className={`text-xs mt-1 ${pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {pct >= 0 ? '+' : ''}{pct.toFixed(1)}% vs baseline
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* P&L — monthly by planning group (no COA drill-down) */}
              <div className="bg-white rounded-lg border overflow-hidden">
                <div className="px-3 py-2 border-b bg-slate-50 text-xs text-slate-600">
                  Rows = budget plan groups (no COA), or — if none — <strong>rolled up by P&amp;L category</strong> across all groups.{' '}
                  <strong>Jan–Dec</strong> follow <strong>DWH BaselineData</strong> month-shapes from FY{' '}
                  <strong>{plData.pl_seasonality?.reference_fiscal_year ?? fiscalYear - 1}</strong>
                  {plData.pl_seasonality?.accounts_with_history != null && (
                    <> ({plData.pl_seasonality.accounts_with_history} COAs with history)</>
                  )}
                  ; amounts are scaled to plan Σ so totals match. If history is missing, months split evenly.
                  <strong> Σ Baseline</strong> / <strong>Σ Adjusted</strong> = full-year totals.
                  {plData.has_ai_scenario && ' Σ AI = scenario year total (monthly AI summed).'}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse min-w-[1100px]">
                    <thead>
                      <tr className="bg-gray-100 border-b border-gray-200">
                        <th className="text-left p-2 font-semibold text-gray-700 sticky left-0 bg-gray-100 z-10 min-w-[8rem]">P&amp;L category</th>
                        <th className="text-left p-2 font-semibold text-gray-700 sticky left-[8rem] bg-gray-100 z-10 min-w-[9rem] border-r border-gray-200">Planning group</th>
                        {PL_MONTH_LABELS.map((lab) => (
                          <th key={lab} className="text-right p-1.5 font-semibold text-gray-600 whitespace-nowrap w-14">
                            {lab}
                          </th>
                        ))}
                        <th className="text-right p-2 font-semibold text-gray-700 border-l border-gray-200">Σ Baseline</th>
                        <th className="text-right p-2 font-semibold text-blue-700 border-l border-gray-200">Σ Adjusted</th>
                        {plData.has_ai_scenario && (
                          <th className="text-right p-2 font-semibold text-indigo-700 bg-indigo-50 border-l border-gray-200">Σ AI</th>
                        )}
                        <th className="text-right p-2 font-semibold text-gray-700 w-16">Var %</th>
                        <th className="text-left p-2 font-semibold text-gray-700 min-w-[7rem]">Driver</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plMonthlyDisplayRows.map((row: any) => (
                        <tr key={`${row.group_id ?? 'all'}-${row.p_l_flag}`} className="border-t border-gray-100 hover:bg-slate-50/80">
                          <td className="p-2 text-gray-800 font-medium sticky left-0 bg-white z-[1]">{row.p_l_category}</td>
                          <td className="p-2 text-gray-700 sticky left-[8rem] bg-white z-[1] border-r border-gray-100 max-w-[10rem] truncate" title={row.budgeting_group_name || 'Consolidated by P&L flag'}>
                            {row.budgeting_group_name || (row.group_id == null ? '— All groups' : `Group ${row.group_id}`)}
                          </td>
                          {PL_MONTH_KEYS.map((mk) => (
                            <td key={mk} className="p-1.5 text-right font-mono text-blue-800 whitespace-nowrap" title={`Baseline ${mk}: ${formatCurrency(Number(row.monthly_baseline?.[mk] ?? 0))}`}>
                              {formatCurrency(Number(row.monthly_adjusted?.[mk] ?? 0))}
                            </td>
                          ))}
                          <td className="p-2 text-right font-mono text-gray-700 border-l border-gray-100">{formatCurrency(row.annual_baseline)}</td>
                          <td className="p-2 text-right font-mono text-blue-700 border-l border-gray-100">{formatCurrency(row.annual_adjusted)}</td>
                          {plData.has_ai_scenario && (
                            <td className="p-2 text-right font-mono text-indigo-700 bg-indigo-50/40 border-l border-gray-100">
                              {formatCurrency(Number(row.annual_ai ?? 0))}
                            </td>
                          )}
                          <td className={`p-2 text-right font-mono font-medium ${row.variance_pct >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                            {row.variance_pct >= 0 ? '+' : ''}{Number(row.variance_pct).toFixed(1)}%
                          </td>
                          <td className="p-2 align-top">
                            {row.driver && (
                              <span
                                className={`inline-flex flex-col gap-0.5 px-1 py-0.5 rounded text-[10px] font-medium ${DRIVER_TYPE_COLORS[row.driver.type] || 'bg-gray-100 text-gray-700'}`}
                              >
                                <span>
                                  {DRIVER_TYPE_LABELS[row.driver.type] || row.driver.type}{' '}
                                  {row.driver.rate != null ? `${row.driver.rate}%` : ''}
                                </span>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                      {plMonthlyDisplayRows.length === 0 && (
                        <tr>
                          <td colSpan={20} className="p-6 text-center text-gray-500">
                            {plData.summary?.net_income != null &&
                            (plData.summary.net_income.baseline !== 0 || plData.summary.net_income.adjusted !== 0)
                              ? 'No detailed P&amp;L grid rows for this view; use the FY summary rows below. Restart the API after updating if month columns stay blank.'
                              : 'No P&amp;L planning lines for this year. Initialize baseline or check Baseline Reference plan.'}
                          </td>
                        </tr>
                      )}

                      {/* KPI summary rows — months from summary_monthly.adjusted when API provides it */}
                      {plData.summary &&
                        PL_KPI_TABLE_FOOTERS.map(({ summaryKey, label, stickyBg, borderCls }) => {
                          const s = plData.summary[summaryKey];
                          const bl = s?.baseline ?? 0;
                          const adj = s?.adjusted ?? 0;
                          const adjMo = (plData.summary_monthly?.adjusted?.[summaryKey] ??
                            derivedSummaryMonthly?.adjusted?.[summaryKey]) as Record<string, number> | undefined;
                          const blMo = (plData.summary_monthly?.baseline?.[summaryKey] ??
                            derivedSummaryMonthly?.baseline?.[summaryKey]) as Record<string, number> | undefined;
                          const aiKey =
                            summaryKey === 'net_interest_income'
                              ? 'net_interest_income'
                              : summaryKey === 'net_income'
                                ? 'net_income'
                                : null;
                          return (
                            <tr key={summaryKey} className={`${stickyBg} border-t-2 ${borderCls}`}>
                              <td className={`p-2 font-bold sticky left-0 z-[1] ${stickyBg}`} colSpan={2}>
                                {label}
                              </td>
                              {PL_MONTH_KEYS.map((mk) => {
                                const vAdj = adjMo && adjMo[mk] !== undefined && adjMo[mk] !== null ? Number(adjMo[mk]) : null;
                                return (
                                  <td
                                    key={mk}
                                    className="p-1.5 text-right font-mono text-[11px] font-bold whitespace-nowrap"
                                    title={
                                      blMo && blMo[mk] !== undefined
                                        ? `Baseline ${mk}: ${formatCurrency(Number(blMo[mk]))}`
                                        : undefined
                                    }
                                  >
                                    {vAdj != null ? formatCurrency(vAdj) : '—'}
                                  </td>
                                );
                              })}
                              <td className={`p-2 text-right font-bold font-mono text-gray-700 border-l border-gray-200 ${stickyBg}`}>
                                {formatCurrency(bl)}
                              </td>
                              <td className={`p-2 text-right font-bold font-mono border-l border-gray-200 ${stickyBg}`}>{formatCurrency(adj)}</td>
                              {plData.has_ai_scenario && (
                                <td className={`p-2 text-right font-bold font-mono border-l border-gray-200 ${stickyBg}`}>
                                  {aiKey ? formatCurrency(Number(plData.ai_summary?.[aiKey] ?? 0)) : '—'}
                                </td>
                              )}
                              <td className={`p-2 text-right font-bold font-mono ${stickyBg}`}>
                                {bl !== 0 ? `${(((adj - bl) / Math.abs(bl)) * 100).toFixed(1)}%` : '—'}
                              </td>
                              <td className={`p-2 ${stickyBg}`} />
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* AI Scenario note */}
              {!plData.has_ai_scenario && aiScenarios.length === 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-start gap-2">
                  <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-blue-700">
                    <span className="font-medium">AI Projections:</span> Use the AI Assistant to generate scenario projections.
                    AI-modeled figures will appear as an additional column once generated.
                  </div>
                </div>
              )}
              {plData.has_ai_scenario && plData.ai_summary && (
                <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-indigo-700">
                    <span className="font-medium">AI Scenario "{plData.scenario_name}" applied.</span>{' '}
                    AI-projected Net Income: <span className="font-bold font-mono">{formatCurrency(plData.ai_summary.net_income)}</span>
                    {' vs baseline '}
                    <span className="font-mono">{formatCurrency(plData.summary.net_income?.baseline)}</span>
                    {plData.summary.net_income?.baseline !== 0 && (
                      <span className={`ml-1 font-bold ${plData.ai_summary.net_income >= plData.summary.net_income?.baseline ? 'text-green-700' : 'text-red-700'}`}>
                        ({((plData.ai_summary.net_income - plData.summary.net_income?.baseline) / Math.abs(plData.summary.net_income?.baseline) * 100).toFixed(1)}%)
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Drill-Down Modal (Level 3 Details) */}
      {drillDownGroup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b bg-gray-50">
              <div>
                <h3 className="text-lg font-semibold">{drillDownGroup.budgeting_group_name}</h3>
                <p className="text-sm text-gray-500">Level 3: COA Account Details</p>
              </div>
              <button onClick={() => setDrillDownGroup(null)} className="p-1 hover:bg-gray-200 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-auto max-h-[60vh]">
              {renderDrillDownContent()}
            </div>
            <div className="flex justify-end p-4 border-t bg-gray-50">
              <button
                onClick={() => setDrillDownGroup(null)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DepartmentBudgetTemplate;
