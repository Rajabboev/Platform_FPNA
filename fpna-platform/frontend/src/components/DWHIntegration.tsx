import React, { useState, useEffect } from 'react';
import {
  Database, Download, Upload, RefreshCw, AlertTriangle, CheckCircle,
  Clock, Play, ArrowRight, ArrowLeft, Table, Columns, Eye, Settings,
  Bell, AlertCircle, TrendingUp, TrendingDown, FileText, History,
  GitBranch, Target, Zap, Filter, ChevronDown, ChevronRight
} from 'lucide-react';
import { dwhIntegrationAPI, connectionsAPI, budgetAPI } from '../services/api';

// Shared UI Components
const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
  </div>
);

const ErrorMessage = ({ message }: { message: string }) => (
  <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
    <AlertCircle className="w-5 h-5" />
    <span>{message}</span>
  </div>
);

const SuccessMessage = ({ message }: { message: string }) => (
  <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
    <CheckCircle className="w-5 h-5" />
    <span>{message}</span>
  </div>
);

const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-white rounded-xl shadow-sm border border-gray-200 ${className}`}>
    {children}
  </div>
);

const PageHeader = ({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) => (
  <div className="flex justify-between items-start mb-6">
    <div>
      <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      {subtitle && <p className="text-gray-500 mt-1">{subtitle}</p>}
    </div>
    {actions && <div className="flex gap-2">{actions}</div>}
  </div>
);

const TabButton = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
  <button
    onClick={onClick}
    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      active
        ? 'bg-blue-600 text-white'
        : 'text-gray-600 hover:bg-gray-100'
    }`}
  >
    {children}
  </button>
);

const StatCard = ({ label, value, icon: Icon, trend, color = 'blue' }: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  trend?: { value: number; label: string };
  color?: string;
}) => {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <div className="bg-white rounded-xl p-4 border border-gray-200">
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg ${colors[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <div className={`flex items-center text-sm ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend.value >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
            {Math.abs(trend.value)}%
          </div>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  );
};

// ============================================
// DWH Integration Page
// ============================================
export const DWHIntegrationPage = () => {
  const [activeTab, setActiveTab] = useState<'ingestion' | 'egress' | 'alerts' | 'audit'>('ingestion');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  return (
    <div className="p-6">
      <PageHeader
        title="DWH Integration"
        subtitle="Bidirectional ETL between Data Warehouse and FP&A Platform"
      />

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card className="mb-6">
        <div className="p-4 border-b border-gray-200">
          <div className="flex gap-2">
            <TabButton active={activeTab === 'ingestion'} onClick={() => setActiveTab('ingestion')}>
              <div className="flex items-center gap-2">
                <Download className="w-4 h-4" />
                Ingestion (DWH → Platform)
              </div>
            </TabButton>
            <TabButton active={activeTab === 'egress'} onClick={() => setActiveTab('egress')}>
              <div className="flex items-center gap-2">
                <Upload className="w-4 h-4" />
                Egress (Platform → DWH)
              </div>
            </TabButton>
            <TabButton active={activeTab === 'alerts'} onClick={() => setActiveTab('alerts')}>
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4" />
                Variance Alerts
              </div>
            </TabButton>
            <TabButton active={activeTab === 'audit'} onClick={() => setActiveTab('audit')}>
              <div className="flex items-center gap-2">
                <History className="w-4 h-4" />
                Audit Trail
              </div>
            </TabButton>
          </div>
        </div>

        <div className="p-6">
          {activeTab === 'ingestion' && <IngestionPanel setError={setError} setSuccess={setSuccess} />}
          {activeTab === 'egress' && <EgressPanel setError={setError} setSuccess={setSuccess} />}
          {activeTab === 'alerts' && <AlertsPanel setError={setError} setSuccess={setSuccess} />}
          {activeTab === 'audit' && <AuditPanel />}
        </div>
      </Card>
    </div>
  );
};

// Currency code mapping
const CURRENCY_CODES: Record<number, string> = {
  0: 'UZS', 860: 'UZS', 840: 'USD', 978: 'EUR', 643: 'RUB',
  756: 'CHF', 826: 'GBP', 392: 'JPY', 156: 'CNY', 398: 'KZT'
};

// ============================================
// Ingestion Panel (DWH -> Platform)
// ============================================
const IngestionPanel = ({ setError, setSuccess }: { setError: (e: string | null) => void; setSuccess: (s: string | null) => void }) => {
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [dwhSummary, setDwhSummary] = useState<any>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [importHistory, setImportHistory] = useState<any[]>([]);
  const [fiscalYear, setFiscalYear] = useState(new Date().getFullYear() + 1);
  const [baselineMethod, setBaselineMethod] = useState('average');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [aggregateBranches, setAggregateBranches] = useState(true);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  useEffect(() => {
    loadConnections();
    loadImportHistory();
  }, []);

  const loadConnections = async () => {
    try {
      const data = await connectionsAPI.list();
      setConnections(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load connections');
    }
  };

  const loadImportHistory = async () => {
    try {
      const data = await dwhIntegrationAPI.getImportHistory({ limit: 10 });
      setImportHistory(data);
    } catch (err) {
      console.error('Failed to load import history:', err);
    }
  };

  const loadDWHSummary = async (connectionId: number) => {
    setLoading(true);
    try {
      const data = await dwhIntegrationAPI.getBalansSummary(connectionId);
      setDwhSummary(data);
      setPreviewData(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load DWH summary');
    } finally {
      setLoading(false);
    }
  };

  const previewData_ = async () => {
    if (!selectedConnection) return;
    setLoading(true);
    try {
      const data = await dwhIntegrationAPI.previewBalansData(selectedConnection, {
        snapshot_date: selectedDate || undefined,
        limit: 100
      });
      setPreviewData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to preview data');
    } finally {
      setLoading(false);
    }
  };

  const runIngestion = async () => {
    if (!selectedConnection) {
      setError('Please select a connection');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await dwhIntegrationAPI.ingestSnapshots({
        connection_id: selectedConnection,
        source_table: 'balans_ato',
        source_schema: 'dbo',
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        aggregate_branches: aggregateBranches
      });
      setSuccess(`Successfully imported ${result.imported_records} records (Batch: ${result.batch_id})`);
      loadImportHistory();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ingestion failed');
    } finally {
      setLoading(false);
    }
  };

  const generateBaselines = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await dwhIntegrationAPI.generateBaselines({
        fiscal_year: fiscalYear,
        method: baselineMethod,
        apply_trend: true,
        apply_seasonality: true
      });
      setSuccess(`Generated ${result.baselines_created} new baselines, updated ${result.baselines_updated} existing`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Baseline generation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Connection Selection */}
      <div className="grid grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">DWH Connection</label>
          <select
            value={selectedConnection || ''}
            onChange={(e) => {
              const id = parseInt(e.target.value);
              setSelectedConnection(id);
              if (id) loadDWHSummary(id);
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select connection...</option>
            {connections.map((conn) => (
              <option key={conn.id} value={conn.id}>{conn.name} ({conn.db_type})</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-end gap-2">
          <button
            onClick={previewData_}
            disabled={!selectedConnection || loading}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
          >
            <Eye className="w-4 h-4" /> Preview
          </button>
          <button
            onClick={runIngestion}
            disabled={!selectedConnection || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Play className="w-4 h-4" /> Run Ingestion
          </button>
        </div>
      </div>

      {/* DWH Summary */}
      {dwhSummary && (
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Database className="w-4 h-4" /> DWH Data Summary (balans_ato)
          </h3>
          <div className="grid grid-cols-5 gap-4 mb-4">
            <StatCard label="Total Records" value={dwhSummary.total_rows?.toLocaleString() || 0} icon={Table} color="blue" />
            <StatCard label="Unique Accounts" value={dwhSummary.unique_accounts || 0} icon={FileText} color="green" />
            <StatCard label="Monthly Snapshots" value={dwhSummary.unique_dates || 0} icon={Clock} color="purple" />
            <StatCard label="Currencies" value={dwhSummary.unique_currencies || 0} icon={RefreshCw} color="yellow" />
            <StatCard label="Branches" value={dwhSummary.unique_branches || 0} icon={GitBranch} color="red" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">
                <strong>Date Range:</strong> {dwhSummary.date_range?.min} to {dwhSummary.date_range?.max}
              </p>
              <p className="text-sm text-gray-600 mt-1">
                <strong>Available Dates:</strong> {dwhSummary.available_dates?.slice(0, 6).join(', ')}...
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600"><strong>Account Classes:</strong></p>
              <div className="flex flex-wrap gap-2 mt-1">
                {dwhSummary.account_classes?.map((ac: any) => (
                  <span key={ac.class} className="px-2 py-1 bg-gray-100 rounded text-xs">
                    Class {ac.class}: {ac.count} accounts
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Aggregation Options */}
      {selectedConnection && (
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Settings className="w-4 h-4" /> Import Options
          </h3>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={aggregateBranches}
                onChange={(e) => setAggregateBranches(e.target.checked)}
                className="rounded border-gray-300"
              />
              <span className="text-sm text-gray-700">Aggregate all branches</span>
            </label>
            <p className="text-sm text-gray-500">
              {aggregateBranches 
                ? 'Data will be aggregated by account/date/currency across all branches'
                : 'Data will be imported per branch (more detailed)'}
            </p>
          </div>
        </div>
      )}

      {/* Data Preview */}
      {previewData && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">Data Preview ({previewData.count} records)</h3>
          </div>
          <div className="overflow-x-auto max-h-80">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Currency</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Branch</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Balance (UZS)</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Balance (Currency)</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Debit</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Credit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {previewData.data?.slice(0, 20).map((row: any, idx: number) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm font-mono text-gray-900">{row.account_code}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{row.snapshot_date}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{CURRENCY_CODES[row.currency_code] || row.currency_code}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{row.branch_code}</td>
                    <td className="px-4 py-2 text-sm text-right text-gray-900">{row.balance_uzs?.toLocaleString()}</td>
                    <td className="px-4 py-2 text-sm text-right text-gray-600">{row.balance_currency?.toLocaleString()}</td>
                    <td className="px-4 py-2 text-sm text-right text-red-600">{row.debit_turnover?.toLocaleString()}</td>
                    <td className="px-4 py-2 text-sm text-right text-green-600">{row.credit_turnover?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Baseline Generation */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
          <Target className="w-4 h-4" /> Baseline Generation
        </h3>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fiscal Year</label>
            <input
              type="number"
              value={fiscalYear}
              onChange={(e) => setFiscalYear(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Method</label>
            <select
              value={baselineMethod}
              onChange={(e) => setBaselineMethod(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="average">Simple Average</option>
              <option value="weighted_average">Weighted Average</option>
              <option value="trend">Trend Projection</option>
            </select>
          </div>
          <div className="col-span-2 flex items-end">
            <button
              onClick={generateBaselines}
              disabled={loading}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
            >
              <Zap className="w-4 h-4" /> Generate Baselines
            </button>
          </div>
        </div>
      </div>

      {/* Import History */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
          <h3 className="font-medium text-gray-900">Recent Imports</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {importHistory.length === 0 ? (
            <div className="p-4 text-center text-gray-500">No import history</div>
          ) : (
            importHistory.map((log) => (
              <div key={log.id} className="px-4 py-3 flex items-center justify-between">
                <div>
                  <span className="font-medium text-gray-900">{log.import_batch_id.slice(0, 8)}...</span>
                  <span className="text-sm text-gray-500 ml-2">
                    {log.imported_records} / {log.total_records} records
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    log.status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                    log.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                    'bg-yellow-100 text-yellow-700'
                  }`}>
                    {log.status}
                  </span>
                  <span className="text-sm text-gray-500">
                    {log.started_at ? new Date(log.started_at).toLocaleString() : '-'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================
// Egress Panel (Platform -> DWH)
// ============================================
const EgressPanel = ({ setError, setSuccess }: { setError: (e: string | null) => void; setSuccess: (s: string | null) => void }) => {
  const [connections, setConnections] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [selectedBudget, setSelectedBudget] = useState<number | null>(null);
  const [targetTable, setTargetTable] = useState('fpna_approved_budgets');
  const [versionLabel, setVersionLabel] = useState('');
  const [scenarioType, setScenarioType] = useState('OPTIMISTIC');
  const [adjustmentFactor, setAdjustmentFactor] = useState(1.1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadConnections();
    loadBudgets();
  }, []);

  const loadConnections = async () => {
    try {
      const data = await connectionsAPI.list();
      setConnections(data);
    } catch (err) {
      console.error('Failed to load connections:', err);
    }
  };

  const loadBudgets = async () => {
    try {
      const data = await budgetAPI.list({ status: 'APPROVED' });
      setBudgets(data);
    } catch (err) {
      console.error('Failed to load budgets:', err);
    }
  };

  const exportBudget = async () => {
    if (!selectedConnection || !selectedBudget) {
      setError('Please select a connection and budget');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await dwhIntegrationAPI.exportBudget({
        connection_id: selectedConnection,
        budget_id: selectedBudget,
        target_table: targetTable,
        version_label: versionLabel || undefined
      });
      setSuccess(`Exported ${result.records_exported} records to ${targetTable} (Version: ${result.version})`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  const exportScenario = async () => {
    if (!selectedConnection || !selectedBudget) {
      setError('Please select a connection and budget');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await dwhIntegrationAPI.exportScenario({
        connection_id: selectedConnection,
        budget_id: selectedBudget,
        scenario_type: scenarioType,
        adjustment_factor: adjustmentFactor
      });
      setSuccess(`Exported ${result.records_exported} ${scenarioType} scenario records`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Scenario export failed');
    } finally {
      setLoading(false);
    }
  };

  const createVersion = async () => {
    if (!selectedBudget || !versionLabel) {
      setError('Please select a budget and enter a version label');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await dwhIntegrationAPI.createVersion({
        budget_id: selectedBudget,
        version_label: versionLabel
      });
      setSuccess(`Created new version: ${result.new_budget_code} (Version ${result.version})`);
      loadBudgets();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Version creation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Export Budget */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Upload className="w-4 h-4" /> Export Approved Budget to DWH
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">DWH Connection</label>
            <select
              value={selectedConnection || ''}
              onChange={(e) => setSelectedConnection(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">Select connection...</option>
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>{conn.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Approved Budget</label>
            <select
              value={selectedBudget || ''}
              onChange={(e) => setSelectedBudget(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">Select budget...</option>
              {budgets.map((b) => (
                <option key={b.id} value={b.id}>{b.budget_code} - {b.fiscal_year}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Table</label>
            <input
              type="text"
              value={targetTable}
              onChange={(e) => setTargetTable(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Version Label</label>
            <input
              type="text"
              value={versionLabel}
              onChange={(e) => setVersionLabel(e.target.value)}
              placeholder="e.g., V1, Final"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button
            onClick={exportBudget}
            disabled={loading || !selectedConnection || !selectedBudget}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Upload className="w-4 h-4" /> Export Budget
          </button>
          <button
            onClick={createVersion}
            disabled={loading || !selectedBudget || !versionLabel}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
          >
            <GitBranch className="w-4 h-4" /> Create Version
          </button>
        </div>
      </div>

      {/* Export Scenarios */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" /> Export Budget Scenarios
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Scenario Type</label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="OPTIMISTIC">Optimistic</option>
              <option value="PESSIMISTIC">Pessimistic</option>
              <option value="BEST_CASE">Best Case</option>
              <option value="WORST_CASE">Worst Case</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Adjustment Factor</label>
            <input
              type="number"
              step="0.01"
              value={adjustmentFactor}
              onChange={(e) => setAdjustmentFactor(parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
            <p className="text-xs text-gray-500 mt-1">
              1.1 = +10%, 0.9 = -10%
            </p>
          </div>
          <div className="flex items-end">
            <button
              onClick={exportScenario}
              disabled={loading || !selectedConnection || !selectedBudget}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
            >
              <Upload className="w-4 h-4" /> Export Scenario
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// Alerts Panel
// ============================================
const AlertsPanel = ({ setError, setSuccess }: { setError: (e: string | null) => void; setSuccess: (s: string | null) => void }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [thresholds, setThresholds] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [fiscalYear, setFiscalYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number | undefined>();

  useEffect(() => {
    loadAlerts();
    loadSummary();
    loadThresholds();
  }, []);

  const loadAlerts = async () => {
    try {
      const data = await dwhIntegrationAPI.getPendingAlerts({ limit: 50 });
      setAlerts(data);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    }
  };

  const loadSummary = async () => {
    try {
      const data = await dwhIntegrationAPI.getAlertSummary();
      setSummary(data);
    } catch (err) {
      console.error('Failed to load summary:', err);
    }
  };

  const loadThresholds = async () => {
    try {
      const data = await dwhIntegrationAPI.listAlertThresholds();
      setThresholds(data);
    } catch (err) {
      console.error('Failed to load thresholds:', err);
    }
  };

  const checkVariances = async () => {
    setLoading(true);
    setError(null);
    try {
      const newAlerts = await dwhIntegrationAPI.checkVariances(fiscalYear, selectedMonth);
      setSuccess(`Generated ${newAlerts.length} new alerts`);
      loadAlerts();
      loadSummary();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Variance check failed');
    } finally {
      setLoading(false);
    }
  };

  const acknowledgeAlert = async (alertCode: string) => {
    try {
      await dwhIntegrationAPI.acknowledgeAlert(alertCode);
      loadAlerts();
      loadSummary();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to acknowledge alert');
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200';
      case 'WARNING': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default: return 'bg-blue-100 text-blue-700 border-blue-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            label="Total Alerts"
            value={summary.total}
            icon={Bell}
            color="blue"
          />
          <StatCard
            label="Critical"
            value={summary.by_severity?.CRITICAL || 0}
            icon={AlertTriangle}
            color="red"
          />
          <StatCard
            label="Warning"
            value={summary.by_severity?.WARNING || 0}
            icon={AlertCircle}
            color="yellow"
          />
          <StatCard
            label="Pending"
            value={summary.by_status?.PENDING || 0}
            icon={Clock}
            color="purple"
          />
        </div>
      )}

      {/* Check Variances */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-3">Check Budget Variances</h3>
        <div className="flex gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fiscal Year</label>
            <input
              type="number"
              value={fiscalYear}
              onChange={(e) => setFiscalYear(parseInt(e.target.value))}
              className="w-32 px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Month (Optional)</label>
            <select
              value={selectedMonth || ''}
              onChange={(e) => setSelectedMonth(e.target.value ? parseInt(e.target.value) : undefined)}
              className="w-40 px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">All Months</option>
              {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
                <option key={m} value={m}>{new Date(2000, m-1).toLocaleString('default', { month: 'long' })}</option>
              ))}
            </select>
          </div>
          <button
            onClick={checkVariances}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Check Variances
          </button>
        </div>
      </div>

      {/* Alerts List */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex justify-between items-center">
          <h3 className="font-medium text-gray-900">Pending Alerts</h3>
          <button
            onClick={loadAlerts}
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
        <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
          {alerts.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
              <p>No pending alerts</p>
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.alert_code} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${getSeverityColor(alert.severity)}`}>
                        {alert.severity}
                      </span>
                      <span className="text-sm font-medium text-gray-900">{alert.account_code}</span>
                      <span className="text-sm text-gray-500">- {alert.department}</span>
                    </div>
                    <p className="text-sm text-gray-700">{alert.message}</p>
                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                      <span>Variance: {alert.variance_percent?.toFixed(1)}%</span>
                      <span>Planned: {alert.planned_amount?.toLocaleString()}</span>
                      <span>Actual: {alert.actual_amount?.toLocaleString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => acknowledgeAlert(alert.alert_code)}
                    className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                  >
                    Acknowledge
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Thresholds */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
          <h3 className="font-medium text-gray-900">Alert Thresholds</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Department</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Info (%)</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Warning (%)</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Critical (%)</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Notify CFO</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {thresholds.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No custom thresholds configured. Using defaults (5%, 10%, 20%)
                  </td>
                </tr>
              ) : (
                thresholds.map((t, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-900">{t.department || 'All'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{t.account_code || 'All'}</td>
                    <td className="px-4 py-2 text-sm text-center text-blue-600">{t.info_threshold}%</td>
                    <td className="px-4 py-2 text-sm text-center text-yellow-600">{t.warning_threshold}%</td>
                    <td className="px-4 py-2 text-sm text-center text-red-600">{t.critical_threshold}%</td>
                    <td className="px-4 py-2 text-center">
                      {t.notify_cfo ? <CheckCircle className="w-4 h-4 text-green-500 mx-auto" /> : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ============================================
// Audit Panel
// ============================================
const AuditPanel = () => {
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>('');

  useEffect(() => {
    loadAuditLogs();
  }, [filter]);

  const loadAuditLogs = async () => {
    setLoading(true);
    try {
      const data = await dwhIntegrationAPI.getAuditTrail({
        operation: filter || undefined,
        limit: 100
      });
      setAuditLogs(data);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const getOperationColor = (operation: string) => {
    if (operation.includes('INGEST')) return 'bg-blue-100 text-blue-700';
    if (operation.includes('EXPORT')) return 'bg-green-100 text-green-700';
    if (operation.includes('GENERATE')) return 'bg-purple-100 text-purple-700';
    if (operation.includes('VERSION')) return 'bg-yellow-100 text-yellow-700';
    return 'bg-gray-100 text-gray-700';
  };

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-4 items-center">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Operation</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-48 px-3 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Operations</option>
            <option value="INGEST_SNAPSHOTS">Ingest Snapshots</option>
            <option value="INGEST_ACTUALS">Ingest Actuals</option>
            <option value="GENERATE_BASELINES">Generate Baselines</option>
            <option value="EXPORT_BUDGET">Export Budget</option>
            <option value="EXPORT_SCENARIO">Export Scenario</option>
            <option value="CREATE_VERSION">Create Version</option>
          </select>
        </div>
        <button
          onClick={loadAuditLogs}
          className="mt-6 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto max-h-[600px]">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Operation</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Target</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Records</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Batch ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    {loading ? 'Loading...' : 'No audit logs found'}
                  </td>
                </tr>
              ) : (
                auditLogs.map((log, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-500 whitespace-nowrap">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getOperationColor(log.operation)}`}>
                        {log.operation}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900">{log.source_table || '-'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{log.target_table || '-'}</td>
                    <td className="px-4 py-2 text-sm text-center text-gray-900">{log.record_count}</td>
                    <td className="px-4 py-2 text-center">
                      <span className={`px-2 py-1 text-xs rounded ${
                        log.status === 'SUCCESS' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500 font-mono">
                      {log.batch_id?.slice(0, 8)}...
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DWHIntegrationPage;
