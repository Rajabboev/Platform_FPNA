import React, { useState, useEffect, useCallback } from 'react';
import {
  Database,
  Calculator,
  FileSpreadsheet,
  Upload,
  Download,
  CheckCircle,
  Clock,
  AlertCircle,
  RefreshCw,
  ChevronRight,
  ArrowRight,
  TrendingUp,
  Filter,
  Search,
  Send,
  Check,
  X,
  Building2,
  Users,
  ClipboardCheck,
  Brain,
  Eye,
  Loader2,
  Table,
  Columns,
  BarChart3,
  Shield,
  GitBranch,
  Plus,
} from 'lucide-react';
import { budgetPlanningAPI, departmentAPI, connectionsAPI } from '../services/api';
import DepartmentBudgetTemplate from './budget/DepartmentBudgetTemplate';
import BudgetApprovalDashboard from './budget/BudgetApprovalDashboard';
import DriverConfigPanel from './budget/DriverConfigPanel';

interface WorkflowStatus {
  fiscal_year: number;
  total_plans: number;
  status_counts: Record<string, number>;
  all_cfo_approved: boolean;
  all_ceo_approved: boolean;
  ready_for_ceo: number;
  ready_for_export: number;
}

interface Department {
  id: number;
  code: string;
  name_en: string;
  is_active: boolean;
  is_baseline_only: boolean;
  budgeting_group_ids: number[];
  dwh_segment_value?: string | null;
  primary_product_key?: string | null;
  product_label_en?: string | null;
  product_pillar?: string | null;
}

interface Connection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  database_name: string;
  is_active: boolean;
}

const formatNumber = (num: number): string => {
  if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(2) + 'T';
  if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(2) + 'B';
  if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(2) + 'M';
  if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(2) + 'K';
  return num.toFixed(2);
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colors: Record<string, string> = {
    COMPLETED: 'bg-green-100 text-green-800',
    PENDING: 'bg-yellow-100 text-yellow-800',
    IN_PROGRESS: 'bg-blue-100 text-blue-800',
    DRAFT: 'bg-gray-100 text-gray-800',
    SUBMITTED: 'bg-blue-100 text-blue-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
    EXPORTED: 'bg-purple-100 text-purple-800',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  );
};

const StepCard: React.FC<{
  step: number;
  title: string;
  description: string;
  status: string;
  icon: React.ReactNode;
  stats?: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
}> = ({ step, title, description, status, icon, stats, isActive, onClick }) => (
  <div
    onClick={onClick}
    className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${
      isActive
        ? 'border-blue-500 bg-blue-50'
        : status === 'COMPLETED'
        ? 'border-green-200 bg-green-50'
        : 'border-gray-200 bg-white hover:border-gray-300'
    }`}
  >
    <div className="flex items-start gap-2">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          status === 'COMPLETED' ? 'bg-green-500 text-white' : isActive ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-600'
        }`}
      >
        {status === 'COMPLETED' ? <CheckCircle className="w-4 h-4" /> : icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1">
          <h3 className="font-semibold text-gray-900 text-sm truncate">{step}. {title}</h3>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 truncate">{description}</p>
        {stats && <div className="mt-1">{stats}</div>}
      </div>
    </div>
  </div>
);


const BudgetPlanningNew: React.FC = () => {
  const [fiscalYear, setFiscalYear] = useState(2027);
  const [activeStep, setActiveStep] = useState(1);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedDepartment, setSelectedDepartment] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Step 1 state
  const [sourceYears, setSourceYears] = useState<number[]>([]);
  const [calculationMethod, setCalculationMethod] = useState('simple_average');
  const [dwhTables, setDwhTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState('balans_ato');
  const [previewData, setPreviewData] = useState<any>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

  // Step 2 state
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [comparingBaselines, setComparingBaselines] = useState(false);

  // Step 3 state
  const [assignmentData, setAssignmentData] = useState<any>(null);

  // Step 6 state
  const [consolidatedPlan, setConsolidatedPlan] = useState<any>(null);
  const [ceoComment, setCeoComment] = useState('');
  const [rejectReason, setRejectReason] = useState('');

  // Step 7 state
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [newScenarioName, setNewScenarioName] = useState('');
  const [selectedScenario, setSelectedScenario] = useState<number | null>(null);
  const [scenarioComparison, setScenarioComparison] = useState<any>(null);
  const [targetTable, setTargetTable] = useState('year_budget_approved');

  const loadWorkflowStatus = useCallback(async () => {
    try {
      const status = await budgetPlanningAPI.getWorkflowStatus(fiscalYear);
      setWorkflowStatus(status);
    } catch (err) {
      console.error('Failed to load workflow status:', err);
    }
  }, [fiscalYear]);

  const loadConnections = useCallback(async () => {
    try {
      const conns = await connectionsAPI.list();
      setConnections(conns);
      if (conns.length > 0 && !selectedConnection) {
        setSelectedConnection(conns[0].id);
      }
    } catch (err) {
      console.error('Failed to load connections:', err);
    }
  }, [selectedConnection]);

  const loadDepartments = useCallback(async () => {
    try {
      const depts = await departmentAPI.list();
      setDepartments(depts);
    } catch (err) {
      console.error('Failed to load departments:', err);
    }
  }, []);

  useEffect(() => {
    loadWorkflowStatus();
    loadConnections();
    loadDepartments();
    setSourceYears([fiscalYear - 3, fiscalYear - 2, fiscalYear - 1]);
  }, [loadWorkflowStatus, loadConnections, loadDepartments, fiscalYear]);

  // Load DWH tables when connection changes
  useEffect(() => {
    if (selectedConnection) {
      connectionsAPI.getTables(selectedConnection)
        .then((tables: any) => setDwhTables(Array.isArray(tables) ? tables.map((t: any) => typeof t === 'string' ? t : t.table_name || t.name) : []))
        .catch(() => setDwhTables([]));
    }
  }, [selectedConnection]);

  const handlePreviewSource = async () => {
    if (!selectedConnection || !selectedTable) return;
    setLoading(true);
    try {
      const data = await budgetPlanningAPI.previewSource(selectedConnection, selectedTable);
      setPreviewData(data);
      if (data.auto_mapping) setColumnMapping(data.auto_mapping);
      setSuccess('Table preview loaded');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Preview failed');
    } finally {
      setLoading(false);
    }
  };

  const handleInitialize = async () => {
    if (!selectedConnection) { setError('Please select a DWH connection'); return; }
    setLoading(true); setError(null);
    try {
      const result = await budgetPlanningAPI.initialize(fiscalYear, {
        connection_id: selectedConnection,
        source_table: selectedTable,
        source_years: sourceYears,
        calculation_method: calculationMethod,
        column_mapping: Object.keys(columnMapping).length > 0 ? columnMapping : undefined,
      });
      setSuccess(`Initialized: ${result.plans?.plans_created || 0} department plans created`);
      loadWorkflowStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Initialization failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm(`FY ${fiscalYear} uchun barcha budget ma'lumotlari o'chiriladi. Davom etasizmi?`)) return;
    setLoading(true); setError(null);
    try {
      const result = await budgetPlanningAPI.resetFiscalYear(fiscalYear);
      setSuccess(`FY ${fiscalYear} tozalandi: ${JSON.stringify(result.deleted)}`);
      loadWorkflowStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Reset failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCompareBaselines = async () => {
    setComparingBaselines(true); setError(null);
    try {
      const data = await budgetPlanningAPI.compareBaselines(fiscalYear, sourceYears);
      setComparisonData(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Comparison failed');
    } finally {
      setComparingBaselines(false);
    }
  };

  const loadAssignments = useCallback(async () => {
    try {
      const data = await budgetPlanningAPI.getDepartmentAssignments(fiscalYear);
      setAssignmentData(data);
    } catch (err) {
      console.error('Failed to load assignments:', err);
    }
  }, [fiscalYear]);

  const loadConsolidated = useCallback(async () => {
    try {
      const data = await budgetPlanningAPI.getConsolidatedPlan(fiscalYear);
      setConsolidatedPlan(data);
    } catch (err) {
      console.error('Failed to load consolidated:', err);
    }
  }, [fiscalYear]);

  const loadScenarios = useCallback(async () => {
    try {
      const data = await budgetPlanningAPI.listScenarios(fiscalYear);
      setScenarios(data.scenarios || []);
    } catch (err) {
      console.error('Failed to load scenarios:', err);
    }
  }, [fiscalYear]);

  const [factSummary, setFactSummary] = useState<any>(null);

  const handleExport = async () => {
    if (!selectedConnection) { setError('Please select a DWH connection'); return; }
    setLoading(true); setError(null);
    try {
      const result = await budgetPlanningAPI.exportToDWH(fiscalYear, selectedConnection, targetTable);
      setSuccess(`Exported ${result.plans_exported} plans (${result.rows_exported} summary rows + ${result.fact_rows_exported || 0} detail rows) to DWH (batch: ${result.batch_id})`);
      loadWorkflowStatus();
      // Load fact table summary
      try {
        const summary = await budgetPlanningAPI.getFactTableSummary(fiscalYear);
        setFactSummary(summary);
      } catch { /* non-critical */ }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCeoApprove = async () => {
    setLoading(true); setError(null);
    try {
      await budgetPlanningAPI.ceoApprove(fiscalYear, ceoComment || undefined);
      setSuccess('CEO approval granted for all plans');
      loadWorkflowStatus(); loadConsolidated();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'CEO approval failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCeoReject = async () => {
    if (!rejectReason.trim()) { setError('Please provide a rejection reason'); return; }
    setLoading(true); setError(null);
    try {
      await budgetPlanningAPI.ceoReject(fiscalYear, rejectReason);
      setSuccess('Plans returned to CFO for revision');
      setRejectReason('');
      loadWorkflowStatus(); loadConsolidated();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'CEO rejection failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateScenario = async () => {
    if (!newScenarioName.trim()) return;
    try {
      await budgetPlanningAPI.createScenario(fiscalYear, { name: newScenarioName });
      setNewScenarioName('');
      loadScenarios();
      setSuccess('Scenario created');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create scenario');
    }
  };

  const getStepStatus = (step: number): string => {
    if (!workflowStatus) return 'PENDING';
    const counts = workflowStatus.status_counts || {};
    const total = workflowStatus.total_plans || 0;
    switch (step) {
      case 1: return total > 0 ? 'COMPLETED' : 'PENDING';
      case 2: return total > 0 ? 'COMPLETED' : 'PENDING';
      case 3: return total > 0 ? 'COMPLETED' : 'PENDING';
      case 4: return total > 0 ? 'COMPLETED' : 'PENDING';
      case 5: {
        const draft = counts.draft || 0;
        const submitted = counts.submitted || 0;
        if (draft > 0 || submitted > 0) return 'IN_PROGRESS';
        return total > 0 ? 'COMPLETED' : 'PENDING';
      }
      case 6: {
        const ceoApproved = counts.ceo_approved || 0;
        if (ceoApproved === total && total > 0) return 'COMPLETED';
        const cfoApproved = counts.cfo_approved || 0;
        if (cfoApproved > 0) return 'IN_PROGRESS';
        return 'PENDING';
      }
      case 7: {
        const exported = counts.exported || 0;
        if (exported === total && total > 0) return 'COMPLETED';
        if (exported > 0) return 'IN_PROGRESS';
        return 'PENDING';
      }
      default: return 'PENDING';
    }
  };

  const METHOD_INFO: Record<string, { label: string; icon: any; color: string; desc: string }> = {
    simple_average: { label: 'Simple Average', icon: BarChart3, color: 'blue', desc: 'Mean of historical values' },
    weighted_average: { label: 'Weighted Average', icon: TrendingUp, color: 'green', desc: 'Recent years weighted higher' },
    trend: { label: 'Trend Analysis', icon: ArrowRight, color: 'amber', desc: 'Linear trend projection' },
    ai_forecast: { label: 'AI Forecast (Prophet)', icon: Brain, color: 'purple', desc: 'Time-series decomposition with seasonality' },
    ml_trend: { label: 'ML Regression', icon: Calculator, color: 'pink', desc: 'Gradient boosting with feature engineering' },
  };

  const renderStepContent = () => {
    switch (activeStep) {

      // ===== STEP 1: DWH SOURCE SETUP =====
      case 1:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2"><Database className="w-5 h-5 text-blue-600" /> DWH Source Setup</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">DWH Connection</label>
                  <select value={selectedConnection || ''} onChange={(e) => setSelectedConnection(Number(e.target.value))} className="w-full border rounded-lg px-3 py-2">
                    <option value="">Select connection...</option>
                    {connections.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.database_name})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Source Table</label>
                  <div className="flex gap-2">
                    <select value={selectedTable} onChange={(e) => setSelectedTable(e.target.value)} className="flex-1 border rounded-lg px-3 py-2">
                      <option value="balans_ato">balans_ato (default)</option>
                      {dwhTables.filter(t => t !== 'balans_ato').map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <button onClick={handlePreviewSource} disabled={loading || !selectedConnection} className="px-3 py-2 bg-gray-100 border rounded-lg hover:bg-gray-200 disabled:opacity-50" title="Preview table">
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {previewData && (
                <div className="mt-4 space-y-3">
                  <h4 className="text-sm font-medium text-gray-700">Column Mapping</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                    {['coa_col', 'date_col', 'balance_col', 'currency_col', 'segment_col'].map((key) => (
                      <div key={key}>
                        <label className="block text-xs text-gray-500 mb-1">
                          {key === 'segment_col' ? 'Segment (optional)' : `${key.replace('_col', '').toUpperCase()} Column`}
                        </label>
                        <select value={columnMapping[key] || ''} onChange={(e) => setColumnMapping(prev => ({ ...prev, [key]: e.target.value }))} className="w-full border rounded px-2 py-1.5 text-sm">
                          <option value="">Auto-detect</option>
                          {previewData.columns?.map((c: string) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      </div>
                    ))}
                  </div>
                  <div className="max-h-48 overflow-auto border rounded">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          {previewData.columns?.slice(0, 8).map((c: string) => <th key={c} className="px-2 py-1 text-left font-medium">{c}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.sample?.slice(0, 10).map((row: any, i: number) => (
                          <tr key={i} className="border-t">
                            {previewData.columns?.slice(0, 8).map((c: string) => <td key={c} className="px-2 py-1 font-mono">{String(row[c] ?? '')}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Source Years</label>
                  <input type="text" value={sourceYears.join(', ')} disabled className="w-full border rounded-lg px-3 py-2 bg-gray-50" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Baseline Method</label>
                  <select value={calculationMethod} onChange={(e) => setCalculationMethod(e.target.value)} className="w-full border rounded-lg px-3 py-2">
                    {Object.entries(METHOD_INFO).map(([key, info]) => <option key={key} value={key}>{info.label}</option>)}
                  </select>
                </div>
                <div className="flex items-end gap-2">
                  <button onClick={handleInitialize} disabled={loading || !selectedConnection} className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2">
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
                    Initialize Budget Cycle
                  </button>
                  <button onClick={handleReset} disabled={loading} title={`FY ${fiscalYear} ma'lumotlarini tozalash`} className="bg-red-100 text-red-700 border border-red-300 px-3 py-2 rounded-lg hover:bg-red-200 disabled:opacity-50 flex items-center gap-1 text-sm font-medium whitespace-nowrap">
                    🗑 Reset FY {fiscalYear}
                  </button>
                </div>
              </div>
            </div>

            {workflowStatus && workflowStatus.total_plans > 0 && (
              <div className="bg-green-50 rounded-lg border border-green-200 p-4 flex items-center gap-2 text-green-800">
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">Budget cycle initialized - {workflowStatus.total_plans} department plans for FY {fiscalYear}</span>
              </div>
            )}
          </div>
        );

      // ===== STEP 2: BASELINE COMPARISON =====
      case 2:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2"><Brain className="w-5 h-5 text-purple-600" /> Baseline Comparison</h3>
                <button onClick={handleCompareBaselines} disabled={comparingBaselines} className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50">
                  {comparingBaselines ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
                  Compare All 5 Methods
                </button>
              </div>
              <p className="text-sm text-gray-600 mb-4">Compare baseline calculations across all methods including AI/ML to find the best fit.</p>

              <div className="grid grid-cols-5 gap-3 mb-6">
                {Object.entries(METHOD_INFO).map(([key, info]) => {
                  const Icon = info.icon;
                  const isSelected = calculationMethod === key;
                  return (
                    <button key={key} onClick={() => setCalculationMethod(key)}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${isSelected ? `border-${info.color}-500 bg-${info.color}-50` : 'border-gray-200 hover:border-gray-300'}`}>
                      <Icon className={`w-5 h-5 mb-1 text-${info.color}-600`} />
                      <div className="font-medium text-sm">{info.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{info.desc}</div>
                    </button>
                  );
                })}
              </div>

              {comparisonData && comparisonData.methods && (
                <div className="space-y-4">
                  <div className="grid grid-cols-5 gap-3">
                    {Object.entries(comparisonData.methods).map(([method, data]: [string, any]) => (
                      <div key={method} className="bg-gray-50 rounded-lg p-3 text-center">
                        <div className="text-xs text-gray-500 font-medium mb-1">{METHOD_INFO[method]?.label || method}</div>
                        <div className="text-lg font-bold text-gray-900">{formatNumber(data.total || 0)}</div>
                        <div className="text-xs text-gray-400">{data.group_count || 0} groups</div>
                        {data.status === 'error' && <div className="text-xs text-red-500 mt-1">Error</div>}
                      </div>
                    ))}
                  </div>

                  <div className="overflow-x-auto max-h-64">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-100 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left">Budgeting Group</th>
                          {Object.keys(comparisonData.methods).map(m => (
                            <th key={m} className="px-3 py-2 text-right text-xs">{METHOD_INFO[m]?.label || m}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(Object.values(comparisonData.methods)[0] as any)?.groups?.map((g: any, i: number) => (
                          <tr key={g.budgeting_group_id || i} className="border-t">
                            <td className="px-3 py-2 truncate max-w-[200px]">{g.budgeting_group_name}</td>
                            {Object.entries(comparisonData.methods).map(([m, data]: [string, any]) => (
                              <td key={m} className="px-3 py-2 text-right font-mono text-xs">
                                {formatNumber(data.groups?.[i]?.total || 0)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        );

      // ===== STEP 3: DEPARTMENT ASSIGNMENT =====
      case 3:
        return <DepartmentAssignmentStep fiscalYear={fiscalYear} onRefresh={loadWorkflowStatus} />;

      // ===== STEP 4: DRIVER SETUP =====
      case 4:
        return <DriverConfigPanel fiscalYear={fiscalYear} onApplied={loadWorkflowStatus} />;

      // ===== STEP 5: DEPARTMENT ENTRY =====
      case 5:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2"><FileSpreadsheet className="w-5 h-5 text-green-600" /> Product owner budget entry</h3>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Select product owner</label>
                <select value={selectedDepartment || ''} onChange={(e) => setSelectedDepartment(Number(e.target.value))} className="w-full max-w-md border rounded-lg px-3 py-2">
                  <option value="">Select unit...</option>
                  {departments.filter(d => d.is_active).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.primary_product_key
                        ? `${d.name_en} · ${d.primary_product_key}`
                        : `${d.name_en} (${d.code})`}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {selectedDepartment && (
              <DepartmentBudgetTemplate departmentId={selectedDepartment} fiscalYear={fiscalYear} onStatusChange={loadWorkflowStatus} />
            )}
          </div>
        );

      // ===== STEP 6: APPROVAL (3-tab) =====
      case 6:
        return <ApprovalStep
          fiscalYear={fiscalYear}
          workflowStatus={workflowStatus}
          consolidatedPlan={consolidatedPlan}
          loadConsolidated={loadConsolidated}
          onViewPlan={(deptId) => { setSelectedDepartment(deptId); setActiveStep(5); }}
          ceoComment={ceoComment}
          setCeoComment={setCeoComment}
          rejectReason={rejectReason}
          setRejectReason={setRejectReason}
          onCeoApprove={handleCeoApprove}
          onCeoReject={handleCeoReject}
          loading={loading}
          loadWorkflowStatus={loadWorkflowStatus}
        />;

      // ===== STEP 7: EXPORT & SCENARIOS =====
      case 7:
        return (
          <div className="space-y-4">
            {/* Export Panel */}
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2"><Upload className="w-5 h-5 text-indigo-600" /> Export to DWH</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target DWH Connection</label>
                  <select value={selectedConnection || ''} onChange={(e) => setSelectedConnection(Number(e.target.value))} className="w-full border rounded-lg px-3 py-2">
                    <option value="">Select connection...</option>
                    {connections.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.database_name})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target Table</label>
                  <input type="text" value={targetTable} onChange={(e) => setTargetTable(e.target.value)} className="w-full border rounded-lg px-3 py-2" />
                </div>
                <div className="flex items-end">
                  <button onClick={handleExport} disabled={loading || !selectedConnection || (workflowStatus?.ready_for_export || 0) === 0}
                    className="w-full bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2">
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    Export to DWH
                  </button>
                </div>
              </div>
              {workflowStatus && (
                <div className="grid grid-cols-4 gap-3">
                  <div className="bg-green-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-green-600">{workflowStatus.ready_for_export || 0}</div>
                    <div className="text-xs text-gray-600">Ready to Export</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-purple-600">{workflowStatus.status_counts?.exported || 0}</div>
                    <div className="text-xs text-gray-600">Exported</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-blue-600">{workflowStatus.status_counts?.ceo_approved || 0}</div>
                    <div className="text-xs text-gray-600">CEO Approved</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-gray-600">{workflowStatus.total_plans || 0}</div>
                    <div className="text-xs text-gray-600">Total Plans</div>
                  </div>
                </div>
              )}
            </div>

            {/* Fact Table Detail */}
            <div className="bg-white rounded-lg border p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Database className="w-5 h-5 text-teal-600" /> Account-Level Fact Table
                </h3>
                <button onClick={async () => {
                  try {
                    const summary = await budgetPlanningAPI.getFactTableSummary(fiscalYear);
                    setFactSummary(summary);
                  } catch { setFactSummary(null); }
                }} className="p-1.5 border rounded hover:bg-gray-50"><RefreshCw className="w-4 h-4" /></button>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Mirrors DWH source grain (1 row per COA account per month) with driver_code, driver_rate, and version columns.
                Written to <code className="bg-gray-100 px-1 rounded">{targetTable}_detail</code> in DWH and <code className="bg-gray-100 px-1 rounded">approved_budget_fact</code> locally.
                Ready for fact-vs-plan analysis and ML pipelines.
              </p>
              {factSummary && factSummary.total_rows > 0 ? (
                <div className="grid grid-cols-5 gap-3">
                  <div className="bg-teal-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-teal-700">{factSummary.total_rows.toLocaleString()}</div>
                    <div className="text-xs text-gray-600">Total Rows</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-blue-700">{factSummary.unique_accounts}</div>
                    <div className="text-xs text-gray-600">COA Accounts</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-purple-700">{factSummary.unique_departments}</div>
                    <div className="text-xs text-gray-600">Departments</div>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-3 text-center">
                    <div className="text-xl font-bold text-amber-700">{factSummary.unique_groups}</div>
                    <div className="text-xs text-gray-600">Budget Groups</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-xs font-mono text-gray-600 truncate" title={factSummary.latest_batch}>{factSummary.latest_batch}</div>
                    <div className="text-xs text-gray-600">Latest Batch</div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-400 text-center py-3">No fact data exported yet. Export will generate this automatically.</p>
              )}
            </div>

            {/* Scenarios */}
            <div className="bg-white rounded-lg border p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2"><GitBranch className="w-5 h-5 text-amber-600" /> What-If Scenarios</h3>
                <button onClick={loadScenarios} className="p-1.5 border rounded hover:bg-gray-50"><RefreshCw className="w-4 h-4" /></button>
              </div>
              <div className="flex gap-2 mb-4">
                <input type="text" value={newScenarioName} onChange={(e) => setNewScenarioName(e.target.value)} placeholder="Scenario name..." className="flex-1 border rounded-lg px-3 py-2 text-sm" />
                <button onClick={handleCreateScenario} disabled={!newScenarioName.trim()} className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-1">
                  <Plus className="w-4 h-4" /> Create
                </button>
              </div>
              {scenarios.length > 0 ? (
                <div className="space-y-2">
                  {scenarios.map((s) => (
                    <div key={s.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-gray-50">
                      <div>
                        <div className="font-medium text-sm">{s.name}</div>
                        <div className="text-xs text-gray-500">{s.scenario_type} - {s.status}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={s.status?.toUpperCase() || 'DRAFT'} />
                        <button onClick={async () => {
                          const data = await budgetPlanningAPI.compareScenario(s.id);
                          setSelectedScenario(s.id);
                          setScenarioComparison(data);
                        }} className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">Compare</button>
                        {s.status === 'draft' && (
                          <button onClick={async () => {
                            await budgetPlanningAPI.approveScenario(s.id);
                            loadScenarios();
                            setSuccess('Scenario approved');
                          }} className="px-2 py-1 text-xs bg-green-50 text-green-700 rounded hover:bg-green-100">Approve</button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">No scenarios created yet. Create one to model what-if adjustments.</p>
              )}
              {scenarioComparison && (
                <div className="mt-4 p-3 bg-gray-50 rounded-lg border">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium text-sm">{scenarioComparison.scenario_name} - Comparison</h4>
                    <button onClick={() => setScenarioComparison(null)} className="p-1 hover:bg-gray-200 rounded"><X className="w-3 h-3" /></button>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="text-center p-2 bg-white rounded">
                      <div className="text-xs text-gray-500">Original</div>
                      <div className="font-bold">{formatNumber(scenarioComparison.total_original || 0)}</div>
                    </div>
                    <div className="text-center p-2 bg-white rounded">
                      <div className="text-xs text-gray-500">Scenario</div>
                      <div className="font-bold">{formatNumber(scenarioComparison.total_scenario || 0)}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        );

      default: return null;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budget Planning Workflow</h1>
          <p className="text-gray-600">Professional FP&A Budget Planning with AI/ML</p>
        </div>
        <div className="flex items-center gap-4">
          <select value={fiscalYear} onChange={(e) => setFiscalYear(Number(e.target.value))} className="border rounded-lg px-4 py-2">
            <option value={2028}>FY 2028</option>
            <option value={2027}>FY 2027</option>
            <option value={2026}>FY 2026</option>
          </select>
          <button onClick={loadWorkflowStatus} className="p-2 border rounded-lg hover:bg-gray-50" title="Refresh"><RefreshCw className="w-5 h-5" /></button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" /> <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5 flex-shrink-0" /> <span className="flex-1">{success}</span>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      <div className="grid grid-cols-7 gap-2">
        <StepCard step={1} title="Source" description="DWH table & mapping" status={getStepStatus(1)} icon={<Database className="w-4 h-4" />} isActive={activeStep === 1} onClick={() => setActiveStep(1)}
          stats={workflowStatus?.total_plans ? <div className="text-xs text-gray-500">{workflowStatus.total_plans} plans</div> : null} />
        <StepCard step={2} title="Baseline" description="AI/ML comparison" status={getStepStatus(2)} icon={<Brain className="w-4 h-4" />} isActive={activeStep === 2} onClick={() => setActiveStep(2)} stats={null} />
        <StepCard step={3} title="Assign" description="Product owners" status={getStepStatus(3)} icon={<Building2 className="w-4 h-4" />} isActive={activeStep === 3} onClick={() => { setActiveStep(3); loadAssignments(); }}
          stats={departments.length > 0 ? <div className="text-xs text-gray-500">{departments.length} units</div> : null} />
        <StepCard step={4} title="Drivers" description="CFO driver setup" status={getStepStatus(4)} icon={<Calculator className="w-4 h-4" />} isActive={activeStep === 4} onClick={() => setActiveStep(4)} stats={null} />
        <StepCard step={5} title="Entry" description="Dept budget edit" status={getStepStatus(5)} icon={<FileSpreadsheet className="w-4 h-4" />} isActive={activeStep === 5} onClick={() => setActiveStep(5)}
          stats={workflowStatus?.status_counts ? <div className="text-xs text-gray-500">{workflowStatus.status_counts.submitted || 0} submitted</div> : null} />
        <StepCard step={6} title="Approve" description="Dept → CFO → CEO" status={getStepStatus(6)} icon={<ClipboardCheck className="w-4 h-4" />} isActive={activeStep === 6} onClick={() => { setActiveStep(6); loadConsolidated(); }}
          stats={workflowStatus?.status_counts ? <div className="text-xs text-gray-500">{(workflowStatus.status_counts.ceo_approved || 0) + (workflowStatus.status_counts.cfo_approved || 0)} approved</div> : null} />
        <StepCard step={7} title="Export" description="DWH & scenarios" status={getStepStatus(7)} icon={<Upload className="w-4 h-4" />} isActive={activeStep === 7} onClick={() => { setActiveStep(7); loadScenarios(); }}
          stats={workflowStatus?.ready_for_export ? <div className="text-xs text-gray-500">{workflowStatus.ready_for_export} ready</div> : null} />
      </div>

      <div className="bg-gray-50 rounded-lg p-6">{renderStepContent()}</div>
    </div>
  );
};


// ============================================================================
// Step 3: Department Assignment Sub-Component
// ============================================================================
const DepartmentAssignmentStep: React.FC<{ fiscalYear: number; onRefresh: () => void }> = ({ fiscalYear, onRefresh }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [edits, setEdits] = useState<Record<number, { groupIds: number[]; canEdit: boolean }>>({});
  const [msg, setMsg] = useState<string | null>(null);
  /** Prefer FP&A taxonomy product owners (Loans, Deposits, …); turn off to see legacy org units (TREASURY, …). */
  const [productOwnersOnly, setProductOwnersOnly] = useState(true);

  useEffect(() => {
    setLoading(true);
    budgetPlanningAPI.getDepartmentAssignments(fiscalYear, productOwnersOnly)
      .then((d) => {
        setData(d);
        const init: Record<number, { groupIds: number[]; canEdit: boolean }> = {};
        for (const dept of d.departments || []) {
          init[dept.id] = {
            groupIds: (dept.assigned_groups || []).map((g: any) => g.budgeting_group_id),
            canEdit: (dept.assigned_groups || [])[0]?.can_edit ?? true,
          };
        }
        setEdits(init);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [fiscalYear, productOwnersOnly]);

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      const assignments = (data?.departments || []).map((dept: any) => {
        const val = edits[dept.id];
        return {
          department_id: dept.id,
          budgeting_group_ids: val?.groupIds ?? [],
          can_edit: val?.canEdit ?? true,
          can_submit: val?.canEdit ?? true,
        };
      });
      await budgetPlanningAPI.assignDepartmentsV2(fiscalYear, assignments, true);
      setMsg('Assignments saved and notifications sent');
      onRefresh();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
          <div>
            <h3 className="font-semibold flex items-center gap-2"><Building2 className="w-5 h-5 text-green-600" /> Product owner assignment</h3>
            <p className="text-xs text-gray-500 mt-1 max-w-xl">
              Units are FP&A taxonomy product owners (e.g. Loans, Deposits). Legacy org codes (Treasury, Retail, …) are hidden when the filter below is on — use <strong>Budget Structure → Product owners → Seed from taxonomy</strong> to create them.
            </p>
          </div>
          <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 shrink-0">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Assign & Notify
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 mb-3 cursor-pointer select-none">
          <input
            type="checkbox"
            className="rounded border-gray-300 text-green-600 focus:ring-green-500"
            checked={productOwnersOnly}
            onChange={(e) => setProductOwnersOnly(e.target.checked)}
          />
          <span>Show only FP&amp;A product owners (hide legacy department codes)</span>
        </label>
        {productOwnersOnly && (data?.departments || []).length === 0 && !loading && (
          <div className="text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded-lg px-3 py-2 mb-3">
            No product-owner departments found. Open <strong>Budget Structure</strong>, tab <strong>Product owners</strong>, and click <strong>Seed from taxonomy</strong>, then refresh this step. Or turn off the filter above to work with existing org units.
          </div>
        )}
        {msg && <div className={`text-sm px-3 py-2 rounded mb-3 ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{msg}</div>}

        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Product owner</th>
                <th className="px-3 py-2 text-center font-medium">Coverage</th>
                <th className="px-3 py-2 text-center font-medium">Edit Permission</th>
                <th className="px-3 py-2 text-center font-medium">Plan Status</th>
              </tr>
            </thead>
            <tbody>
              {(data?.departments || []).map((dept: any) => (
                <tr key={dept.id} className="border-t">
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-900">{dept.name_en}</div>
                    {dept.primary_product_key ? (
                      <div className="text-xs text-primary-700 font-mono mt-0.5">
                        {dept.primary_product_key}
                        {dept.product_label_en ? ` · ${dept.product_label_en}` : ''}
                        {dept.product_pillar ? <span className="text-gray-500"> ({dept.product_pillar})</span> : null}
                      </div>
                    ) : null}
                    <div className="text-xs text-gray-500">{dept.code}</div>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <div className="flex flex-wrap justify-center gap-1">
                      <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                        {edits[dept.id]?.groupIds.length || 0} CBU groups
                      </span>
                      {(dept.product_keys?.length ?? 0) > 0 && (
                        <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded text-xs font-medium" title={dept.product_keys?.join(', ')}>
                          {dept.product_keys.length} FP&amp;A product{dept.product_keys.length === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button onClick={() => setEdits(prev => ({
                      ...prev,
                      [dept.id]: { ...prev[dept.id], canEdit: !prev[dept.id]?.canEdit }
                    }))} className={`px-3 py-1 rounded text-xs font-medium ${edits[dept.id]?.canEdit ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {edits[dept.id]?.canEdit ? 'Can Edit' : 'View Only'}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-center">
                    {dept.plan_status ? <StatusBadge status={dept.plan_status.toUpperCase()} /> : <span className="text-gray-400 text-xs">No plan</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


// ============================================================================
// Step 6: Approval Sub-Component (3 tabs)
// ============================================================================
const ApprovalStep: React.FC<{
  fiscalYear: number;
  workflowStatus: WorkflowStatus | null;
  consolidatedPlan: any;
  loadConsolidated: () => void;
  onViewPlan: (deptId: number) => void;
  ceoComment: string;
  setCeoComment: (v: string) => void;
  rejectReason: string;
  setRejectReason: (v: string) => void;
  onCeoApprove: () => void;
  onCeoReject: () => void;
  loading: boolean;
  loadWorkflowStatus: () => void;
}> = ({ fiscalYear, workflowStatus, consolidatedPlan, loadConsolidated, onViewPlan, ceoComment, setCeoComment, rejectReason, setRejectReason, onCeoApprove, onCeoReject, loading, loadWorkflowStatus }) => {
  const [tab, setTab] = useState<'dept' | 'cfo' | 'ceo'>('dept');

  useEffect(() => { loadConsolidated(); }, [loadConsolidated]);

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border">
        <div className="flex border-b">
          {[
            { key: 'dept', label: 'Department Review', icon: Users },
            { key: 'cfo', label: 'CFO Review', icon: Shield },
            { key: 'ceo', label: 'CEO Sign-off', icon: ClipboardCheck },
          ].map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setTab(key as any)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${tab === key ? 'border-blue-500 text-blue-700 bg-blue-50' : 'border-transparent text-gray-600 hover:text-gray-800'}`}>
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {tab === 'dept' && (
            <BudgetApprovalDashboard fiscalYear={fiscalYear} onViewPlan={onViewPlan} />
          )}

          {tab === 'cfo' && (
            <BudgetApprovalDashboard fiscalYear={fiscalYear} onViewPlan={onViewPlan} />
          )}

          {tab === 'ceo' && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg flex items-center gap-2"><ClipboardCheck className="w-5 h-5 text-amber-600" /> CEO Consolidated Sign-off</h3>

              {consolidatedPlan ? (
                <>
                  <div className="grid grid-cols-4 gap-3">
                    <div className="bg-blue-50 rounded-lg p-3 text-center">
                      <div className="text-xl font-bold text-blue-700">{formatNumber(consolidatedPlan.grand_baseline || 0)}</div>
                      <div className="text-xs text-gray-600">Total Baseline</div>
                    </div>
                    <div className="bg-green-50 rounded-lg p-3 text-center">
                      <div className="text-xl font-bold text-green-700">{formatNumber(consolidatedPlan.grand_adjusted || 0)}</div>
                      <div className="text-xs text-gray-600">Total Adjusted</div>
                    </div>
                    <div className="bg-amber-50 rounded-lg p-3 text-center">
                      <div className="text-xl font-bold text-amber-700">{formatNumber(consolidatedPlan.grand_variance || 0)}</div>
                      <div className="text-xs text-gray-600">Variance</div>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-3 text-center">
                      <div className="text-xl font-bold text-purple-700">{consolidatedPlan.ready_for_ceo || 0}</div>
                      <div className="text-xs text-gray-600">Ready for Sign-off</div>
                    </div>
                  </div>

                  {consolidatedPlan.bs_class_totals?.length > 0 && (
                    <div className="bg-gray-50 rounded-lg border p-3">
                      <h4 className="font-medium text-sm mb-2">By BS Class</h4>
                      <table className="w-full text-sm">
                        <thead className="bg-white">
                          <tr>
                            <th className="px-3 py-1 text-left font-medium">BS Class</th>
                            <th className="px-3 py-1 text-right font-medium">Baseline</th>
                            <th className="px-3 py-1 text-right font-medium">Adjusted</th>
                            <th className="px-3 py-1 text-right font-medium">Variance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {consolidatedPlan.bs_class_totals.map((c: any) => (
                            <tr key={c.bs_class} className="border-t">
                              <td className="px-3 py-1.5">{c.bs_class}</td>
                              <td className="px-3 py-1.5 text-right font-mono">{formatNumber(c.baseline)}</td>
                              <td className="px-3 py-1.5 text-right font-mono">{formatNumber(c.adjusted)}</td>
                              <td className={`px-3 py-1.5 text-right font-mono ${c.variance >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatNumber(c.variance)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {consolidatedPlan.departments?.length > 0 && (
                    <div className="bg-gray-50 rounded-lg border p-3">
                      <h4 className="font-medium text-sm mb-2">Department Breakdown</h4>
                      <div className="space-y-1">
                        {consolidatedPlan.departments.map((d: any) => (
                          <div key={d.department_id} className="flex items-center justify-between p-2 bg-white rounded">
                            <div>
                              <span className="font-medium text-sm">{d.department_name}</span>
                              <span className="ml-2 text-xs text-gray-500">{d.department_code}</span>
                            </div>
                            <div className="flex items-center gap-4 text-sm">
                              <span className="font-mono">{formatNumber(d.total_adjusted)}</span>
                              <span className={`font-mono text-xs ${d.total_variance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {d.total_variance >= 0 ? '+' : ''}{formatNumber(d.total_variance)}
                              </span>
                              <StatusBadge status={d.status?.toUpperCase() || 'DRAFT'} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t pt-4 space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">CEO Notes (optional)</label>
                      <textarea value={ceoComment} onChange={(e) => setCeoComment(e.target.value)} rows={2} placeholder="Add your notes..." className="w-full border rounded-lg px-3 py-2 text-sm" />
                    </div>
                    <div className="flex gap-3">
                      <button onClick={onCeoApprove} disabled={loading || (consolidatedPlan.ready_for_ceo || 0) === 0}
                        className="flex items-center gap-2 px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                        Approve Entire Plan
                      </button>
                      <div className="flex-1 flex items-center gap-2">
                        <input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Rejection reason..." className="flex-1 border rounded-lg px-3 py-2 text-sm" />
                        <button onClick={onCeoReject} disabled={loading || !rejectReason.trim()}
                          className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium">
                          <X className="w-4 h-4" /> Reject
                        </button>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-600" />
                  Loading consolidated plan...
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BudgetPlanningNew;
