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
} from 'lucide-react';
import { baselineAPI, connectionsAPI } from '../services/api';

interface WorkflowStatus {
  fiscal_year: number;
  steps: {
    '1_ingest': { status: string; accounts: number; records: number; date_range: string | null };
    '2_calculate': { status: string; baselines: number; total_amount: number };
    '3_plan': { status: string; by_status: Record<string, { count: number; amount: number }> };
    '4_export': { status: string; exported: number };
  };
}

interface Connection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  database_name: string;
  is_active: boolean;
}

interface BaselineData {
  id: number;
  account_code: string;
  snapshot_date: string;
  fiscal_year: number;
  fiscal_month: number;
  currency: string;
  balance: number;
  balance_uzs: number;
}

interface Baseline {
  id: number;
  account_code: string;
  currency: string;
  monthly: Record<string, number>;
  annual_total: number;
  calculation_method: string;
  source_years: string;
  yoy_growth_rate: number | null;
}

interface PlannedBudget {
  id: number;
  budget_code: string;
  account_code: string;
  department: string | null;
  currency: string;
  monthly: Record<string, number>;
  annual_total: number;
  baseline_amount: number;
  driver_adjustment_pct: number;
  variance_from_baseline: number;
  variance_pct: number;
  scenario: string;
  status: string;
  submitted_at: string | null;
  approved_at: string | null;
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
    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
      isActive
        ? 'border-blue-500 bg-blue-50'
        : status === 'COMPLETED'
        ? 'border-green-200 bg-green-50'
        : 'border-gray-200 bg-white hover:border-gray-300'
    }`}
  >
    <div className="flex items-start gap-3">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center ${
          status === 'COMPLETED' ? 'bg-green-500 text-white' : isActive ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-600'
        }`}
      >
        {status === 'COMPLETED' ? <CheckCircle className="w-5 h-5" /> : icon}
      </div>
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Step {step}: {title}</h3>
          <StatusBadge status={status} />
        </div>
        <p className="text-sm text-gray-600 mt-1">{description}</p>
        {stats && <div className="mt-2">{stats}</div>}
      </div>
    </div>
  </div>
);

const BudgetPlanning: React.FC = () => {
  const [fiscalYear, setFiscalYear] = useState(2026);
  const [activeStep, setActiveStep] = useState(1);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Step-specific data
  const [baselineData, setBaselineData] = useState<{ total: number; data: BaselineData[] } | null>(null);
  const [baselines, setBaselines] = useState<{ total: number; data: Baseline[] } | null>(null);
  const [plannedBudgets, setPlannedBudgets] = useState<{ total: number; data: PlannedBudget[] } | null>(null);

  // Filters
  const [accountFilter, setAccountFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [driverAdjustment, setDriverAdjustment] = useState(0);

  const loadWorkflowStatus = useCallback(async () => {
    try {
      const status = await baselineAPI.getWorkflowStatus(fiscalYear);
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

  useEffect(() => {
    loadWorkflowStatus();
    loadConnections();
  }, [loadWorkflowStatus, loadConnections]);

  // Step 1: Ingest
  const handleIngest = async () => {
    if (!selectedConnection) {
      setError('Please select a DWH connection');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await baselineAPI.ingest({
        connection_id: selectedConnection,
        start_year: fiscalYear - 3,
        end_year: fiscalYear - 1,
      });
      setSuccess(`Ingested ${result.records_imported} records from ${result.unique_accounts} accounts`);
      loadWorkflowStatus();
      loadBaselineData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Ingestion failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const loadBaselineData = async () => {
    try {
      const data = await baselineAPI.getBaselineData({
        fiscal_year: fiscalYear - 1,
        account_code: accountFilter || undefined,
        limit: 50,
      });
      setBaselineData(data);
    } catch (err) {
      console.error('Failed to load baseline data:', err);
    }
  };

  // Step 2: Calculate
  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await baselineAPI.calculate({
        fiscal_year: fiscalYear,
        method: 'simple_average',
        source_years: [fiscalYear - 3, fiscalYear - 2, fiscalYear - 1],
      });
      setSuccess(`Created ${result.baselines_created} baseline budgets for ${fiscalYear}`);
      loadWorkflowStatus();
      loadBaselines();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Calculation failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const loadBaselines = async () => {
    try {
      const data = await baselineAPI.listBaselines({
        fiscal_year: fiscalYear,
        account_code: accountFilter || undefined,
        limit: 50,
      });
      setBaselines(data);
    } catch (err) {
      console.error('Failed to load baselines:', err);
    }
  };

  // Step 3: Plan
  const handleBulkCreatePlanned = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await baselineAPI.bulkCreatePlanned({
        fiscal_year: fiscalYear,
        driver_adjustment_pct: driverAdjustment / 100,
        scenario: 'BASE',
      });
      setSuccess(`Created ${result.budgets_created} planned budgets`);
      loadWorkflowStatus();
      loadPlannedBudgets();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Creation failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const loadPlannedBudgets = async () => {
    try {
      const data = await baselineAPI.listPlanned({
        fiscal_year: fiscalYear,
        status: statusFilter || undefined,
        account_code: accountFilter || undefined,
        limit: 50,
      });
      setPlannedBudgets(data);
    } catch (err) {
      console.error('Failed to load planned budgets:', err);
    }
  };

  const handleSubmit = async (budgetCode: string) => {
    try {
      await baselineAPI.submitPlanned(budgetCode);
      setSuccess('Budget submitted for approval');
      loadPlannedBudgets();
      loadWorkflowStatus();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Submit failed';
      setError(message);
    }
  };

  const handleApprove = async (budgetCode: string) => {
    try {
      await baselineAPI.approvePlanned(budgetCode);
      setSuccess('Budget approved');
      loadPlannedBudgets();
      loadWorkflowStatus();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Approval failed';
      setError(message);
    }
  };

  // Step 4: Export
  const handleExport = async () => {
    if (!selectedConnection) {
      setError('Please select a DWH connection');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await baselineAPI.exportToDWH({
        connection_id: selectedConnection,
        fiscal_year: fiscalYear,
        target_table: 'fpna_budget_planned',
        status_filter: 'APPROVED',
      });
      setSuccess(`Exported ${result.budgets_exported} budgets to DWH`);
      loadWorkflowStatus();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Export failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Load step-specific data when step changes
  useEffect(() => {
    if (activeStep === 1) loadBaselineData();
    else if (activeStep === 2) loadBaselines();
    else if (activeStep === 3) loadPlannedBudgets();
  }, [activeStep, fiscalYear, accountFilter, statusFilter]);

  const renderStepContent = () => {
    switch (activeStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Ingest Historical Data from DWH</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">DWH Connection</label>
                  <select
                    value={selectedConnection || ''}
                    onChange={(e) => setSelectedConnection(Number(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.database_name})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Source Years</label>
                  <input
                    type="text"
                    value={`${fiscalYear - 3} - ${fiscalYear - 1}`}
                    disabled
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleIngest}
                    disabled={loading || !selectedConnection}
                    className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                    Run Ingestion
                  </button>
                </div>
              </div>
            </div>

            {baselineData && (
              <div className="bg-white rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Imported Data Preview ({baselineData.total} records)</h3>
                  <div className="flex items-center gap-2">
                    <Search className="w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Filter by account..."
                      value={accountFilter}
                      onChange={(e) => setAccountFilter(e.target.value)}
                      className="border rounded px-2 py-1 text-sm"
                    />
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left">Account</th>
                        <th className="px-3 py-2 text-left">Date</th>
                        <th className="px-3 py-2 text-left">Year</th>
                        <th className="px-3 py-2 text-left">Month</th>
                        <th className="px-3 py-2 text-right">Balance (UZS)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {baselineData.data.map((row) => (
                        <tr key={row.id} className="border-t">
                          <td className="px-3 py-2 font-mono">{row.account_code}</td>
                          <td className="px-3 py-2">{row.snapshot_date}</td>
                          <td className="px-3 py-2">{row.fiscal_year}</td>
                          <td className="px-3 py-2">{row.fiscal_month}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(row.balance_uzs)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Calculate Baseline Budgets for {fiscalYear}</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Calculation Method</label>
                  <select className="w-full border rounded-lg px-3 py-2">
                    <option value="simple_average">Simple Average</option>
                    <option value="weighted_average">Weighted Average</option>
                    <option value="trend">Trend-based</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Source Years</label>
                  <input
                    type="text"
                    value={`${fiscalYear - 3}, ${fiscalYear - 2}, ${fiscalYear - 1}`}
                    disabled
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleCalculate}
                    disabled={loading}
                    className="w-full bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                    Calculate Baselines
                  </button>
                </div>
              </div>
            </div>

            {baselines && (
              <div className="bg-white rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Calculated Baselines ({baselines.total} accounts)</h3>
                  <div className="flex items-center gap-2">
                    <Search className="w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Filter by account..."
                      value={accountFilter}
                      onChange={(e) => setAccountFilter(e.target.value)}
                      className="border rounded px-2 py-1 text-sm"
                    />
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left">Account</th>
                        <th className="px-3 py-2 text-right">Jan</th>
                        <th className="px-3 py-2 text-right">Feb</th>
                        <th className="px-3 py-2 text-right">Mar</th>
                        <th className="px-3 py-2 text-right">Q1</th>
                        <th className="px-3 py-2 text-right">Annual</th>
                        <th className="px-3 py-2 text-right">YoY %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {baselines.data.map((row) => (
                        <tr key={row.id} className="border-t">
                          <td className="px-3 py-2 font-mono">{row.account_code}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(row.monthly.jan)}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(row.monthly.feb)}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(row.monthly.mar)}</td>
                          <td className="px-3 py-2 text-right font-medium">
                            {formatNumber(row.monthly.jan + row.monthly.feb + row.monthly.mar)}
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatNumber(row.annual_total)}</td>
                          <td className="px-3 py-2 text-right">
                            {row.yoy_growth_rate !== null ? (
                              <span className={row.yoy_growth_rate >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {(row.yoy_growth_rate * 100).toFixed(1)}%
                              </span>
                            ) : (
                              '-'
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Create Planned Budgets with Driver Adjustments</h3>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Driver Adjustment (%)</label>
                  <input
                    type="number"
                    value={driverAdjustment}
                    onChange={(e) => setDriverAdjustment(Number(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2"
                    placeholder="e.g., 5 for 5% increase"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Scenario</label>
                  <select className="w-full border rounded-lg px-3 py-2">
                    <option value="BASE">Base</option>
                    <option value="OPTIMISTIC">Optimistic</option>
                    <option value="PESSIMISTIC">Pessimistic</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleBulkCreatePlanned}
                    disabled={loading}
                    className="w-full bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
                    Create Planned Budgets
                  </button>
                </div>
                <div className="flex items-end">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="">All Statuses</option>
                    <option value="DRAFT">Draft</option>
                    <option value="SUBMITTED">Submitted</option>
                    <option value="APPROVED">Approved</option>
                    <option value="EXPORTED">Exported</option>
                  </select>
                </div>
              </div>
            </div>

            {plannedBudgets && (
              <div className="bg-white rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Planned Budgets ({plannedBudgets.total} items)</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left">Account</th>
                        <th className="px-3 py-2 text-right">Baseline</th>
                        <th className="px-3 py-2 text-right">Planned</th>
                        <th className="px-3 py-2 text-right">Adj %</th>
                        <th className="px-3 py-2 text-right">Variance</th>
                        <th className="px-3 py-2 text-center">Status</th>
                        <th className="px-3 py-2 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plannedBudgets.data.map((row) => (
                        <tr key={row.id} className="border-t">
                          <td className="px-3 py-2 font-mono">{row.account_code}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(row.baseline_amount)}</td>
                          <td className="px-3 py-2 text-right font-medium">{formatNumber(row.annual_total)}</td>
                          <td className="px-3 py-2 text-right">{(row.driver_adjustment_pct * 100).toFixed(1)}%</td>
                          <td className="px-3 py-2 text-right">
                            <span className={row.variance_from_baseline >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {formatNumber(row.variance_from_baseline)} ({row.variance_pct.toFixed(1)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center">
                            <StatusBadge status={row.status} />
                          </td>
                          <td className="px-3 py-2 text-center">
                            <div className="flex items-center justify-center gap-1">
                              {row.status === 'DRAFT' && (
                                <button
                                  onClick={() => handleSubmit(row.budget_code)}
                                  className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                                  title="Submit for approval"
                                >
                                  <Send className="w-4 h-4" />
                                </button>
                              )}
                              {row.status === 'SUBMITTED' && (
                                <button
                                  onClick={() => handleApprove(row.budget_code)}
                                  className="p-1 text-green-600 hover:bg-green-50 rounded"
                                  title="Approve"
                                >
                                  <Check className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        );

      case 4:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Export Approved Budgets to DWH</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target DWH Connection</label>
                  <select
                    value={selectedConnection || ''}
                    onChange={(e) => setSelectedConnection(Number(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="">Select connection...</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.database_name})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target Table</label>
                  <input
                    type="text"
                    value="fpna_budget_planned"
                    disabled
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleExport}
                    disabled={loading || !selectedConnection}
                    className="w-full bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    Export to DWH
                  </button>
                </div>
              </div>
            </div>

            {workflowStatus && (
              <div className="bg-white rounded-lg border p-4">
                <h3 className="font-semibold mb-4">Export Summary</h3>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {workflowStatus.steps['3_plan'].by_status?.APPROVED?.count || 0}
                    </div>
                    <div className="text-sm text-gray-600">Ready to Export</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {workflowStatus.steps['4_export'].exported}
                    </div>
                    <div className="text-sm text-gray-600">Already Exported</div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {formatNumber(workflowStatus.steps['3_plan'].by_status?.APPROVED?.amount || 0)}
                    </div>
                    <div className="text-sm text-gray-600">Total Amount</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">{fiscalYear}</div>
                    <div className="text-sm text-gray-600">Fiscal Year</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budget Planning Workflow</h1>
          <p className="text-gray-600">DWH → Baseline → Planned Budget → Export</p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={fiscalYear}
            onChange={(e) => setFiscalYear(Number(e.target.value))}
            className="border rounded-lg px-4 py-2"
          >
            <option value={2026}>FY 2026</option>
            <option value={2025}>FY 2025</option>
            <option value={2024}>FY 2024</option>
          </select>
          <button
            onClick={loadWorkflowStatus}
            className="p-2 border rounded-lg hover:bg-gray-50"
            title="Refresh status"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5" />
          {success}
          <button onClick={() => setSuccess(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Workflow Steps */}
      <div className="grid grid-cols-4 gap-4">
        <StepCard
          step={1}
          title="Ingest"
          description="Import 3-year historical data from DWH"
          status={workflowStatus?.steps['1_ingest'].status || 'PENDING'}
          icon={<Database className="w-5 h-5" />}
          isActive={activeStep === 1}
          onClick={() => setActiveStep(1)}
          stats={
            workflowStatus?.steps['1_ingest'].accounts ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.steps['1_ingest'].accounts} accounts, {workflowStatus.steps['1_ingest'].records} records
              </div>
            ) : null
          }
        />
        <StepCard
          step={2}
          title="Calculate"
          description="Generate baseline budgets using averages"
          status={workflowStatus?.steps['2_calculate'].status || 'PENDING'}
          icon={<Calculator className="w-5 h-5" />}
          isActive={activeStep === 2}
          onClick={() => setActiveStep(2)}
          stats={
            workflowStatus?.steps['2_calculate'].baselines ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.steps['2_calculate'].baselines} baselines, {formatNumber(workflowStatus.steps['2_calculate'].total_amount)}
              </div>
            ) : null
          }
        />
        <StepCard
          step={3}
          title="Plan"
          description="Apply driver adjustments and approve"
          status={workflowStatus?.steps['3_plan'].status || 'PENDING'}
          icon={<FileSpreadsheet className="w-5 h-5" />}
          isActive={activeStep === 3}
          onClick={() => setActiveStep(3)}
          stats={
            workflowStatus?.steps['3_plan'].by_status ? (
              <div className="text-xs text-gray-500">
                {Object.entries(workflowStatus.steps['3_plan'].by_status).map(([status, data]) => (
                  <span key={status} className="mr-2">
                    {status}: {data.count}
                  </span>
                ))}
              </div>
            ) : null
          }
        />
        <StepCard
          step={4}
          title="Export"
          description="Send approved budgets to DWH"
          status={workflowStatus?.steps['4_export'].status || 'PENDING'}
          icon={<Upload className="w-5 h-5" />}
          isActive={activeStep === 4}
          onClick={() => setActiveStep(4)}
          stats={
            workflowStatus?.steps['4_export'].exported ? (
              <div className="text-xs text-gray-500">{workflowStatus.steps['4_export'].exported} exported</div>
            ) : null
          }
        />
      </div>

      {/* Step Content */}
      <div className="bg-gray-50 rounded-lg p-6">{renderStepContent()}</div>
    </div>
  );
};

export default BudgetPlanning;
