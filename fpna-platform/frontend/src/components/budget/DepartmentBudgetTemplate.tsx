import React, { useState, useEffect } from 'react';
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
  budgeting_group_id: number;
  budgeting_group_name: string;
  baseline_total: number;
  adjusted_total: number;
  variance: number;
  variance_pct: number;
  driver_code: string | null;
  driver_name: string | null;
  driver_rate: number | null;
  is_locked: boolean;
  locked_by_cfo: boolean;
  cfo_lock_reason: string | null;
  monthly_baseline: MonthlyData;
  monthly_adjusted: MonthlyData;
  adjustment_notes: string | null;
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

const formatCurrency = (num: number): string => {
  if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(1)}T`;
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toFixed(0);
};

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
  return (
    <div className="absolute z-50 w-72 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-2">
      <div className="font-semibold mb-1">{driver.driver_name}</div>
      {driver.description && <p className="text-gray-300 mb-2">{driver.description}</p>}
      {driver.formula_description && (
        <div className="mb-2">
          <span className="text-gray-400">Formula: </span>
          <span className="text-green-300">{driver.formula_description}</span>
        </div>
      )}
      <div className="flex gap-3 text-gray-400">
        {driver.default_value !== null && <span>Default: {driver.default_value}{driver.unit}</span>}
        {driver.min_value !== null && <span>Min: {driver.min_value}{driver.unit}</span>}
        {driver.max_value !== null && <span>Max: {driver.max_value}{driver.unit}</span>}
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
    } else {
      newExpanded.add(groupId);
    }
    setExpandedBudgetGroups(newExpanded);
  };

  const loadDriversForGroup = async (budgetingGroupId: number) => {
    try {
      setLoadingDrivers(true);
      const response = await driversAPI.getDriversForGroup(budgetingGroupId);
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
    await loadDriversForGroup(group.budgeting_group_id);
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

  const calcVariancePct = (baseline: number, adjusted: number): number => {
    if (baseline === 0) return 0;
    return ((adjusted - baseline) / Math.abs(baseline)) * 100;
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

      {/* 4-Level Hierarchy */}
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
              <span className="text-gray-500">Baseline: <span className="font-semibold text-gray-900">{formatCurrency(bsClass.total_baseline)}</span></span>
              <span className="text-gray-500">Adjusted: <span className="font-semibold text-blue-700">{formatCurrency(bsClass.total_adjusted)}</span></span>
              <span className={`font-semibold ${calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted) >= 0 ? '+' : ''}
                {calcVariancePct(bsClass.total_baseline, bsClass.total_adjusted).toFixed(1)}%
              </span>
            </div>
          </button>

          {/* Level 2: BS Groups */}
          {expandedClasses.has(bsClass.bs_flag) && (
            <div className="border-t">
              {bsClass.bs_groups.map((bsGroup) => {
                const bsGroupKey = `${bsClass.bs_flag}-${bsGroup.bs_group}`;
                return (
                  <div key={bsGroupKey} className="border-b last:border-b-0">
                    {/* Level 2: BS Group Header */}
                    <button
                      onClick={() => toggleBSGroup(bsClass.bs_flag, bsGroup.bs_group)}
                      className="w-full flex items-center justify-between p-3 pl-8 bg-gray-50 hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        {expandedBSGroups.has(bsGroupKey) ? (
                          <ChevronDown className="w-4 h-4 text-gray-500" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-500" />
                        )}
                        <span className="font-semibold text-gray-800">{bsGroup.bs_group} - {bsGroup.bs_group_name}</span>
                        <span className="text-xs text-gray-400 bg-gray-200 px-1.5 py-0.5 rounded">Level 2</span>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-gray-500">{formatCurrency(bsGroup.total_baseline)}</span>
                        <span className="text-blue-600 font-medium">{formatCurrency(bsGroup.total_adjusted)}</span>
                        <span className={`font-medium ${calcVariancePct(bsGroup.total_baseline, bsGroup.total_adjusted) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {calcVariancePct(bsGroup.total_baseline, bsGroup.total_adjusted) >= 0 ? '+' : ''}
                          {calcVariancePct(bsGroup.total_baseline, bsGroup.total_adjusted).toFixed(1)}%
                        </span>
                      </div>
                    </button>

                    {/* Level 3: Budgeting Groups (Editable) */}
                    {expandedBSGroups.has(bsGroupKey) && (
                      <div className="bg-white">
                        {bsGroup.groups.map((group) => (
                          <div key={group.id} className="border-t">
                            {/* Level 3: Budgeting Group Row */}
                            <div className="flex items-center justify-between p-3 pl-14 hover:bg-blue-50/30 transition-colors">
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
                                  <span className="font-medium text-gray-700">{group.budgeting_group_name}</span>
                                  <span className="text-xs text-blue-500 bg-blue-100 px-1.5 py-0.5 rounded">Level 3</span>
                                  {group.is_locked && (
                                    <span className="flex items-center gap-1 px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded" title={group.cfo_lock_reason || 'Locked'}>
                                      <Lock className="w-3 h-3" />
                                      {group.locked_by_cfo ? 'CFO Locked' : 'Locked'}
                                    </span>
                                  )}
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-4">
                                <div className="text-right">
                                  <div className="text-xs text-gray-400">Baseline</div>
                                  <div className="font-mono text-gray-600">{formatCurrency(group.baseline_total)}</div>
                                </div>
                                <div className="text-right">
                                  <div className="text-xs text-gray-400">Adjusted</div>
                                  <div className="font-mono text-blue-600 font-medium">{formatCurrency(group.adjusted_total)}</div>
                                </div>
                                <div className="text-right w-16">
                                  <div className="text-xs text-gray-400">Variance</div>
                                  <div className={`flex items-center justify-end gap-0.5 font-medium ${group.variance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {group.variance >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                    <span>{group.variance >= 0 ? '+' : ''}{group.variance_pct.toFixed(1)}%</span>
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
                                            onChange={(e) => setEditData({ ...editData, driver_rate: parseFloat(e.target.value) || null })}
                                            className="w-full px-2 py-1 text-xs border rounded"
                                            placeholder="Rate %"
                                          />
                                        </>
                                      )}
                                    </div>
                                  ) : group.driver_rate ? (
                                    <div className="relative">
                                      <div
                                        className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium cursor-help ${group.driver_rate >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}
                                        onMouseEnter={() => setHoveredDriver(group.id)}
                                        onMouseLeave={() => setHoveredDriver(null)}
                                      >
                                        <span>{group.driver_name || group.driver_code}</span>
                                        <span>{group.driver_rate > 0 ? '+' : ''}{group.driver_rate}%</span>
                                        <HelpCircle className="w-3 h-3 opacity-50" />
                                      </div>
                                      {hoveredDriver === group.id && group.driver_name && (
                                        <div className="absolute z-50 w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-1">
                                          <div className="font-semibold">{group.driver_name}</div>
                                          <div className="text-gray-300">Rate: {group.driver_rate}%</div>
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
                                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
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
                                        title="View Accounts (Level 4)"
                                      >
                                        <Layers className="w-4 h-4" />
                                      </button>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Level 4: COA Accounts (Inline Expansion) */}
                            {expandedBudgetGroups.has(group.id) && (
                              <div className="bg-gray-50 border-t pl-20 pr-4 py-2">
                                <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                                  <span className="bg-gray-200 px-1.5 py-0.5 rounded">Level 4</span>
                                  COA Account Details
                                </div>
                                <div className="text-xs text-gray-400 italic">
                                  Click the <Layers className="w-3 h-3 inline" /> icon to view detailed account breakdown with monthly values.
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}

      {/* Drill-Down Modal (Level 4 Details) */}
      {drillDownGroup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b bg-gray-50">
              <div>
                <h3 className="text-lg font-semibold">{drillDownGroup.budgeting_group_name}</h3>
                <p className="text-sm text-gray-500">Level 4: COA Account Details</p>
              </div>
              <button onClick={() => setDrillDownGroup(null)} className="p-1 hover:bg-gray-200 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-auto max-h-[60vh]">
              {drillDownLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                </div>
              ) : drillDownData?.details ? (
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">COA Code</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">Account Name</th>
                      <th className="px-3 py-2 text-right font-medium text-gray-600">Total</th>
                      {MONTH_LABELS.map((m) => (
                        <th key={m} className="px-2 py-2 text-right font-medium text-gray-600 text-xs">{m}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {drillDownData.details.map((detail: any) => (
                      <tr key={detail.coa_code} className="border-t hover:bg-blue-50/30">
                        <td className="px-3 py-2 font-mono text-blue-600">{detail.coa_code}</td>
                        <td className="px-3 py-2 truncate max-w-[200px]" title={detail.coa_name}>{detail.coa_name}</td>
                        <td className="px-3 py-2 text-right font-mono font-medium">{formatCurrency(detail.baseline_total)}</td>
                        {MONTHS.map((m) => (
                          <td key={m} className="px-2 py-2 text-right font-mono text-xs text-gray-600">
                            {formatCurrency(detail.monthly_baseline?.[m] || 0)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center py-8 text-gray-500">No account details available</div>
              )}
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
