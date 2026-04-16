import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2, AlertCircle, Check, X, Plus, Pencil, Trash2,
  RefreshCw, Calculator, Database, TrendingUp, TrendingDown,
  ChevronDown, ChevronRight, Save, BarChart2,
} from 'lucide-react';
import { driversAPI } from '../../services/api';

// ── Types ──────────────────────────────────────────────────────────────────
interface Driver {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  driver_type: string;
  scope: string;
  source_account_pattern: string | null;
  target_account_pattern: string | null;
  formula: string | null;
  formula_description: string | null;
  default_value: number | null;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  decimal_places: number;
  is_active: boolean;
  is_system: boolean;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const DRIVER_TYPES = [
  { value: 'growth_rate', label: 'Growth Rate', color: 'bg-blue-100 text-blue-700' },
  { value: 'yield_rate', label: 'Yield Rate', color: 'bg-green-100 text-green-700' },
  { value: 'cost_rate', label: 'Cost Rate', color: 'bg-red-100 text-red-700' },
  { value: 'provision_rate', label: 'Provision Rate', color: 'bg-amber-100 text-amber-700' },
  { value: 'inflation_rate', label: 'Inflation Rate', color: 'bg-purple-100 text-purple-700' },
  { value: 'fx_rate', label: 'FX Rate', color: 'bg-cyan-100 text-cyan-700' },
  { value: 'headcount', label: 'Headcount', color: 'bg-indigo-100 text-indigo-700' },
  { value: 'custom', label: 'Custom', color: 'bg-gray-100 text-gray-700' },
];

const getTypeColor = (type: string) => DRIVER_TYPES.find(t => t.value === type)?.color || 'bg-gray-100 text-gray-700';
const getTypeLabel = (type: string) => DRIVER_TYPES.find(t => t.value === type)?.label || type;

// ── Drivers Page ───────────────────────────────────────────────────────────
const DriversPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'drivers' | 'values'>('drivers');
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [initialLoaded, setInitialLoaded] = useState(false);

  const fetchDrivers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await driversAPI.list();
      setDrivers(data);
      setInitialLoaded(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load drivers');
      setInitialLoaded(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDrivers(); }, [fetchDrivers]);

  if (loading && !initialLoaded) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-primary-600 animate-spin" /></div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Drivers</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Budget calculation drivers and historical values</p>
        </div>
        <button onClick={fetchDrivers} className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-800 dark:text-gray-300 dark:border-slate-600">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="text-red-800 dark:text-red-300 flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4 text-red-400" /></button>
        </div>
      )}
      {success && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 flex items-center gap-3">
          <Check className="w-5 h-5 text-green-600" />
          <span className="text-green-800 dark:text-green-300 flex-1">{success}</span>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4 text-green-400" /></button>
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700">
        <div className="p-4 border-b border-gray-200 dark:border-slate-700 flex gap-2">
          <button onClick={() => setActiveTab('drivers')}
            className={`px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2 ${activeTab === 'drivers' ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400'}`}>
            <Calculator className="w-4 h-4" /> Drivers ({drivers.length})
          </button>
          <button onClick={() => setActiveTab('values')}
            className={`px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2 ${activeTab === 'values' ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400'}`}>
            <BarChart2 className="w-4 h-4" /> Driver Values & Deltas
          </button>
        </div>

        <div className="p-4">
          {activeTab === 'drivers' && (
            <DriversTab drivers={drivers} onRefresh={fetchDrivers} onError={setError} onSuccess={setSuccess} />
          )}
          {activeTab === 'values' && (
            <DriverValuesTab drivers={drivers} onError={setError} onSuccess={setSuccess} />
          )}
        </div>
      </div>
    </div>
  );
};

// ── Tab 1: Drivers CRUD ────────────────────────────────────────────────────
const DriversTab: React.FC<{
  drivers: Driver[];
  onRefresh: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ drivers, onRefresh, onError, onSuccess }) => {
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Driver | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    code: '', name_en: '', name_uz: '', driver_type: 'growth_rate', scope: 'global',
    source_account_pattern: '', target_account_pattern: '', formula: '', formula_description: '',
    default_value: '', min_value: '', max_value: '', unit: '%',
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ code: '', name_en: '', name_uz: '', driver_type: 'growth_rate', scope: 'global',
      source_account_pattern: '', target_account_pattern: '', formula: '', formula_description: '',
      default_value: '', min_value: '', max_value: '', unit: '%' });
    setShowForm(true);
  };

  const openEdit = (d: Driver) => {
    setEditing(d);
    setForm({
      code: d.code, name_en: d.name_en, name_uz: d.name_uz || '',
      driver_type: d.driver_type, scope: d.scope || 'global',
      source_account_pattern: d.source_account_pattern || '',
      target_account_pattern: d.target_account_pattern || '',
      formula: d.formula || '', formula_description: d.formula_description || '',
      default_value: d.default_value?.toString() || '',
      min_value: d.min_value?.toString() || '',
      max_value: d.max_value?.toString() || '',
      unit: d.unit || '%',
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.code || !form.name_en) { onError('Code and name are required'); return; }
    try {
      setSaving(true);
      const payload: any = {
        code: form.code, name_en: form.name_en, name_uz: form.name_uz || undefined,
        driver_type: form.driver_type, scope: form.scope,
        source_account_pattern: form.source_account_pattern || undefined,
        target_account_pattern: form.target_account_pattern || undefined,
        formula: form.formula || undefined,
        formula_description: form.formula_description || undefined,
        default_value: form.default_value ? parseFloat(form.default_value) : undefined,
        min_value: form.min_value ? parseFloat(form.min_value) : undefined,
        max_value: form.max_value ? parseFloat(form.max_value) : undefined,
        unit: form.unit,
      };
      if (editing) {
        await driversAPI.update(editing.code, payload);
        onSuccess(`Updated driver ${form.name_en}`);
      } else {
        await driversAPI.create(payload);
        onSuccess(`Created driver ${form.name_en}`);
      }
      setShowForm(false);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to save driver');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (d: Driver) => {
    if (d.is_system) { onError('System drivers cannot be deleted'); return; }
    if (!confirm(`Delete driver "${d.name_en}"?`)) return;
    try {
      await driversAPI.delete(d.code);
      onSuccess(`Deleted ${d.name_en}`);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const handleSeed = async () => {
    try {
      await driversAPI.seed();
      onSuccess('Default drivers seeded successfully');
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to seed');
    }
  };

  return (
    <div>
      <div className="flex justify-end gap-2 mb-4">
        <button onClick={handleSeed} className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-800 dark:text-gray-300 dark:border-slate-600">
          <Database className="w-4 h-4" /> Seed Defaults
        </button>
        <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
          <Plus className="w-4 h-4" /> Add Driver
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Code</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Name</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Type</th>
              <th className="text-right p-3 font-semibold text-gray-700 dark:text-gray-300">Default</th>
              <th className="text-right p-3 font-semibold text-gray-700 dark:text-gray-300">Range</th>
              <th className="text-center p-3 font-semibold text-gray-700 dark:text-gray-300">System</th>
              <th className="text-center p-3 font-semibold text-gray-700 dark:text-gray-300">Actions</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map(d => (
              <tr key={d.id} className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-800/50">
                <td className="p-3 font-mono font-medium text-primary-600">{d.code}</td>
                <td className="p-3">
                  <div className="text-gray-900 dark:text-white">{d.name_en}</div>
                  {d.name_uz && <div className="text-gray-500 text-xs">{d.name_uz}</div>}
                </td>
                <td className="p-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(d.driver_type)}`}>
                    {getTypeLabel(d.driver_type)}
                  </span>
                </td>
                <td className="p-3 text-right font-mono">{d.default_value != null ? `${d.default_value}${d.unit}` : '—'}</td>
                <td className="p-3 text-right font-mono text-xs text-gray-500">
                  {d.min_value != null || d.max_value != null ? `${d.min_value ?? '—'} – ${d.max_value ?? '—'}` : '—'}
                </td>
                <td className="p-3 text-center">
                  {d.is_system && <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">SYS</span>}
                </td>
                <td className="p-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <button onClick={() => openEdit(d)} className="p-1 text-gray-400 hover:text-primary-600"><Pencil className="w-4 h-4" /></button>
                    {!d.is_system && (
                      <button onClick={() => handleDelete(d)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {drivers.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <Calculator className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No drivers configured. Click "Seed Defaults" to load banking standard drivers.</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl w-full max-w-lg max-h-[85vh] overflow-y-auto">
            <div className="p-4 border-b dark:border-slate-700">
              <h3 className="text-lg font-semibold">{editing ? 'Edit' : 'New'} Driver</h3>
              {editing?.is_system && <p className="text-xs text-amber-600 mt-1">System driver: only default, min, max, and unit can be edited</p>}
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Code *</label>
                  <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} disabled={!!editing}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white disabled:opacity-50" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
                  <select value={form.driver_type} onChange={e => setForm({ ...form, driver_type: e.target.value })} disabled={editing?.is_system}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white disabled:opacity-50">
                    {DRIVER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (EN) *</label>
                <input value={form.name_en} onChange={e => setForm({ ...form, name_en: e.target.value })} disabled={editing?.is_system}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white disabled:opacity-50" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (UZ)</label>
                <input value={form.name_uz} onChange={e => setForm({ ...form, name_uz: e.target.value })} disabled={editing?.is_system}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white disabled:opacity-50" />
              </div>
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Default</label>
                  <input type="number" step="0.01" value={form.default_value} onChange={e => setForm({ ...form, default_value: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Min</label>
                  <input type="number" step="0.01" value={form.min_value} onChange={e => setForm({ ...form, min_value: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max</label>
                  <input type="number" step="0.01" value={form.max_value} onChange={e => setForm({ ...form, max_value: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Unit</label>
                  <input value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white" />
                </div>
              </div>
              {!editing?.is_system && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description / Formula</label>
                  <textarea value={form.formula_description} onChange={e => setForm({ ...form, formula_description: e.target.value })} rows={2}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white" />
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 p-4 border-t dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 rounded-b-xl">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg">Cancel</button>
              <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                {editing ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Tab 2: Driver Values with Monthly & Yearly Deltas ──────────────────────
const DriverValuesTab: React.FC<{
  drivers: Driver[];
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ drivers, onError, onSuccess }) => {
  const currentYear = new Date().getFullYear();
  const [fiscalYear, setFiscalYear] = useState(currentYear + 1);
  const [selectedDriver, setSelectedDriver] = useState<string>('');
  const [currentValues, setCurrentValues] = useState<Record<number, number>>({});
  const [prevYearValues, setPrevYearValues] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editValues, setEditValues] = useState<Record<number, string>>({});
  const [dirty, setDirty] = useState(false);

  const [actualsSource, setActualsSource] = useState<string>('');

  const loadMatrix = useCallback(async () => {
    if (!selectedDriver) return;
    setLoading(true);
    try {
      // Load planned values for current year and actuals for both years from DWH
      const [curr, currActuals, prevActuals] = await Promise.all([
        driversAPI.getValueMatrix(selectedDriver, fiscalYear).catch(() => ({ monthly_values: {} })),
        driversAPI.getActuals(selectedDriver, fiscalYear).catch(() => ({ monthly_values: {}, source: 'none' })),
        driversAPI.getActuals(selectedDriver, fiscalYear - 1).catch(() => ({ monthly_values: {}, source: 'none' })),
      ]);
      const cVals: Record<number, number> = {};
      const pVals: Record<number, number> = {};
      for (let m = 1; m <= 12; m++) {
        // Current year: use planned values from driver_values if available, else actuals
        cVals[m] = curr.monthly_values?.[m] ?? currActuals.monthly_values?.[m] ?? 0;
        // Prior year: always use actuals from DWH baseline_data
        pVals[m] = prevActuals.monthly_values?.[m] ?? 0;
      }
      setCurrentValues(cVals);
      setPrevYearValues(pVals);
      setActualsSource(prevActuals.source || 'none');
      // Init edit values from planned data
      const edits: Record<number, string> = {};
      for (let m = 1; m <= 12; m++) {
        edits[m] = cVals[m] ? cVals[m].toString() : '';
      }
      setEditValues(edits);
      setDirty(false);
    } catch (err: any) {
      onError(err.message || 'Failed to load values');
    } finally {
      setLoading(false);
    }
  }, [selectedDriver, fiscalYear, onError]);

  useEffect(() => { loadMatrix(); }, [loadMatrix]);

  const handleValueChange = (month: number, val: string) => {
    setEditValues(prev => ({ ...prev, [month]: val }));
    setDirty(true);
  };

  const handleSaveValues = async () => {
    if (!selectedDriver || !driver) return;
    try {
      setSaving(true);
      const values = Object.entries(editValues)
        .filter(([, v]) => v !== '')
        .map(([m, v]) => ({
          driver_id: driver.id,
          fiscal_year: fiscalYear,
          month: parseInt(m),
          value: parseFloat(v),
          value_type: 'rate',
        }));
      if (values.length > 0) {
        await driversAPI.bulkCreateValues(values);
        onSuccess(`Saved ${values.length} monthly values`);
        await loadMatrix();
      }
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to save values');
    } finally {
      setSaving(false);
    }
  };

  const driver = drivers.find(d => d.code === selectedDriver);

  // Calculate deltas
  const monthlyDeltas: Record<number, number | null> = {};
  const yearlyDeltas: Record<number, number | null> = {};
  for (let m = 1; m <= 12; m++) {
    const val = editValues[m] ? parseFloat(editValues[m]) : null;
    const prevMonth = m > 1 && editValues[m - 1] ? parseFloat(editValues[m - 1]) : null;
    const prevYearMonth = prevYearValues[m] || null;

    monthlyDeltas[m] = val !== null && prevMonth !== null ? val - prevMonth : null;
    yearlyDeltas[m] = val !== null && prevYearMonth !== null ? val - prevYearMonth : null;
  }

  // Annual totals / averages
  const currTotal = Object.values(editValues).reduce((sum, v) => sum + (v ? parseFloat(v) : 0), 0);
  const currAvg = currTotal / 12;
  const prevTotal = Object.values(prevYearValues).reduce((sum, v) => sum + (v || 0), 0);
  const prevAvg = prevTotal / 12;
  const yearDelta = currAvg - prevAvg;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Driver</label>
          <select value={selectedDriver} onChange={e => setSelectedDriver(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white min-w-[250px]">
            <option value="">Select a driver...</option>
            {drivers.map(d => (
              <option key={d.code} value={d.code}>{d.name_en} ({getTypeLabel(d.driver_type)})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Fiscal Year</label>
          <select value={fiscalYear} onChange={e => setFiscalYear(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white">
            {[currentYear - 1, currentYear, currentYear + 1, currentYear + 2].map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        {selectedDriver && (
          <div className="ml-auto flex gap-2">
            <button onClick={handleSaveValues} disabled={saving || !dirty}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
            </button>
          </div>
        )}
      </div>

      {!selectedDriver ? (
        <div className="text-center py-16 text-gray-400">
          <BarChart2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Select a driver to view and edit monthly values</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center h-48"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>
      ) : (
        <div>
          {/* Data source badge */}
          {actualsSource && (
            <div className="mb-3 flex items-center gap-2 text-xs">
              <span className={`px-2 py-1 rounded font-medium ${actualsSource === 'baseline_data' ? 'bg-green-100 text-green-700' : actualsSource === 'driver_values' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}>
                {actualsSource === 'baseline_data' ? 'Actuals from DWH' : actualsSource === 'driver_values' ? 'From saved values' : 'No data'}
              </span>
              <span className="text-gray-400">Prior year values source</span>
            </div>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="bg-white dark:bg-slate-800 border dark:border-slate-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase">Budget Avg ({fiscalYear})</div>
              <div className="text-2xl font-bold text-blue-600 mt-1">{currAvg.toFixed(2)}{driver?.unit}</div>
            </div>
            <div className="bg-white dark:bg-slate-800 border dark:border-slate-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase">Actual Avg ({fiscalYear - 1})</div>
              <div className="text-2xl font-bold text-gray-600 mt-1">{prevAvg.toFixed(2)}{driver?.unit}</div>
            </div>
            <div className="bg-white dark:bg-slate-800 border dark:border-slate-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase">YoY Change</div>
              <div className={`text-2xl font-bold mt-1 flex items-center gap-1 ${yearDelta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {yearDelta >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                {yearDelta >= 0 ? '+' : ''}{yearDelta.toFixed(2)}{driver?.unit}
              </div>
            </div>
            <div className="bg-white dark:bg-slate-800 border dark:border-slate-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase">YoY Change %</div>
              <div className={`text-2xl font-bold mt-1 ${yearDelta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {prevAvg !== 0 ? `${yearDelta >= 0 ? '+' : ''}${((yearDelta / prevAvg) * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>

          {/* Matrix table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800 border-b dark:border-slate-700">
                  <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300 w-40">Row</th>
                  {MONTHS.map((m, i) => (
                    <th key={m} className="text-center p-2 font-semibold text-gray-700 dark:text-gray-300 w-20">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Current Year Values (editable) */}
                <tr className="border-b border-gray-200 dark:border-slate-700">
                  <td className="p-3 font-medium text-gray-900 dark:text-white">{fiscalYear} Budget</td>
                  {MONTHS.map((_, i) => {
                    const m = i + 1;
                    return (
                      <td key={m} className="p-1">
                        <input
                          type="number" step="0.01"
                          value={editValues[m] || ''}
                          onChange={e => handleValueChange(m, e.target.value)}
                          className="w-full px-2 py-1.5 border border-gray-300 dark:border-slate-600 rounded text-center text-sm font-mono dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500"
                          placeholder="—"
                        />
                      </td>
                    );
                  })}
                </tr>

                {/* Prior Year Values (read-only) */}
                <tr className="border-b border-gray-100 dark:border-slate-700/50 bg-gray-50/50 dark:bg-slate-800/30">
                  <td className="p-3 text-gray-500 text-xs">{fiscalYear - 1} Actual</td>
                  {MONTHS.map((_, i) => (
                    <td key={i + 1} className="p-2 text-center font-mono text-xs text-gray-500">
                      {prevYearValues[i + 1] ? prevYearValues[i + 1].toFixed(2) : '—'}
                    </td>
                  ))}
                </tr>

                {/* MoM Delta */}
                <tr className="border-b border-gray-100 dark:border-slate-700/50">
                  <td className="p-3 text-gray-500 text-xs">MoM Delta</td>
                  {MONTHS.map((_, i) => {
                    const m = i + 1;
                    const delta = monthlyDeltas[m];
                    return (
                      <td key={m} className="p-2 text-center">
                        {delta !== null ? (
                          <span className={`font-mono text-xs font-medium ${delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-400'}`}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                    );
                  })}
                </tr>

                {/* YoY Delta */}
                <tr className="border-b border-gray-200 dark:border-slate-700">
                  <td className="p-3 text-gray-500 text-xs">YoY Delta</td>
                  {MONTHS.map((_, i) => {
                    const m = i + 1;
                    const delta = yearlyDeltas[m];
                    return (
                      <td key={m} className="p-2 text-center">
                        {delta !== null ? (
                          <span className={`font-mono text-xs font-medium ${delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-400'}`}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>

          {dirty && <p className="text-sm text-amber-600 mt-2">Unsaved changes — click Save to persist</p>}
        </div>
      )}
    </div>
  );
};

export default DriversPage;
