import React, { useState, useEffect, useCallback } from 'react';
import {
  Save,
  Play,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  ChevronDown,
  ChevronRight,
  Info,
  TrendingUp,
  TrendingDown,
  RefreshCw,
} from 'lucide-react';
import { budgetPlanningAPI } from '../../services/api';

interface DriverOption {
  id: number;
  code: string;
  name_en: string;
  driver_type: string | null;
  default_value: number | null;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  formula_description: string | null;
}

interface GroupDriverConfig {
  budgeting_group_id: number | null;
  fpna_product_key?: string | null;
  product_key?: string | null;
  budgeting_group_name: string;
  bs_flag: number;
  bs_class_name: string;
  bs_group: string;
  bs_group_name: string;
  total_baseline: number;
  total_adjusted: number;
  assigned_driver: {
    driver_id: number;
    driver_code: string;
    driver_name: string;
    driver_type: string | null;
    default_value: number | null;
    unit: string;
  } | null;
  rate: number | null;
  monthly_rates: Record<number, number> | null;
}

function driverConfigRowKey(g: GroupDriverConfig): string {
  const pk = g.fpna_product_key || g.product_key;
  if (pk) return `p:${pk}`;
  return `b:${g.budgeting_group_id ?? 'none'}`;
}

interface EditState {
  driver_id: number | null;
  rate: number | null;
}

interface Props {
  fiscalYear: number;
  onApplied?: () => void;
}

const DRIVER_TYPE_COLORS: Record<string, string> = {
  yield_rate: 'bg-green-100 text-green-700',
  cost_rate: 'bg-red-100 text-red-700',
  growth_rate: 'bg-blue-100 text-blue-700',
  provision_rate: 'bg-amber-100 text-amber-700',
  inflation_rate: 'bg-purple-100 text-purple-700',
  fx_rate: 'bg-cyan-100 text-cyan-700',
  headcount: 'bg-indigo-100 text-indigo-700',
  custom: 'bg-gray-100 text-gray-700',
};

const DRIVER_TYPE_LABELS: Record<string, string> = {
  yield_rate: 'Yield',
  cost_rate: 'Cost',
  growth_rate: 'Growth',
  provision_rate: 'Provision',
  inflation_rate: 'Inflation',
  fx_rate: 'FX Rate',
  headcount: 'Headcount',
  custom: 'Custom',
};

const formatCurrency = (num: number): string => {
  if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(1)}T`;
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toFixed(0);
};

const DriverConfigPanel: React.FC<Props> = ({ fiscalYear, onApplied }) => {
  const [drivers, setDrivers] = useState<DriverOption[]>([]);
  const [groups, setGroups] = useState<GroupDriverConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [edits, setEdits] = useState<Record<string, EditState>>({});
  const [dirty, setDirty] = useState(false);

  // Collapsed BS classes
  const [expandedClasses, setExpandedClasses] = useState<Set<number>>(new Set());

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await budgetPlanningAPI.getDriverConfig(fiscalYear);
      setDrivers(data.drivers || []);
      setGroups(data.groups || []);

      const initialEdits: Record<string, EditState> = {};
      for (const g of data.groups || []) {
        const rk = driverConfigRowKey(g as GroupDriverConfig);
        initialEdits[rk] = {
          driver_id: g.assigned_driver?.driver_id ?? null,
          rate: g.rate ?? g.assigned_driver?.default_value ?? null,
        };
      }
      setEdits(initialEdits);
      setDirty(false);

      // Expand all classes by default
      const classFlags = new Set<number>(
        (data.groups || []).map((g: GroupDriverConfig) => g.bs_flag),
      );
      setExpandedClasses(classFlags);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load driver config');
    } finally {
      setLoading(false);
    }
  }, [fiscalYear]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleDriverChange = (rowKey: string, driverId: number | null) => {
    const driver = drivers.find(d => d.id === driverId);
    setEdits(prev => ({
      ...prev,
      [rowKey]: {
        driver_id: driverId,
        rate: driver?.default_value ?? prev[rowKey]?.rate ?? null,
      },
    }));
    setDirty(true);
  };

  const handleRateChange = (rowKey: string, rate: number | null) => {
    setEdits(prev => ({
      ...prev,
      [rowKey]: { ...prev[rowKey], rate },
    }));
    setDirty(true);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const configs = groups.map(g => {
        const rk = driverConfigRowKey(g);
        const edit = edits[rk] || { driver_id: null, rate: null };
        return {
          fpna_product_key: g.fpna_product_key || g.product_key || undefined,
          budgeting_group_id: g.budgeting_group_id ?? undefined,
          driver_id: edit.driver_id,
          rate: edit.rate,
        };
      });

      await budgetPlanningAPI.saveDriverConfig(fiscalYear, configs);
      setSuccess('Driver configuration saved');
      setDirty(false);
      await loadConfig();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleApplyAll = async () => {
    if (dirty) {
      setError('Please save your changes before applying drivers');
      return;
    }
    try {
      setApplying(true);
      setError(null);
      const result = await budgetPlanningAPI.applyDriversBulk(fiscalYear);
      setSuccess(`Applied drivers to ${result.groups_applied} groups (${result.groups_skipped} skipped)`);
      await loadConfig();
      onApplied?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply drivers');
    } finally {
      setApplying(false);
    }
  };

  const toggleClass = (bsFlag: number) => {
    setExpandedClasses(prev => {
      const next = new Set(prev);
      if (next.has(bsFlag)) next.delete(bsFlag);
      else next.add(bsFlag);
      return next;
    });
  };

  // Estimate adjusted total for a group given a rate and driver type
  const estimateAdjusted = (baseline: number, rate: number | null, driverId: number | null): number | null => {
    if (rate === null || driverId === null) return null;
    const driver = drivers.find(d => d.id === driverId);
    if (!driver) return null;
    const dt = driver.driver_type;
    if (dt === 'growth_rate') {
      let total = 0;
      for (let m = 1; m <= 12; m++) {
        total += (baseline / 12) * Math.pow(1 + rate / 100, m / 12);
      }
      return total;
    }
    if (dt === 'yield_rate' || dt === 'cost_rate') {
      return baseline + baseline * rate / 100 / 12 * 12;
    }
    return baseline * (1 + rate / 100);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  // Group by bs_flag for display
  const byClass: Record<number, { name: string; groups: GroupDriverConfig[] }> = {};
  for (const g of groups) {
    const flag = g.bs_flag ?? 0;
    if (!byClass[flag]) byClass[flag] = { name: g.bs_class_name || `Class ${flag}`, groups: [] };
    byClass[flag].groups.push(g);
  }

  const configuredCount = Object.values(edits).filter(e => e.driver_id !== null).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-lg border p-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Driver Configuration</h3>
            <p className="text-sm text-gray-500 mt-1">
              Assign drivers and rates per FP&A product (or legacy budgeting group). Departments see these as available drivers.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-500">
              {configuredCount}/{groups.length} configured
            </div>
            <button
              onClick={loadConfig}
              className="p-2 border rounded-lg hover:bg-gray-50"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 mt-4 pt-4 border-t">
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Configuration
          </button>
          <button
            onClick={handleApplyAll}
            disabled={applying || dirty}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            title={dirty ? 'Save first before applying' : 'Apply all configured drivers to budget plans'}
          >
            {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Apply All Drivers
          </button>
          {dirty && (
            <span className="text-sm text-amber-600 font-medium">Unsaved changes</span>
          )}
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          {success}
          <button onClick={() => setSuccess(null)} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Driver legend */}
      <div className="flex flex-wrap items-center gap-2 px-4 py-2 bg-gray-50 rounded-lg border text-xs">
        <span className="font-medium text-gray-600 mr-1">Driver types:</span>
        {Object.entries(DRIVER_TYPE_LABELS).map(([key, label]) => (
          <span key={key} className={`px-2 py-0.5 rounded font-medium ${DRIVER_TYPE_COLORS[key]}`}>
            {label}
          </span>
        ))}
      </div>

      {/* Groups table by BS class */}
      {Object.entries(byClass).sort(([a], [b]) => Number(a) - Number(b)).map(([flagStr, data]) => {
        const flag = Number(flagStr);
        const isExpanded = expandedClasses.has(flag);

        return (
          <div key={flag} className="bg-white rounded-lg border overflow-hidden">
            <button
              onClick={() => toggleClass(flag)}
              className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-gray-100 to-gray-50 hover:from-gray-200 hover:to-gray-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                {isExpanded ? <ChevronDown className="w-5 h-5 text-gray-600" /> : <ChevronRight className="w-5 h-5 text-gray-600" />}
                <span className="font-bold text-gray-900">{data.name}</span>
                <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                  {data.groups.length} groups
                </span>
              </div>
              <div className="text-sm text-gray-500">
                  {data.groups.filter(g => edits[driverConfigRowKey(g)]?.driver_id).length}/{data.groups.length} configured
              </div>
            </button>

            {isExpanded && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-t border-b">
                      <th className="text-left p-3 font-semibold text-gray-700">Product / group</th>
                      <th className="text-right p-3 font-semibold text-gray-700 w-28">Baseline</th>
                      <th className="text-left p-3 font-semibold text-gray-700 w-56">Driver</th>
                      <th className="text-right p-3 font-semibold text-gray-700 w-24">Rate</th>
                      <th className="text-right p-3 font-semibold text-gray-700 w-28">Est. Adjusted</th>
                      <th className="text-right p-3 font-semibold text-gray-700 w-24">Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.groups.map(g => {
                      const rk = driverConfigRowKey(g);
                      const edit = edits[rk] || { driver_id: null, rate: null };
                      const selectedDriver = drivers.find(d => d.id === edit.driver_id);
                      const estimated = estimateAdjusted(g.total_baseline, edit.rate, edit.driver_id);
                      const impact = estimated !== null ? estimated - g.total_baseline : null;
                      const impactPct = g.total_baseline !== 0 && impact !== null
                        ? (impact / Math.abs(g.total_baseline)) * 100
                        : null;

                      return (
                        <tr key={rk} className="border-b border-gray-100 hover:bg-gray-50/80">
                          <td className="p-3">
                            <div className="font-medium text-gray-900">{g.budgeting_group_name}</div>
                            <div className="text-xs text-gray-500">{g.bs_group_name}</div>
                          </td>
                          <td className="p-3 text-right font-mono text-gray-700">
                            {formatCurrency(g.total_baseline)}
                          </td>
                          <td className="p-2">
                            <div className="flex items-center gap-2">
                              <select
                                value={edit.driver_id ?? ''}
                                onChange={(e) => handleDriverChange(rk, e.target.value ? parseInt(e.target.value) : null)}
                                className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              >
                                <option value="">No driver</option>
                                {drivers.map(d => (
                                  <option key={d.id} value={d.id}>
                                    {d.name_en} ({DRIVER_TYPE_LABELS[d.driver_type || 'custom'] || d.driver_type})
                                  </option>
                                ))}
                              </select>
                              {selectedDriver?.driver_type && (
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold whitespace-nowrap ${DRIVER_TYPE_COLORS[selectedDriver.driver_type] || 'bg-gray-100 text-gray-700'}`}>
                                  {DRIVER_TYPE_LABELS[selectedDriver.driver_type] || selectedDriver.driver_type}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-2">
                            <input
                              type="number"
                              step="0.1"
                              value={edit.rate ?? ''}
                              onChange={(e) => handleRateChange(rk, e.target.value === '' ? null : parseFloat(e.target.value))}
                              disabled={!edit.driver_id}
                              placeholder="%"
                              className="w-full px-2 py-1.5 border border-gray-300 rounded text-right text-sm font-mono focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                            />
                          </td>
                          <td className="p-3 text-right font-mono text-blue-700">
                            {estimated !== null ? formatCurrency(estimated) : '—'}
                          </td>
                          <td className="p-3 text-right">
                            {impactPct !== null ? (
                              <div className={`flex items-center justify-end gap-0.5 font-medium text-sm ${impactPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {impactPct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                <span>{impactPct >= 0 ? '+' : ''}{impactPct.toFixed(1)}%</span>
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      {groups.length === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-2 text-blue-700">
          <Info className="w-5 h-5" />
          No budgeting groups found. Initialize the budget cycle first (Step 1).
        </div>
      )}
    </div>
  );
};

export default DriverConfigPanel;
