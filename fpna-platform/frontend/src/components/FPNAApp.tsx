// src/components/FPNAApp.tsx - Connected to Real Backend
import React, { useState, useEffect } from 'react';
import { 
  Upload, 
  Download, 
  FileSpreadsheet, 
  TrendingUp, 
  DollarSign, 
  Users, 
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  Clock,
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  BarChart2,
  Pencil,
  Filter,
  Database,
  Plug,
  ArrowRight,
  RefreshCw,
  Play,
  Globe,
  FileText,
  Table,
  Layers,
  Banknote,
  Calculator,
  LayoutTemplate,
  Settings
} from 'lucide-react';
import { budgetAPI, authAPI, approvalsAPI, connectionsAPI, etlAPI, budgetUploadAPI } from '../services/api';
import { COAPage, CurrenciesPage, DriversPage, TemplatesPage, SnapshotsPage } from './FPNAModules';
import { DWHIntegrationPage } from './DWHIntegration';
import { DataIntegrationPage } from './DataIntegration';
import { VarianceReportPage } from './VarianceReport';
import BudgetPlanning from './BudgetPlanning';
import BudgetPlanningNew from './BudgetPlanningNew';
import type { ColumnMapping, ColumnMappingSuggestion, HeaderValues } from '../services/api';
import LoginPage from './LoginPage';
import AppHeader from './AppHeader';

// Types
interface Budget {
  id: number;
  budget_code: string;
  fiscal_year: number;
  department: string | null;
  branch: string | null;
  total_amount: number;
  currency: string;
  status: string;
  created_at: string;
  line_items_count?: number;
}

interface BudgetDetail extends Budget {
  line_items: LineItem[];
}

interface LineItem {
  id: number;
  account_code: string;
  account_name: string;
  category: string | null;
  month: number | null;
  quarter?: number | null;
  year?: number | null;
  amount: number;
  quantity: number | null;
  unit_price: number | null;
  notes?: string | null;
}

// Status Badge Component
const StatusBadge = ({ status }: { status: string }) => {
  const statusColors: Record<string, string> = {
    DRAFT: 'bg-gray-100 text-gray-700',
    APPROVED: 'bg-green-100 text-green-700',
    REJECTED: 'bg-red-100 text-red-700',
    PENDING_L1: 'bg-yellow-100 text-yellow-700',
    PENDING_L2: 'bg-yellow-100 text-yellow-700',
    PENDING_L3: 'bg-yellow-100 text-yellow-700',
    PENDING_L4: 'bg-yellow-100 text-yellow-700',
  };

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusColors[status] || 'bg-gray-100 text-gray-700'}`}>
      {status.replace('_', ' ')}
    </span>
  );
};

// Loading Spinner
const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-64">
    <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
  </div>
);

// Error Message
const ErrorMessage = ({ message }: { message: string }) => (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
    <div>
      <p className="text-red-800 font-medium">Error</p>
      <p className="text-red-700 text-sm mt-1">{message}</p>
    </div>
  </div>
);

// Main App Component
const FPNAApp = () => {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [user, setUser] = useState<{ username: string; full_name?: string; roles?: string[] } | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [selectedBudget, setSelectedBudget] = useState<BudgetDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [_uploadProgress, _setUploadProgress] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      authAPI.getCurrentUser()
        .then((u: { username?: string; full_name?: string; roles?: string[] }) =>
          setUser({
            username: u.username || 'user',
            full_name: u.full_name,
            roles: u.roles || [],
          })
        )
        .catch(() => {
          setUser(null);
          setLoginError(null);
        });
    } else {
      setUser(null);
      setLoginError(null);
    }
  }, [currentPage]);

  // Listen for 401 from any API call - force back to login
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setLoginError(null);
    };
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, []);

  const handleLogin = async (username: string, password: string) => {
    setLoginError(null);
    try {
      const res = await authAPI.login(username, password) as {
        access_token?: string;
        user?: { username?: string; full_name?: string; roles?: string[] };
      };
      localStorage.setItem('access_token', res.access_token || '');
      const u = res.user;
      setUser({
        username: u?.username || username,
        full_name: u?.full_name,
        roles: u?.roles || [],
      });
    } catch (err: unknown) {
      const ax = err as { response?: { data?: Record<string, unknown>; status?: number }; message?: string; code?: string };
      let msg: string | undefined;
      const data = ax.response?.data as Record<string, unknown> | undefined;
      const dataMsg = data?.message ?? data?.error ?? data?.detail;
      if (ax.response?.status === 500) {
        msg = typeof dataMsg === 'string' ? dataMsg
          : Array.isArray(dataMsg) ? (dataMsg[0] as { msg?: string })?.msg ?? String(dataMsg)
          : dataMsg != null ? String(dataMsg) : undefined;
        if (!msg && data) {
          msg = JSON.stringify(data).slice(0, 200);
        }
        if (!msg) msg = 'Server error. Check backend console. Start backend with: python -m uvicorn app.main:app --port 8001';
      } else if (ax.response?.status === 401) {
        msg = 'Incorrect username or password';
      } else if (ax.response?.status === 403) {
        msg = 'Account is inactive';
      } else {
        const d = data?.detail;
        msg = typeof d === 'string' ? d : Array.isArray(d) ? (d[0] as { msg?: string })?.msg ?? (d as unknown[]).join(', ') : undefined;
        if (!msg) msg = (data?.message ?? data?.error) as string | undefined;
      }
      if (!msg) {
        if (ax.code === 'ECONNREFUSED' || ax.message?.includes('Network Error')) msg = 'Cannot connect to server. Is the backend running?';
        else if (ax.message) msg = ax.message;
        else msg = 'Login failed';
      }
      setLoginError(msg);
      throw err;
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
    setLoginError(null);
  };

  // Fetch budgets on mount and when entering data-entry
  useEffect(() => {
    if (currentPage === 'dashboard' || currentPage === 'data-entry') {
      fetchBudgets();
    }
  }, [currentPage]);

  const fetchBudgets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await budgetAPI.list();
      setBudgets(Array.isArray(data) ? data : data?.items ?? data?.data ?? []);
    } catch (err: any) {
      const d = err.response?.data;
      let msg = typeof d?.detail === 'string' ? d.detail : d?.message ?? d?.error;
      if (!msg && (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error'))) {
        msg = 'Cannot connect to backend. Is it running on port 8001? Start with: python -m uvicorn app.main:app --port 8001';
      }
      if (!msg) msg = 'Failed to fetch budgets';
      setError(msg);
      console.error('Error fetching budgets:', err?.response?.data || err);
    } finally {
      setLoading(false);
    }
  };

  const fetchBudgetDetails = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await budgetAPI.get(id);
      setSelectedBudget(data);
      setCurrentPage('details');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch budget details');
      console.error('Error fetching budget details:', err);
    } finally {
      setLoading(false);
    }
  };

  const selectBudgetForDataEntry = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await budgetAPI.get(id);
      setSelectedBudget(data);
      setCurrentPage('data-entry');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch budget details');
      console.error('Error fetching budget details:', err);
    } finally {
      setLoading(false);
    }
  };

  // Legacy upload function - kept for potential backward compatibility
  void (async function _handleUpload() {
    if (!uploadedFile) return;
    _setUploadProgress(true);
    setError(null);
    try {
      const uploadedBy = user?.username || 'unknown';
      const result = await budgetAPI.upload(uploadedFile, uploadedBy);
      alert(`Budget uploaded successfully! Code: ${result.budget_code}`);
      setUploadedFile(null);
      setCurrentPage('dashboard');
      await fetchBudgets();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Failed to upload budget');
    } finally {
      _setUploadProgress(false);
    }
  });

  const handleDownloadTemplate = async () => {
    try {
      const blob = await budgetAPI.downloadTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'budget_template.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Failed to download template');
      console.error('Error downloading template:', err);
    }
  };

  const handleSubmitBudget = async (id: number) => {
    setError(null);
    try {
      const budgetId = typeof id === 'string' ? parseInt(id, 10) : id;
      if (isNaN(budgetId)) {
        setError('Invalid budget ID');
        return;
      }
      await budgetAPI.submit(budgetId);
      fetchBudgets();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: Record<string, unknown>; status?: number }; message?: string };
      const d = ax.response?.data;
      let msg = (d?.detail ?? d?.message ?? d?.error) as string | undefined;
      if (ax.response?.status === 401) msg = 'Session expired. Please log in again.';
      else if (ax.response?.status === 403) msg = msg || 'No permission to submit budgets.';
      else if (ax.response?.status === 404) msg = msg || 'Budget not found.';
      else if (ax.response?.status === 500) msg = msg || (typeof d === 'object' ? JSON.stringify(d).slice(0, 150) : undefined);
      if (!msg) msg = ax.message || 'Failed to submit. Try logging out and back in.';
      setError(msg);
    }
  };

  const handleDeleteBudget = async (id: number) => {
    if (!confirm('Are you sure you want to delete this budget?')) return;

    try {
      await budgetAPI.delete(id);
      alert('Budget deleted successfully');
      fetchBudgets();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete budget');
    }
  };

  // Dashboard Page - Updated to show Budget Planning workflow data
  const Dashboard = () => {
    const [workflowStatus, setWorkflowStatus] = useState<any>(null);
    const [plannedBudgets, setPlannedBudgets] = useState<any>(null);
    const [dashboardLoading, setDashboardLoading] = useState(true);
    const [fiscalYear] = useState(2026);

    const formatAmount = (num: number): string => {
      if (num === null || num === undefined) return '-';
      if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(2) + 'T';
      if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(2) + 'B';
      if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(2) + 'M';
      if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(1) + 'K';
      return num.toLocaleString();
    };

    useEffect(() => {
      const loadDashboardData = async () => {
        setDashboardLoading(true);
        try {
          const { baselineAPI } = await import('../services/api');
          const [status, planned] = await Promise.all([
            baselineAPI.getWorkflowStatus(fiscalYear),
            baselineAPI.listPlanned({ fiscal_year: fiscalYear, limit: 20 })
          ]);
          setWorkflowStatus(status);
          setPlannedBudgets(planned);
        } catch (err) {
          console.error('Failed to load dashboard data:', err);
        } finally {
          setDashboardLoading(false);
        }
      };
      loadDashboardData();
    }, [fiscalYear]);

    const steps = workflowStatus?.steps || {};
    const byStatus = steps['3_plan']?.by_status || {};

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">FP&A Dashboard</h1>
            <p className="text-gray-500 mt-1">Budget Planning Overview - FY {fiscalYear}</p>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => setCurrentPage('budget-planning')}
              className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
            >
              <Calculator className="w-4 h-4" />
              Budget Planning
            </button>
            <button 
              onClick={() => setCurrentPage('data-integration')}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg flex items-center gap-2"
            >
              <Database className="w-4 h-4" />
              Data Integration
            </button>
          </div>
        </div>

        {error && <ErrorMessage message={error} />}

        {dashboardLoading ? (
          <LoadingSpinner />
        ) : (
          <>
            {/* Workflow Progress */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Budget Planning Pipeline</h2>
              <div className="flex items-center justify-between">
                {/* Step 1 */}
                <div className="flex-1 text-center">
                  <div className={`w-14 h-14 mx-auto rounded-full flex items-center justify-center ${
                    steps['1_ingest']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <Database className="w-7 h-7" />
                  </div>
                  <p className="mt-2 font-medium text-gray-900 text-sm">DWH Import</p>
                  <p className="text-xs text-gray-500">{steps['1_ingest']?.records || 0} records</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-300" />
                {/* Step 2 */}
                <div className="flex-1 text-center">
                  <div className={`w-14 h-14 mx-auto rounded-full flex items-center justify-center ${
                    steps['2_calculate']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <Calculator className="w-7 h-7" />
                  </div>
                  <p className="mt-2 font-medium text-gray-900 text-sm">Baselines</p>
                  <p className="text-xs text-gray-500">{steps['2_calculate']?.baselines || 0} accounts</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-300" />
                {/* Step 3 */}
                <div className="flex-1 text-center">
                  <div className={`w-14 h-14 mx-auto rounded-full flex items-center justify-center ${
                    steps['3_plan']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <FileSpreadsheet className="w-7 h-7" />
                  </div>
                  <p className="mt-2 font-medium text-gray-900 text-sm">Planned</p>
                  <p className="text-xs text-gray-500">
                    {Object.values(byStatus).reduce((a: number, b: any) => a + (b?.count || 0), 0)} budgets
                  </p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-300" />
                {/* Step 4 */}
                <div className="flex-1 text-center">
                  <div className={`w-14 h-14 mx-auto rounded-full flex items-center justify-center ${
                    steps['4_export']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <Upload className="w-7 h-7" />
                  </div>
                  <p className="mt-2 font-medium text-gray-900 text-sm">Exported</p>
                  <p className="text-xs text-gray-500">{steps['4_export']?.exported || 0} to DWH</p>
                </div>
              </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Draft</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{byStatus.DRAFT?.count || 0}</p>
                  </div>
                  <div className="bg-gray-100 p-3 rounded-lg">
                    <FileSpreadsheet className="w-5 h-5 text-gray-600" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Submitted</p>
                    <p className="text-2xl font-bold text-blue-600 mt-1">{byStatus.SUBMITTED?.count || 0}</p>
                  </div>
                  <div className="bg-blue-100 p-3 rounded-lg">
                    <Clock className="w-5 h-5 text-blue-600" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Approved</p>
                    <p className="text-2xl font-bold text-green-600 mt-1">{byStatus.APPROVED?.count || 0}</p>
                  </div>
                  <div className="bg-green-100 p-3 rounded-lg">
                    <Check className="w-5 h-5 text-green-600" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Exported</p>
                    <p className="text-2xl font-bold text-purple-600 mt-1">{byStatus.EXPORTED?.count || 0}</p>
                  </div>
                  <div className="bg-purple-100 p-3 rounded-lg">
                    <Upload className="w-5 h-5 text-purple-600" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Amount</p>
                    <p className="text-xl font-bold text-gray-900 mt-1">
                      {formatAmount(Object.values(byStatus).reduce((a: number, b: any) => a + (b?.amount || 0), 0))}
                    </p>
                  </div>
                  <div className="bg-indigo-100 p-3 rounded-lg">
                    <DollarSign className="w-5 h-5 text-indigo-600" />
                  </div>
                </div>
              </div>
            </div>

            {/* Planned Budgets Table */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="p-6 border-b border-gray-200 flex justify-between items-center">
                <h2 className="text-xl font-semibold text-gray-900">Planned Budgets - FY {fiscalYear}</h2>
                <button 
                  onClick={() => setCurrentPage('budget-planning')}
                  className="text-primary-600 hover:text-primary-700 text-sm font-medium flex items-center gap-1"
                >
                  View All <ChevronRight className="w-4 h-4" />
                </button>
              </div>
              
              {!plannedBudgets?.data?.length ? (
                <div className="p-12 text-center text-gray-500">
                  <Calculator className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>No planned budgets yet.</p>
                  <button 
                    onClick={() => setCurrentPage('budget-planning')}
                    className="mt-4 text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Start Budget Planning →
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Account</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Baseline</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Planned</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Variance</th>
                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-700 uppercase">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {plannedBudgets.data.slice(0, 10).map((budget: any) => (
                        <tr key={budget.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 text-sm font-mono text-gray-900">{budget.account_code}</td>
                          <td className="px-6 py-4 text-sm text-right text-gray-600">
                            {formatAmount(budget.baseline_amount)}
                          </td>
                          <td className="px-6 py-4 text-sm text-right font-semibold text-gray-900">
                            {formatAmount(budget.annual_total)}
                          </td>
                          <td className="px-6 py-4 text-sm text-right">
                            <span className={budget.variance_from_baseline >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {budget.variance_pct >= 0 ? '+' : ''}{budget.variance_pct?.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <StatusBadge status={budget.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-4 gap-4">
              <button 
                onClick={() => setCurrentPage('data-integration')}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Download className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Import Data</p>
                    <p className="text-sm text-gray-500">From DWH</p>
                  </div>
                </div>
              </button>
              <button 
                onClick={() => setCurrentPage('budget-planning')}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <Calculator className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Plan Budgets</p>
                    <p className="text-sm text-gray-500">Apply drivers</p>
                  </div>
                </div>
              </button>
              <button 
                onClick={() => setCurrentPage('approvals')}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-yellow-100 rounded-lg">
                    <Users className="w-5 h-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Approvals</p>
                    <p className="text-sm text-gray-500">Review & approve</p>
                  </div>
                </div>
              </button>
              <button 
                onClick={() => setCurrentPage('variance-report')}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <TrendingUp className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Variance Report</p>
                    <p className="text-sm text-gray-500">Plan vs Fact</p>
                  </div>
                </div>
              </button>
            </div>
          </>
        )}
      </div>
    );
  };

  // Data Entry: budget list to select from (when no budget selected yet)
  const DataEntryBudgetList = ({
    budgets,
    loading,
    error,
    onSelectBudget,
    onRefresh,
  }: {
    budgets: Budget[];
    loading: boolean;
    error: string | null;
    onSelectBudget: (id: number) => void;
    onRefresh: () => void;
  }) => (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Data Entry</h1>
      <p className="text-gray-600">Select a budget to edit with drill-down, slice, and batch save.</p>
      {error && <ErrorMessage message={error} />}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-900">Select Budget</h2>
          <button onClick={onRefresh} className="text-primary-600 hover:text-primary-700 text-sm font-medium">Refresh</button>
        </div>
        {loading ? (
          <LoadingSpinner />
        ) : budgets.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <FileSpreadsheet className="w-12 h-12 mx-auto mb-3 text-gray-400" />
            <p>No budgets found. Upload a budget first from the Upload page.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Budget Code</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Fiscal Year</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Department</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Branch</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Amount</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {budgets.map((budget) => (
                  <tr key={budget.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{budget.budget_code}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{budget.fiscal_year}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{budget.department || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{budget.branch || '-'}</td>
                    <td className="px-6 py-4 text-sm font-semibold text-gray-900">${Number(budget.total_amount).toLocaleString()}</td>
                    <td className="px-6 py-4 text-sm"><StatusBadge status={budget.status} /></td>
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => onSelectBudget(budget.id)}
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );

  // Budget Details / Data Entry Page (drill-down, slice, drill-up, section edit, Enter saves)
  const BudgetDetails = () => {
    const [editingHeader, setEditingHeader] = useState(false);
    const [headerEdit, setHeaderEdit] = useState({ department: '', branch: '', description: '', notes: '' });
    const [editingLineId, setEditingLineId] = useState<number | null>(null);
    const [editLineValues, setEditLineValues] = useState<Partial<LineItem>>({});
    const [newRow, setNewRow] = useState<Partial<LineItem> | null>(null);
    const [saving, setSaving] = useState(false);
    // Drill-down / slice state
    const [viewMode, setViewMode] = useState<'drill' | 'table'>('drill');
    const [groupBy, setGroupBy] = useState<'category' | 'month'>('category');
    const [sliceMonth, setSliceMonth] = useState<number | null>(null);
    const [drillPath, setDrillPath] = useState<string[]>([]); // e.g. [] = All, ['Revenue'] = drilled into Revenue
    const [sectionEdit, setSectionEdit] = useState<{ key: string; amount?: number; quantity?: number } | null>(null);
    const [pendingLineEdits, setPendingLineEdits] = useState<Record<number, Partial<LineItem>>>({});
    const [pendingSectionEdits, setPendingSectionEdits] = useState<Record<string, { amount?: number; quantity?: number }>>({});

    if (!selectedBudget) return <LoadingSpinner />;

    const isEditable = selectedBudget.status === 'DRAFT' || selectedBudget.status === 'REJECTED';

    // Filter line items by slice
    const filteredItems = selectedBudget.line_items.filter((i) => {
      if (sliceMonth != null && i.month !== sliceMonth) return false;
      return true;
    });

    // Group by category or month
    const groups = (() => {
      if (groupBy === 'category') {
        const m: Record<string, LineItem[]> = {};
        for (const i of filteredItems) {
          const k = (i.category || 'Uncategorized').trim() || 'Uncategorized';
          if (!m[k]) m[k] = [];
          m[k].push(i);
        }
        return Object.entries(m).sort((a, b) => a[0].localeCompare(b[0]));
      }
      const m: Record<string, LineItem[]> = {};
      for (const i of filteredItems) {
        const k = i.month != null ? String(i.month) : 'Unassigned';
        if (!m[k]) m[k] = [];
        m[k].push(i);
      }
      return Object.entries(m).sort((a, b) => {
        if (a[0] === 'Unassigned') return 1;
        if (b[0] === 'Unassigned') return -1;
        return parseInt(a[0], 10) - parseInt(b[0], 10);
      });
    })();

    const drilledGroup = drillPath[0];
    const drilledItems = drilledGroup ? (groups.find(([k]) => k === drilledGroup)?.[1] ?? []) : [];

    const startEditHeader = () => {
      setHeaderEdit({
        department: selectedBudget.department ?? '',
        branch: selectedBudget.branch ?? '',
        description: ((selectedBudget as unknown) as Record<string, unknown>).description as string ?? '',
        notes: ((selectedBudget as unknown) as Record<string, unknown>).notes as string ?? '',
      });
      setEditingHeader(true);
    };

    const saveHeader = async () => {
      if (!editingHeader) return;
      setSaving(true);
      setError(null);
      try {
        const updated = await budgetAPI.update(selectedBudget.id, {
          department: headerEdit.department || undefined,
          branch: headerEdit.branch || undefined,
          description: headerEdit.description || undefined,
          notes: headerEdit.notes || undefined,
        });
        setSelectedBudget({ ...selectedBudget, ...updated });
        setEditingHeader(false);
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update budget');
      } finally {
        setSaving(false);
      }
    };

    const startEditLine = (item: LineItem) => {
      setEditingLineId(item.id);
      setEditLineValues({
        account_code: item.account_code,
        account_name: item.account_name,
        category: item.category ?? '',
        month: item.month ?? undefined,
        amount: item.amount,
        quantity: item.quantity ?? undefined,
        unit_price: item.unit_price ?? undefined,
        notes: item.notes ?? '',
      });
    };

    const saveLineItem = async () => {
      if (editingLineId == null) return;
      setSaving(true);
      setError(null);
      try {
        await budgetAPI.updateLineItem(selectedBudget.id, editingLineId, {
          account_code: editLineValues.account_code,
          account_name: editLineValues.account_name,
          category: editLineValues.category || null,
          month: editLineValues.month ?? null,
          amount: editLineValues.amount,
          quantity: editLineValues.quantity ?? null,
          unit_price: editLineValues.unit_price ?? null,
          notes: editLineValues.notes || null,
        });
        const detail = await budgetAPI.get(selectedBudget.id);
        setSelectedBudget(detail as BudgetDetail);
        setEditingLineId(null);
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update line item');
      } finally {
        setSaving(false);
      }
    };

    const addNewRow = () => {
      setNewRow({
        account_code: '',
        account_name: '',
        category: '',
        month: undefined,
        amount: 0,
        quantity: undefined,
        unit_price: undefined,
        notes: '',
      });
    };

    const saveNewRow = async () => {
      if (!newRow || selectedBudget == null) return;
      const { account_code, account_name, amount } = newRow;
      if (!account_code?.trim() || !account_name?.trim() || amount == null) {
        setError('Account code, account name, and amount are required.');
        return;
      }
      setSaving(true);
      setError(null);
      try {
        await budgetAPI.createLineItem(selectedBudget.id, {
          account_code: account_code.trim(),
          account_name: account_name.trim(),
          category: newRow.category || null,
          month: newRow.month ?? null,
          quarter: newRow.quarter ?? null,
          year: newRow.year ?? null,
          amount: Number(amount) || 0,
          quantity: newRow.quantity ?? null,
          unit_price: newRow.unit_price ?? null,
          notes: newRow.notes || null,
        });
        const detail = await budgetAPI.get(selectedBudget.id);
        setSelectedBudget(detail as BudgetDetail);
        setNewRow(null);
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to add line item');
      } finally {
        setSaving(false);
      }
    };

    const deleteLineItem = async (itemId: number) => {
      if (!confirm('Delete this line item?')) return;
      setSaving(true);
      setError(null);
      try {
        await budgetAPI.deleteLineItem(selectedBudget.id, itemId);
        setSelectedBudget({
          ...selectedBudget,
          line_items: selectedBudget.line_items.filter((i) => i.id !== itemId),
        });
        const detail = await budgetAPI.get(selectedBudget.id);
        setSelectedBudget(detail as BudgetDetail);
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete');
      } finally {
        setSaving(false);
      }
    };

    const queueLineEdit = () => {
      if (editingLineId == null) return;
      setPendingLineEdits((p) => ({
        ...p,
        [editingLineId]: {
          amount: editLineValues.amount,
          quantity: editLineValues.quantity,
          unit_price: editLineValues.unit_price,
        },
      }));
      setEditingLineId(null);
    };

    const handleKeyDown = (e: React.KeyboardEvent, action: 'header' | 'line' | 'new' | 'section' | 'batch') => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (action === 'header') saveHeader();
        if (action === 'line') {
          if (viewMode === 'drill') queueLineEdit();
          else saveLineItem();
        }
        if (action === 'new') saveNewRow();
        if (action === 'section') saveSectionEdit();
        if (action === 'batch') saveAllPending();
      }
    };

    const saveSectionEdit = async () => {
      if (!sectionEdit || !isEditable) return;
      setSaving(true);
      setError(null);
      try {
        await budgetAPI.scaleSection(
          selectedBudget.id,
          groupBy,
          sectionEdit.key,
          sectionEdit.amount,
          sectionEdit.quantity
        );
        const detail = await budgetAPI.get(selectedBudget.id);
        setSelectedBudget(detail as BudgetDetail);
        setSectionEdit(null);
        setPendingSectionEdits((p) => {
          const n = { ...p };
          delete n[sectionEdit.key];
          return n;
        });
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to scale section');
      } finally {
        setSaving(false);
      }
    };

    const saveAllPending = async () => {
      if (!isEditable) return;
        const lineUpdates = Object.entries(pendingLineEdits)
        .filter(([, v]) => Object.keys(v).length > 0)
        .map(([id, v]) => {
          const obj: Record<string, unknown> = { id: parseInt(id, 10) };
          if (v.amount != null) obj.amount = v.amount;
          if (v.quantity != null) obj.quantity = v.quantity;
          if (v.unit_price != null) obj.unit_price = v.unit_price;
          return obj;
        }) as { id: number; amount?: number; quantity?: number; unit_price?: number }[];
      const sectionKeys = Object.keys(pendingSectionEdits);
      setSaving(true);
      setError(null);
      try {
        for (const key of sectionKeys) {
          const ed = pendingSectionEdits[key];
          if (ed?.amount != null || ed?.quantity != null) {
            await budgetAPI.scaleSection(selectedBudget.id, groupBy, key, ed?.amount, ed?.quantity);
          }
        }
        if (lineUpdates.length > 0) {
          await budgetAPI.batchUpdateLineItems(selectedBudget.id, lineUpdates);
        }
        const detail = await budgetAPI.get(selectedBudget.id);
        setSelectedBudget(detail as BudgetDetail);
        setPendingLineEdits({});
        setPendingSectionEdits({});
        setSectionEdit(null);
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save');
      } finally {
        setSaving(false);
      }
    };

    const hasPending = Object.keys(pendingLineEdits).length > 0 || Object.keys(pendingSectionEdits).length > 0;

    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <button
            onClick={() => currentPage === 'data-entry' ? setSelectedBudget(null) : setCurrentPage('dashboard')}
            className="hover:text-primary-600"
          >
            {currentPage === 'data-entry' ? 'Data Entry' : 'Budgets'}
          </button>
          <ChevronRight className="w-4 h-4" />
          <span className="text-gray-900 font-medium">{selectedBudget.budget_code}</span>
        </div>

        {error && <ErrorMessage message={error} />}

        {/* Budget Header (editable when DRAFT or REJECTED) */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{selectedBudget.budget_code}</h1>
              {!editingHeader ? (
                <p className="text-gray-600 mt-1">
                  {selectedBudget.department || 'No Department'} — {selectedBudget.branch || 'No Branch'}
                </p>
              ) : (
                <div className="mt-2 space-y-2" onKeyDown={(e) => handleKeyDown(e, 'header')}>
                  <input
                    className="border border-gray-300 rounded px-2 py-1 w-48 text-sm"
                    placeholder="Department"
                    value={headerEdit.department}
                    onChange={(e) => setHeaderEdit((h) => ({ ...h, department: e.target.value }))}
                  />
                  <input
                    className="border border-gray-300 rounded px-2 py-1 w-48 text-sm ml-2"
                    placeholder="Branch"
                    value={headerEdit.branch}
                    onChange={(e) => setHeaderEdit((h) => ({ ...h, branch: e.target.value }))}
                  />
                  <div className="flex items-center gap-2 mt-2">
                    <button onClick={saveHeader} disabled={saving} className="px-3 py-1 bg-primary-600 text-white rounded text-sm disabled:opacity-50">Save (Enter)</button>
                    <button onClick={() => setEditingHeader(false)} className="px-3 py-1 border rounded text-sm">Cancel</button>
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={selectedBudget.status} />
              {isEditable && !editingHeader && (
                <button onClick={startEditHeader} className="p-1.5 rounded hover:bg-gray-100" title="Edit header">
                  <Pencil className="w-4 h-4 text-gray-600" />
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-4 gap-6 mt-6">
            <div>
              <p className="text-sm text-gray-600">Fiscal Year</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{selectedBudget.fiscal_year}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Amount</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                ${Number(selectedBudget.total_amount).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Line Items</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{selectedBudget.line_items.length}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Created</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                {new Date(selectedBudget.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </div>

        {/* Data Entry: Drill-down / Slice / Table toggle */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200 flex flex-wrap justify-between items-center gap-4">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold text-gray-900">Data Entry</h2>
              <div className="flex rounded-lg border border-gray-200 p-0.5">
                <button
                  onClick={() => setViewMode('drill')}
                  className={`px-3 py-1.5 text-sm rounded-md ${viewMode === 'drill' ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
                >
                  Drill
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  className={`px-3 py-1.5 text-sm rounded-md ${viewMode === 'table' ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
                >
                  Table
                </button>
              </div>
            </div>
            {isEditable && viewMode === 'table' && (
              <button
                onClick={addNewRow}
                disabled={!!newRow}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm"
              >
                <Plus className="w-4 h-4" />
                Add row
              </button>
            )}
          </div>

          {/* Drill view: slice + drill-down/up + section edit */}
          {viewMode === 'drill' && (
            <div className="p-6 space-y-4">
              {/* Slice bar */}
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Filter className="w-4 h-4 text-gray-500" />
                  <span className="text-sm font-medium text-gray-700">Group by</span>
                  <select
                    className="border rounded px-2 py-1 text-sm"
                    value={groupBy}
                    onChange={(e) => { setGroupBy(e.target.value as 'category' | 'month'); setDrillPath([]); setSectionEdit(null); }}
                  >
                    <option value="category">Category</option>
                    <option value="month">Month</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700">Month filter</span>
                  <select
                    className="border rounded px-2 py-1 text-sm"
                    value={sliceMonth ?? ''}
                    onChange={(e) => { setSliceMonth(e.target.value ? parseInt(e.target.value, 10) : null); setDrillPath([]); }}
                  >
                    <option value="">All months</option>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => (
                      <option key={m} value={m}>Month {m}</option>
                    ))}
                  </select>
                </div>
                {hasPending && isEditable && (
                  <button
                    onClick={saveAllPending}
                    disabled={saving}
                    className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 text-sm font-medium disabled:opacity-50"
                  >
                    Save all (Enter)
                  </button>
                )}
              </div>

              {/* Breadcrumb */}
              <div className="flex items-center gap-1 text-sm text-gray-600">
                <button onClick={() => { setDrillPath([]); setSectionEdit(null); }} className="hover:text-primary-600">
                  All
                </button>
                {drillPath.map((p) => (
                  <span key={p} className="flex items-center gap-1">
                    <ChevronRight className="w-4 h-4" />
                    <button
                      onClick={() => { setDrillPath([p]); setSectionEdit(null); }}
                      className="hover:text-primary-600"
                    >
                      {p}
                    </button>
                  </span>
                ))}
              </div>

              {/* Sections view (drill up) or line items (drilled down) */}
              {!drilledGroup ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">{groupBy === 'category' ? 'Category' : 'Month'}</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Amount</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Quantity</th>
                        {isEditable && <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Actions</th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {groups.map(([key, items]) => {
                        const totalAmount = items.reduce((s, i) => s + Number(i.amount), 0);
                        const totalQty = items.reduce((s, i) => s + Number(i.quantity || 0), 0);
                        const editing = sectionEdit?.key === key;
                        const pending = pendingSectionEdits[key];
                        const dispAmount = pending?.amount ?? totalAmount;
                        const dispQty = pending?.quantity ?? totalQty;
                        return (
                          <tr key={key} className="hover:bg-gray-50">
                            <td className="px-6 py-4 text-sm font-medium text-gray-900">
                              <button
                                onClick={() => setDrillPath([key])}
                                className="flex items-center gap-1 text-primary-600 hover:underline"
                              >
                                <ChevronDown className="w-4 h-4" />
                                {key}
                              </button>
                            </td>
                            <td className="px-6 py-4 text-right">
                              {editing && isEditable ? (
                                <input
                                  type="number"
                                  step="0.01"
                                  className="w-32 border rounded px-2 py-1 text-sm text-right"
                                  value={sectionEdit.amount ?? dispAmount}
                                  onChange={(e) => setSectionEdit((s) => s ? { ...s, amount: parseFloat(e.target.value) || 0 } : null)}
                                  onKeyDown={(e) => handleKeyDown(e, 'section')}
                                  autoFocus
                                />
                              ) : (
                                <span className="text-sm font-semibold text-gray-900">${Number(dispAmount).toLocaleString()}</span>
                              )}
                            </td>
                            <td className="px-6 py-4 text-right">
                              {editing && isEditable && totalQty > 0 ? (
                                <input
                                  type="number"
                                  step="0.01"
                                  className="w-24 border rounded px-2 py-1 text-sm text-right"
                                  value={sectionEdit?.quantity ?? dispQty}
                                  onChange={(e) => setSectionEdit((s) => s ? { ...s, quantity: parseFloat(e.target.value) || 0 } : null)}
                                  onKeyDown={(e) => handleKeyDown(e, 'section')}
                                />
                              ) : (
                                <span className="text-sm text-gray-600">{Number(dispQty).toLocaleString()}</span>
                              )}
                            </td>
                            {isEditable && (
                              <td className="px-6 py-4 text-right">
                                {editing ? (
                                  <button onClick={saveSectionEdit} disabled={saving} className="text-primary-600 hover:underline text-sm mr-2">Save</button>
                                ) : (
                                  <button
                                    onClick={() => setSectionEdit({ key, amount: totalAmount, quantity: totalQty > 0 ? totalQty : undefined })}
                                    className="text-primary-600 hover:underline text-sm"
                                  >
                                    Edit section
                                  </button>
                                )}
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => { setDrillPath([]); setSectionEdit(null); }}
                      className="flex items-center gap-1 text-sm text-primary-600 hover:underline"
                    >
                      <ChevronUp className="w-4 h-4" />
                      Drill up
                    </button>
                    <span className="text-sm text-gray-600">{drilledItems.length} items</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Account</th>
                          <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Name</th>
                          <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Amount</th>
                          <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                          {isEditable && <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Actions</th>}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {drilledItems.map((item) => {
                          const ped = pendingLineEdits[item.id];
                          const dispAmount = ped?.amount ?? item.amount;
                          const dispQty = ped?.quantity ?? item.quantity;
                          const isEditing = editingLineId === item.id;
                          return (
                            <tr key={item.id} className="hover:bg-gray-50">
                              <td className="px-6 py-4 text-sm font-medium text-gray-900">{item.account_code}</td>
                              <td className="px-6 py-4 text-sm text-gray-900">{item.account_name}</td>
                              <td className="px-6 py-4 text-right">
                                {isEditing && isEditable ? (
                                  <input
                                    type="number"
                                    step="0.01"
                                    className="w-28 border rounded px-2 py-1 text-sm text-right"
                                    value={editLineValues.amount ?? dispAmount}
                                    onChange={(e) => setEditLineValues((v) => ({ ...v, amount: parseFloat(e.target.value) || 0 }))}
                                    onKeyDown={(e) => handleKeyDown(e, 'line')}
                                  />
                                ) : (
                                  <span className="text-sm font-semibold">${Number(dispAmount).toLocaleString()}</span>
                                )}
                              </td>
                              <td className="px-6 py-4 text-right">
                                {isEditing && isEditable ? (
                                  <input
                                    type="number"
                                    step="0.01"
                                    className="w-20 border rounded px-2 py-1 text-sm text-right"
                                    value={editLineValues.quantity ?? dispQty ?? ''}
                                    onChange={(e) => setEditLineValues((v) => ({ ...v, quantity: e.target.value ? parseFloat(e.target.value) : undefined }))}
                                    onKeyDown={(e) => handleKeyDown(e, 'line')}
                                  />
                                ) : (
                                  <span className="text-sm text-gray-600">{dispQty != null ? Number(dispQty).toLocaleString() : '-'}</span>
                                )}
                              </td>
                              {isEditable && (
                                <td className="px-6 py-4 text-right">
                                  {isEditing ? (
                                    <button
                                      onClick={queueLineEdit}
                                      className="text-primary-600 hover:underline text-sm mr-2"
                                    >
                                      Queue (Enter)
                                    </button>
                                  ) : (
                                    <button onClick={() => startEditLine(item)} className="text-primary-600 hover:underline text-sm">Edit</button>
                                  )}
                                </td>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-gray-500">
                    Edit rows and click &quot;Queue&quot; to add to batch. Press &quot;Save all&quot; or Enter to persist to database.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Table view (original flat table) */}
          {viewMode === 'table' && (
          <div className="p-6 border-t border-gray-200">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Account Code</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Account Name</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Category</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Month</th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Amount</th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Qty</th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Unit Price</th>
                  {isEditable && <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {selectedBudget.line_items.map((item) => (
                  <tr
                    key={item.id}
                    className={`hover:bg-gray-50 ${editingLineId === item.id ? 'bg-blue-50' : ''}`}
                  >
                    {editingLineId === item.id ? (
                      <>
                        <td className="px-6 py-2">
                          <input
                            className="w-full border rounded px-2 py-1 text-sm"
                            value={editLineValues.account_code ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, account_code: e.target.value }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            className="w-full border rounded px-2 py-1 text-sm"
                            value={editLineValues.account_name ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, account_name: e.target.value }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            className="w-full border rounded px-2 py-1 text-sm"
                            value={editLineValues.category ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, category: e.target.value }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            type="number"
                            className="w-20 border rounded px-2 py-1 text-sm"
                            value={editLineValues.month ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, month: e.target.value ? parseInt(e.target.value, 10) : undefined }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            type="number"
                            step="0.01"
                            className="w-28 border rounded px-2 py-1 text-sm text-right"
                            value={editLineValues.amount ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, amount: parseFloat(e.target.value) || 0 }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            type="number"
                            step="0.01"
                            className="w-20 border rounded px-2 py-1 text-sm text-right"
                            value={editLineValues.quantity ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, quantity: e.target.value ? parseFloat(e.target.value) : undefined }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2">
                          <input
                            type="number"
                            step="0.01"
                            className="w-24 border rounded px-2 py-1 text-sm text-right"
                            value={editLineValues.unit_price ?? ''}
                            onChange={(e) => setEditLineValues((v) => ({ ...v, unit_price: e.target.value ? parseFloat(e.target.value) : undefined }))}
                            onKeyDown={(e) => handleKeyDown(e, 'line')}
                          />
                        </td>
                        <td className="px-6 py-2 text-right">
                          <button onClick={saveLineItem} disabled={saving} className="text-primary-600 hover:underline text-sm mr-2">Save</button>
                          <button onClick={() => setEditingLineId(null)} className="text-gray-500 hover:underline text-sm">Cancel</button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-6 py-4 text-sm font-medium text-gray-900">{item.account_code}</td>
                        <td className="px-6 py-4 text-sm text-gray-900">{item.account_name}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{item.category || '-'}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{item.month ?? '-'}</td>
                        <td className="px-6 py-4 text-sm font-semibold text-right text-gray-900">${Number(item.amount).toLocaleString()}</td>
                        <td className="px-6 py-4 text-sm text-right text-gray-600">{item.quantity != null ? Number(item.quantity).toLocaleString() : '-'}</td>
                        <td className="px-6 py-4 text-sm text-right text-gray-600">{item.unit_price != null ? `$${Number(item.unit_price).toLocaleString()}` : '-'}</td>
                        {isEditable && (
                          <td className="px-6 py-4 text-right">
                            <button onClick={() => startEditLine(item)} className="text-primary-600 hover:underline text-sm mr-2">Edit</button>
                            <button onClick={() => deleteLineItem(item.id)} className="text-red-600 hover:underline text-sm">Delete</button>
                          </td>
                        )}
                      </>
                    )}
                  </tr>
                ))}
                {newRow && (
                  <tr className="bg-amber-50 border-l-4 border-amber-400">
                    <td className="px-6 py-2">
                      <input
                        className="w-full border border-amber-300 rounded px-2 py-1 text-sm bg-white"
                        placeholder="Account code"
                        value={newRow.account_code ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, account_code: e.target.value }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        className="w-full border border-amber-300 rounded px-2 py-1 text-sm bg-white"
                        placeholder="Account name"
                        value={newRow.account_name ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, account_name: e.target.value }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        className="w-full border border-amber-300 rounded px-2 py-1 text-sm bg-white"
                        placeholder="Category"
                        value={newRow.category ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, category: e.target.value }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        type="number"
                        className="w-20 border border-amber-300 rounded px-2 py-1 text-sm bg-white"
                        value={newRow.month ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, month: e.target.value ? parseInt(e.target.value, 10) : undefined }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        type="number"
                        step="0.01"
                        className="w-28 border border-amber-300 rounded px-2 py-1 text-sm text-right bg-white"
                        value={newRow.amount ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, amount: parseFloat(e.target.value) || 0 }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        type="number"
                        step="0.01"
                        className="w-20 border border-amber-300 rounded px-2 py-1 text-sm text-right bg-white"
                        value={newRow.quantity ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, quantity: e.target.value ? parseFloat(e.target.value) : undefined }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    <td className="px-6 py-2">
                      <input
                        type="number"
                        step="0.01"
                        className="w-24 border border-amber-300 rounded px-2 py-1 text-sm text-right bg-white"
                        value={newRow.unit_price ?? ''}
                        onChange={(e) => setNewRow((r) => ({ ...r, unit_price: e.target.value ? parseFloat(e.target.value) : undefined }))}
                        onKeyDown={(e) => handleKeyDown(e, 'new')}
                      />
                    </td>
                    {isEditable && (
                      <td className="px-6 py-2 text-right">
                        <span className="text-amber-700 text-xs font-medium mr-2">New — press Enter to save</span>
                        <button onClick={saveNewRow} disabled={saving} className="text-primary-600 hover:underline text-sm mr-2">Save</button>
                        <button onClick={() => setNewRow(null)} className="text-gray-500 hover:underline text-sm">Cancel</button>
                      </td>
                    )}
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
          )}
        </div>
      </div>
    );
  };

  // Analytics Page (stats + charts from backend)
  const AnalyticsPage = () => {
    const [budgets, setBudgetsList] = useState<Budget[]>([]);
    const [selectedBudgetId, setSelectedBudgetId] = useState<number | null>(null);
    const [stats, setStats] = useState<{
      budget_code: string;
      fiscal_year: number;
      overall: { total_items: number; total_amount: number; average_amount: number; min_amount: number; max_amount: number };
      by_category: { category: string; count: number; total: number }[];
    } | null>(null);
    const [loadingStats, setLoadingStats] = useState(false);

    useEffect(() => {
      budgetAPI.list().then(setBudgetsList).catch(() => setBudgetsList([]));
    }, []);

    useEffect(() => {
      if (selectedBudgetId == null) {
        setStats(null);
        return;
      }
      setLoadingStats(true);
      budgetAPI
        .stats(selectedBudgetId)
        .then((data: unknown) => setStats(data as typeof stats))
        .catch(() => setStats(null))
        .finally(() => setLoadingStats(false));
    }, [selectedBudgetId]);

    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select budget</label>
          <select
            className="border border-gray-300 rounded-lg px-4 py-2 w-full max-w-md"
            value={selectedBudgetId ?? ''}
            onChange={(e) => setSelectedBudgetId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— Choose a budget —</option>
            {budgets.map((b) => (
              <option key={b.id} value={b.id}>
                {b.budget_code} ({b.fiscal_year})
              </option>
            ))}
          </select>
        </div>

        {loadingStats && <LoadingSpinner />}
        {!loadingStats && stats && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary</h2>
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-gray-600">Total line items</dt>
                  <dd className="text-xl font-semibold text-gray-900">{stats.overall.total_items}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-600">Total amount</dt>
                  <dd className="text-xl font-semibold text-gray-900">${Number(stats.overall.total_amount).toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-600">Average amount</dt>
                  <dd className="text-xl font-semibold text-gray-900">${Number(stats.overall.average_amount).toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-600">Min / Max</dt>
                  <dd className="text-xl font-semibold text-gray-900">
                    ${Number(stats.overall.min_amount).toLocaleString()} / ${Number(stats.overall.max_amount).toLocaleString()}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Amount by category</h2>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {stats.by_category.map((cat) => (
                  <div key={cat.category} className="flex justify-between items-center py-2 border-b border-gray-100">
                    <span className="font-medium text-gray-900">{cat.category}</span>
                    <span className="text-gray-600">${Number(cat.total).toLocaleString()} ({cat.count} items)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        {!loadingStats && selectedBudgetId != null && !stats && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p className="text-amber-800">No stats for this budget or failed to load.</p>
          </div>
        )}
      </div>
    );
  };

  // Manage Connections Page - DWH connections and table mappings
  const FPNA_TARGET_ENTITIES = [
    { value: 'budgets', label: 'Budgets (Plan)' },
    { value: 'budget_line_items', label: 'Budget Line Items' },
    { value: 'fact_sales', label: 'Fact Sales' },
    { value: 'fact_expenses', label: 'Fact Expenses' },
    { value: 'fact_revenue', label: 'Fact Revenue' },
    { value: 'dim_accounts', label: 'Dimension Accounts' },
    { value: 'dim_departments', label: 'Dimension Departments' },
    { value: 'custom', label: 'Custom Entity' },
  ];

  const ManageConnectionsPage = () => {
    const [connections, setConnections] = useState<{ id: number; name: string; db_type: string; host: string; port?: number; database_name: string; username: string; schema_name?: string; is_active: boolean }[]>([]);
    const [loading, setConnLoading] = useState(false);
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [form, setForm] = useState({ name: '', db_type: 'sql_server', host: '', port: 1433, database_name: '', username: '', password: '', schema_name: '', use_ssl: false, description: '' });
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [selectedConnId, setSelectedConnId] = useState<number | null>(null);
    const [tables, setTables] = useState<{ schema_name?: string; table_name: string; full_name: string }[]>([]);
    const [mappings, setMappings] = useState<{ id: number; source_table: string; source_schema?: string; target_entity: string; target_description?: string; column_mapping?: Record<string, string>; sync_enabled: boolean }[]>([]);
    const [showMappingForm, setShowMappingForm] = useState(false);
    const [mappingForm, setMappingForm] = useState({ source_table: '', source_schema: '', target_entity: 'budgets', target_description: '', column_mapping: {} as Record<string, string> });
    const [columns, setColumns] = useState<{ column_name: string; data_type: string }[]>([]);

    const fetchConnections = () => {
      setConnLoading(true);
      connectionsAPI.list().then(setConnections).catch(() => setConnections([])).finally(() => setConnLoading(false));
    };

    useEffect(() => { fetchConnections(); }, []);

    useEffect(() => {
      if (!selectedConnId) { setTables([]); setMappings([]); return; }
      connectionsAPI.getTables(selectedConnId).then(setTables).catch(() => setTables([]));
      connectionsAPI.listMappings(selectedConnId).then(setMappings).catch(() => setMappings([]));
    }, [selectedConnId]);

    const handleTestNew = () => {
      setTestResult(null);
      connectionsAPI.testNew({
        name: form.name,
        db_type: form.db_type,
        host: form.host,
        port: form.port || undefined,
        database_name: form.database_name,
        username: form.username,
        password: form.password,
        schema_name: form.schema_name || undefined,
        use_ssl: form.use_ssl,
      }).then(setTestResult).catch((err) => setTestResult({ success: false, message: err?.response?.data?.detail || 'Connection failed' }));
    };

    const handleSaveConnection = async () => {
      setError(null);
      try {
        if (editingId) {
          await connectionsAPI.update(editingId, { ...form, password: form.password || undefined });
        } else {
          await connectionsAPI.create(form);
        }
        setShowForm(false);
        setEditingId(null);
        setForm({ name: '', db_type: 'sql_server', host: '', port: 1433, database_name: '', username: '', password: '', schema_name: '', use_ssl: false, description: '' });
        fetchConnections();
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save');
      }
    };

    const handleEditConnection = (c: { id: number; name: string; db_type: string; host: string; port?: number; database_name: string; username: string; schema_name?: string; description?: string }) => {
      setEditingId(c.id);
      setForm({ name: c.name, db_type: c.db_type, host: c.host, port: c.port || 1433, database_name: c.database_name, username: c.username, password: '', schema_name: c.schema_name || '', use_ssl: false, description: c.description || '' });
      setShowForm(true);
    };

    const handleDeleteConnection = async (id: number) => {
      if (!confirm('Deactivate this connection?')) return;
      setError(null);
      try {
        await connectionsAPI.delete(id);
        if (selectedConnId === id) setSelectedConnId(null);
        fetchConnections();
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete');
      }
    };

    const handleTestConnection = (id: number) => {
      setTestResult(null);
      connectionsAPI.test(id).then(setTestResult).catch((err) => setTestResult({ success: false, message: err?.response?.data?.detail || 'Test failed' }));
    };

    const handleLoadColumns = (tableName: string, schemaName?: string) => {
      if (!selectedConnId) return;
      connectionsAPI.getColumns(selectedConnId, tableName, schemaName).then(setColumns).catch(() => setColumns([]));
    };

    const handleSaveMapping = async () => {
      if (!selectedConnId || !mappingForm.source_table) return;
      setError(null);
      try {
        await connectionsAPI.createMapping(selectedConnId, {
          source_schema: mappingForm.source_schema || undefined,
          source_table: mappingForm.source_table,
          target_entity: mappingForm.target_entity,
          target_description: mappingForm.target_description || undefined,
          column_mapping: Object.keys(mappingForm.column_mapping).length ? mappingForm.column_mapping : undefined,
          sync_enabled: true,
        });
        setShowMappingForm(false);
        setMappingForm({ source_table: '', source_schema: '', target_entity: 'budgets', target_description: '', column_mapping: {} });
        connectionsAPI.listMappings(selectedConnId).then(setMappings).catch(() => {});
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save mapping');
      }
    };

    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Manage Connections</h1>
        <p className="text-gray-600">Plug your Data Warehouse (DWH). Add connections, select tables, and map columns to FPNA entities.</p>
        {error && <ErrorMessage message={error} />}
        {testResult && (
          <div className={`rounded-lg p-4 ${testResult.success ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'}`}>
            {testResult.success ? <Check className="w-5 h-5 inline mr-2" /> : <AlertCircle className="w-5 h-5 inline mr-2" />}
            {testResult.message}
          </div>
        )}

        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-900">Data Warehouse Connections</h2>
          <button onClick={() => { setShowForm(true); setEditingId(null); setForm({ name: '', db_type: 'sql_server', host: '', port: 1433, database_name: '', username: '', password: '', schema_name: '', use_ssl: false, description: '' }); }} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            <Plug className="w-4 h-4" /> Add Connection
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <h3 className="text-lg font-semibold">{editingId ? 'Edit Connection' : 'New Connection'}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Connection Name</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. DWH Production" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Database Type</label>
                <select className="w-full border rounded-lg px-3 py-2" value={form.db_type} onChange={(e) => setForm((f) => ({ ...f, db_type: e.target.value }))}>
                  <option value="sql_server">SQL Server</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.host} onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))} placeholder="localhost or server.dwh.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
                <input type="number" className="w-full border rounded-lg px-3 py-2" value={form.port} onChange={(e) => setForm((f) => ({ ...f, port: parseInt(e.target.value) || 1433 }))} placeholder="1433" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Database Name</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.database_name} onChange={(e) => setForm((f) => ({ ...f, database_name: e.target.value }))} placeholder="dwh_db" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Schema (optional)</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.schema_name} onChange={(e) => setForm((f) => ({ ...f, schema_name: e.target.value }))} placeholder="dbo" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="dwh_user" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password {editingId && '(leave blank to keep)'}</label>
                <input type="password" className="w-full border rounded-lg px-3 py-2" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="••••••••" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
              <input className="w-full border rounded-lg px-3 py-2" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Production DWH" />
            </div>
            <div className="flex gap-2">
              <button onClick={handleTestNew} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Test Connection</button>
              <button onClick={handleSaveConnection} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">Save</button>
              <button onClick={() => { setShowForm(false); setEditingId(null); setTestResult(null); }} className="px-4 py-2 text-gray-600 hover:underline">Cancel</button>
            </div>
          </div>
        )}

        {loading ? (
          <LoadingSpinner />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-200 bg-gray-50">
                  <h3 className="font-semibold text-gray-900">Connections</h3>
                </div>
                <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
                  {connections.length === 0 ? (
                    <div className="p-6 text-center text-gray-500 text-sm">No connections yet. Add one above.</div>
                  ) : (
                    connections.map((c) => (
                      <div
                        key={c.id}
                        className={`p-4 cursor-pointer hover:bg-gray-50 ${selectedConnId === c.id ? 'bg-primary-50 border-l-4 border-primary-600' : ''}`}
                      >
                        <div onClick={() => setSelectedConnId(c.id)} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Database className="w-4 h-4 text-gray-500" />
                            <span className="font-medium text-gray-900">{c.name}</span>
                          </div>
                          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                            <button onClick={() => handleEditConnection(c)} className="p-1 text-gray-500 hover:text-primary-600" title="Edit"><Pencil className="w-3.5 h-3.5" /></button>
                            <button onClick={() => handleDeleteConnection(c.id)} className="p-1 text-gray-500 hover:text-red-600" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div>
                        </div>
                        <div onClick={() => setSelectedConnId(c.id)}>
                          <p className="text-xs text-gray-500 mt-1">{c.db_type} • {c.host}</p>
                          {!c.is_active && <span className="text-xs text-amber-600">Inactive</span>}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
            <div className="lg:col-span-2 space-y-4">
              {selectedConnId ? (
                <>
                  <div className="flex justify-between items-center">
                    <h3 className="font-semibold text-gray-900">Tables & Mappings</h3>
                    <div className="flex gap-2">
                      <button onClick={() => handleTestConnection(selectedConnId)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Test</button>
                      <button onClick={() => { setShowMappingForm(true); setMappingForm({ source_table: '', source_schema: '', target_entity: 'budgets', target_description: '', column_mapping: {} }); }} className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700">Add Mapping</button>
                    </div>
                  </div>
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="p-4 border-b border-gray-200">
                      <h4 className="font-medium text-gray-900">Available Tables</h4>
                      <p className="text-sm text-gray-500">Select a table to map to an FPNA entity</p>
                    </div>
                    <div className="p-4 max-h-48 overflow-y-auto">
                      {tables.length === 0 ? (
                        <p className="text-sm text-gray-500">No tables or failed to load. Ensure connection has password saved.</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-2">
                          {tables.map((t) => (
                            <button
                              key={t.full_name}
                              onClick={() => { setMappingForm((f) => ({ ...f, source_table: t.table_name, source_schema: t.schema_name || '' })); handleLoadColumns(t.table_name, t.schema_name); setShowMappingForm(true); }}
                              className="text-left px-3 py-2 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50/50 text-sm"
                            >
                              {t.full_name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="p-4 border-b border-gray-200">
                      <h4 className="font-medium text-gray-900">Table Mappings</h4>
                      <p className="text-sm text-gray-500">DWH table → FPNA entity</p>
                    </div>
                    <div className="divide-y divide-gray-100">
                      {mappings.length === 0 ? (
                        <div className="p-6 text-center text-gray-500 text-sm">No mappings. Add one to connect DWH tables to FPNA.</div>
                      ) : (
                        mappings.map((m) => (
                          <div key={m.id} className="p-4 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm">{m.source_schema ? `${m.source_schema}.` : ''}{m.source_table}</span>
                              <ArrowRight className="w-4 h-4 text-gray-400" />
                              <span className="font-medium text-primary-600">{m.target_entity}</span>
                            </div>
                            {m.column_mapping && Object.keys(m.column_mapping).length > 0 && (
                              <span className="text-xs text-gray-500">{Object.keys(m.column_mapping).length} columns mapped</span>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  {showMappingForm && (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
                      <h4 className="font-semibold text-gray-900">Map Table to FPNA Entity</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Source Table</label>
                          <input className="w-full border rounded-lg px-3 py-2 bg-gray-50" value={mappingForm.source_table} readOnly />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Target FPNA Entity</label>
                          <select className="w-full border rounded-lg px-3 py-2" value={mappingForm.target_entity} onChange={(e) => setMappingForm((f) => ({ ...f, target_entity: e.target.value }))}>
                            {FPNA_TARGET_ENTITIES.map((e) => (
                              <option key={e.value} value={e.value}>{e.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      {columns.length > 0 && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Column Mapping (optional) — DWH column → FPNA column</label>
                          <div className="space-y-2 max-h-40 overflow-y-auto">
                            {columns.map((col) => (
                              <div key={col.column_name} className="flex items-center gap-3">
                                <span className="text-sm font-mono text-gray-700 w-40">{col.column_name}</span>
                                <ArrowRight className="w-4 h-4 text-gray-400" />
                                <input className="flex-1 border rounded px-2 py-1 text-sm" placeholder="target column" value={mappingForm.column_mapping[col.column_name] || ''} onChange={(e) => setMappingForm((f) => ({ ...f, column_mapping: { ...f.column_mapping, [col.column_name]: e.target.value } }))} />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="flex gap-2">
                        <button onClick={handleSaveMapping} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">Save Mapping</button>
                        <button onClick={() => setShowMappingForm(false)} className="px-4 py-2 text-gray-600 hover:underline">Cancel</button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-500">
                  <Database className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>Select a connection to view tables and configure mappings.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  // ETL Page - data sync between databases
  const ETLPage = () => {
    const [jobs, setJobs] = useState<{ id: number; name: string; source_type: string; source_table: string; target_type: string; target_table: string; load_mode: string }[]>([]);
    const [connections, setConnections] = useState<{ id: number; name: string }[]>([]);
    const [fpnaTables, setFpnaTables] = useState<{ schema_name: string; table_name: string; full_name: string }[]>([]);
    const [loading, setLoading] = useState(false);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({
      name: '', description: '',
      source_type: 'dwh_connection' as string, source_connection_id: null as number | null, source_schema: '', source_table: '',
      target_type: 'fpna_app' as string, target_connection_id: null as number | null, target_schema: '', target_table: '',
      column_mapping: {} as Record<string, string>, create_target_if_missing: false, load_mode: 'full_replace'
    });
    const [sourceTables, setSourceTables] = useState<{ full_name: string }[]>([]);
    const [targetTables, setTargetTables] = useState<{ full_name: string }[]>([]);
    const [runResult, setRunResult] = useState<{ status: string; rows_loaded: number; error_message?: string } | null>(null);
    const [runs, setRuns] = useState<{ id: number; status: string; rows_extracted: number; rows_loaded: number; started_at: string }[]>([]);
    const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

    const fetchJobs = () => { setLoading(true); etlAPI.listJobs().then(setJobs).catch(() => setJobs([])).finally(() => setLoading(false)); };
    const fetchConnections = () => { connectionsAPI.list().then(setConnections).catch(() => setConnections([])); };
    const fetchFpnaTables = () => { etlAPI.getFpnaTables().then(setFpnaTables).catch(() => setFpnaTables([])); };

    useEffect(() => { fetchJobs(); fetchConnections(); fetchFpnaTables(); }, []);

    useEffect(() => {
      if (form.source_type === 'fpna_app') setSourceTables(fpnaTables.map((t) => ({ full_name: t.full_name })));
      else if (form.source_connection_id) connectionsAPI.getTables(form.source_connection_id).then((t: { full_name: string }[]) => setSourceTables(t)).catch(() => setSourceTables([]));
      else setSourceTables([]);
    }, [form.source_type, form.source_connection_id, fpnaTables]);

    useEffect(() => {
      if (form.target_type === 'fpna_app') setTargetTables(fpnaTables.map((t) => ({ full_name: t.full_name })));
      else if (form.target_connection_id) connectionsAPI.getTables(form.target_connection_id).then((t: { full_name: string }[]) => setTargetTables(t)).catch(() => setTargetTables([]));
      else setTargetTables([]);
    }, [form.target_type, form.target_connection_id, fpnaTables]);

    useEffect(() => {
      if (selectedJobId) etlAPI.getJobRuns(selectedJobId).then(setRuns).catch(() => setRuns([]));
    }, [selectedJobId]);

    const handleSaveJob = async () => {
      setError(null);
      try {
        await etlAPI.createJob({
          name: form.name,
          description: form.description || undefined,
          source_type: form.source_type,
          source_connection_id: form.source_type === 'dwh_connection' ? form.source_connection_id! : undefined,
          source_schema: form.source_schema || undefined,
          source_table: form.source_table,
          target_type: form.target_type,
          target_connection_id: form.target_type === 'dwh_connection' ? form.target_connection_id! : undefined,
          target_schema: form.target_schema || undefined,
          target_table: form.target_table,
          column_mapping: Object.keys(form.column_mapping).length ? form.column_mapping : undefined,
          create_target_if_missing: form.create_target_if_missing,
          load_mode: form.load_mode,
        });
        setShowForm(false);
        setForm({ name: '', description: '', source_type: 'dwh_connection', source_connection_id: null, source_schema: '', source_table: '', target_type: 'fpna_app', target_connection_id: null, target_schema: '', target_table: '', column_mapping: {}, create_target_if_missing: false, load_mode: 'full_replace' });
        fetchJobs();
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create job');
      }
    };

    const handleRunJob = async (jobId: number) => {
      setError(null); setRunResult(null);
      try {
        const r = await etlAPI.runJob(jobId);
        setRunResult(r);
        setSelectedJobId(jobId);
        etlAPI.getJobRuns(jobId).then(setRuns).catch(() => {});
        if (r.status === 'failed' && r.error_message) setError(r.error_message);
      } catch (err: unknown) {
        const ax = err as { response?: { status?: number; data?: { detail?: string } }; message?: string };
        const detail = ax?.response?.data?.detail;
        const msg = detail || (ax?.response?.status === 404 ? 'ETL job or endpoint not found. Restart backend and refresh job list.' : 'Run failed');
        setError(msg);
      }
    };

    const parseTable = (full: string) => {
      const parts = full.split('.');
      if (parts.length >= 2) return { schema: parts[0], table: parts[parts.length - 1] };
      return { schema: '', table: full };
    };

    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">ETL</h1>
        <p className="text-gray-600">Sync data between databases: DWH ↔ FPNA app. Existing table + mapping or create new table in destination.</p>
        {error && <ErrorMessage message={error} />}
        {runResult && (
          <div className={`rounded-lg p-4 ${runResult.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
            {runResult.status === 'success' ? <Check className="w-5 h-5 inline mr-2 text-green-600" /> : <AlertCircle className="w-5 h-5 inline mr-2 text-red-600" />}
            {runResult.status === 'success' ? `Loaded ${runResult.rows_loaded} rows` : runResult.error_message}
          </div>
        )}

        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-900">ETL Jobs</h2>
          <button onClick={() => { setShowForm(true); setForm({ name: '', description: '', source_type: 'dwh_connection', source_connection_id: null, source_schema: '', source_table: '', target_type: 'fpna_app', target_connection_id: null, target_schema: '', target_table: '', column_mapping: {}, create_target_if_missing: false, load_mode: 'full_replace' }); }} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            <Plus className="w-4 h-4" /> New Job
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <h3 className="text-lg font-semibold">Create ETL Job</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2"><label className="block text-sm font-medium text-gray-700 mb-1">Job Name</label><input className="w-full border rounded-lg px-3 py-2" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. DWH to FPNA budgets" /></div>
              <div className="md:col-span-2 font-medium text-gray-700">Source</div>
              <div><label className="block text-sm text-gray-600 mb-1">Type</label><select className="w-full border rounded px-3 py-2" value={form.source_type} onChange={(e) => setForm((f) => ({ ...f, source_type: e.target.value, source_connection_id: null }))}><option value="dwh_connection">DWH Connection</option><option value="fpna_app">FPNA App DB</option></select></div>
              <div>{form.source_type === 'dwh_connection' && (<><label className="block text-sm text-gray-600 mb-1">Connection</label><select className="w-full border rounded px-3 py-2" value={form.source_connection_id ?? ''} onChange={(e) => setForm((f) => ({ ...f, source_connection_id: e.target.value ? Number(e.target.value) : null }))}><option value="">— Select —</option>{connections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></>)}</div>
              <div><label className="block text-sm text-gray-600 mb-1">Table</label><select className="w-full border rounded px-3 py-2" value={form.source_schema ? `${form.source_schema}.${form.source_table}` : form.source_table} onChange={(e) => { const v = e.target.value; const p = parseTable(v); setForm((f) => ({ ...f, source_table: p.table, source_schema: p.schema || '' })); }}><option value="">— Select —</option>{sourceTables.map((t) => <option key={t.full_name} value={t.full_name}>{t.full_name}</option>)}</select></div>
              <div className="md:col-span-2 font-medium text-gray-700 mt-4">Target</div>
              <div><label className="block text-sm text-gray-600 mb-1">Type</label><select className="w-full border rounded px-3 py-2" value={form.target_type} onChange={(e) => setForm((f) => ({ ...f, target_type: e.target.value, target_connection_id: null }))}><option value="fpna_app">FPNA App DB</option><option value="dwh_connection">DWH Connection</option></select></div>
              <div>{form.target_type === 'dwh_connection' && (<><label className="block text-sm text-gray-600 mb-1">Connection</label><select className="w-full border rounded px-3 py-2" value={form.target_connection_id ?? ''} onChange={(e) => setForm((f) => ({ ...f, target_connection_id: e.target.value ? Number(e.target.value) : null }))}><option value="">— Select —</option>{connections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></>)}</div>
              <div><label className="block text-sm text-gray-600 mb-1">Table</label><select className="w-full border rounded px-3 py-2" value={form.target_schema ? `${form.target_schema}.${form.target_table}` : form.target_table} onChange={(e) => { const v = e.target.value; const p = parseTable(v); setForm((f) => ({ ...f, target_table: p.table, target_schema: p.schema || '' })); }}><option value="">— Select —</option>{targetTables.map((t) => <option key={t.full_name} value={t.full_name}>{t.full_name}</option>)}</select><input className="w-full border rounded px-3 py-2 mt-1" placeholder="Or type new table name" value={form.target_table && !targetTables.some((t) => t.full_name === form.target_table) ? form.target_table : ''} onChange={(e) => setForm((f) => ({ ...f, target_table: e.target.value, target_schema: '' }))} /></div>
              <div><label className="block text-sm text-gray-600 mb-1">Create target if missing</label><input type="checkbox" checked={form.create_target_if_missing} onChange={(e) => setForm((f) => ({ ...f, create_target_if_missing: e.target.checked }))} /></div>
              <div><label className="block text-sm text-gray-600 mb-1">Load mode</label><select className="w-full border rounded px-3 py-2" value={form.load_mode} onChange={(e) => setForm((f) => ({ ...f, load_mode: e.target.value }))}><option value="full_replace">Full replace (truncate + insert)</option><option value="append">Append only</option></select></div>
            </div>
            <div className="flex gap-2 mt-4"><button onClick={handleSaveJob} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">Create Job</button><button onClick={() => setShowForm(false)} className="px-4 py-2 text-gray-600 hover:underline">Cancel</button></div>
          </div>
        )}

        {loading ? <LoadingSpinner /> : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-200"><h3 className="font-semibold text-gray-900">Jobs</h3></div>
                <div className="divide-y divide-gray-100">
                  {jobs.length === 0 ? <div className="p-6 text-center text-gray-500">No ETL jobs. Create one above.</div> : jobs.map((j) => (
                    <div key={j.id} className={`p-4 flex items-center justify-between ${selectedJobId === j.id ? 'bg-primary-50' : ''}`}>
                      <div onClick={() => setSelectedJobId(j.id)} className="flex-1 cursor-pointer">
                        <div className="flex items-center gap-2"><span className="font-medium">{j.name}</span><span className="text-xs text-gray-500">{j.load_mode}</span></div>
                        <div className="text-sm text-gray-600 mt-1"><ArrowRight className="w-3 h-3 inline mr-1" />{j.source_table} → {j.target_table}</div>
                      </div>
                      <button onClick={() => handleRunJob(j.id)} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"><Play className="w-4 h-4" /> Run</button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-200"><h3 className="font-semibold text-gray-900">Run History</h3></div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {!selectedJobId ? <p className="text-sm text-gray-500">Select a job to see run history.</p> : runs.length === 0 ? <p className="text-sm text-gray-500">No runs yet.</p> : runs.map((r) => (
                    <div key={r.id} className="py-2 border-b border-gray-100 last:border-0">
                      <div className="flex justify-between"><span className={r.status === 'success' ? 'text-green-600' : 'text-red-600'}>{r.status}</span><span className="text-xs text-gray-500">{r.started_at}</span></div>
                      <div className="text-xs text-gray-600">{r.rows_extracted} → {r.rows_loaded} rows</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Approvals Page - pending budgets for approve/reject
  const ApprovalsPage = () => {
    const [pendingBudgets, setPendingBudgets] = useState<{ id: number; budget_code: string; fiscal_year: number; department: string | null; branch: string | null; total_amount: number; status: string; current_level: number }[]>([]);
    const [loadingApprovals, setLoadingApprovals] = useState(false);
    const [comment, setComment] = useState<Record<number, string>>({});

    useEffect(() => {
      setLoadingApprovals(true);
      approvalsAPI
        .listPending()
        .then(setPendingBudgets)
        .catch(() => setPendingBudgets([]))
        .finally(() => setLoadingApprovals(false));
    }, [currentPage]);

    const handleApprove = async (budgetId: number) => {
      setError(null);
      try {
        await approvalsAPI.approve(budgetId, comment[budgetId]);
        setPendingBudgets((p) => p.filter((b) => b.id !== budgetId));
        setComment((c) => ({ ...c, [budgetId]: '' }));
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to approve');
      }
    };

    const handleReject = async (budgetId: number) => {
      setError(null);
      try {
        await approvalsAPI.reject(budgetId, comment[budgetId]);
        setPendingBudgets((p) => p.filter((b) => b.id !== budgetId));
        setComment((c) => ({ ...c, [budgetId]: '' }));
      } catch (err: unknown) {
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to reject');
      }
    };

    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Approvals</h1>
        <p className="text-gray-600">Review and approve or reject budgets pending at your approval level.</p>
        {error && <ErrorMessage message={error} />}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Pending Your Approval</h2>
          </div>
          {loadingApprovals ? (
            <LoadingSpinner />
          ) : pendingBudgets.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <Check className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>No budgets pending your approval.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Budget Code</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Year</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Dept / Branch</th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-700 uppercase">Amount</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Level</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Comment</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {pendingBudgets.map((b) => (
                    <tr key={b.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{b.budget_code}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{b.fiscal_year}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{b.department || '-'} / {b.branch || '-'}</td>
                      <td className="px-6 py-4 text-sm font-semibold text-right text-gray-900">${Number(b.total_amount).toLocaleString()}</td>
                      <td className="px-6 py-4 text-sm"><StatusBadge status={b.status} /></td>
                      <td className="px-6 py-4">
                        <input
                          className="w-48 border rounded px-2 py-1 text-sm"
                          placeholder="Optional comment"
                          value={comment[b.id] ?? ''}
                          onChange={(e) => setComment((c) => ({ ...c, [b.id]: e.target.value }))}
                        />
                      </td>
                      <td className="px-6 py-4 flex gap-2">
                        <button onClick={() => handleApprove(b.id)} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">Approve</button>
                        <button onClick={() => handleReject(b.id)} className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700">Reject</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Universal Upload Page - supports multiple data sources
  const UniversalUpload = () => {
    type SourceType = 'excel' | 'csv' | 'sql_server' | 'postgresql' | 'api';
    type WizardStep = 'source' | 'configure' | 'mapping' | 'import';
    
    const [step, setStep] = useState<WizardStep>('source');
    const [sourceType, setSourceType] = useState<SourceType | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const [previewData, setPreviewData] = useState<{ columns: { name: string; type: string }[]; data: Record<string, unknown>[]; row_count: number } | null>(null);
    const [suggestedMappings, setSuggestedMappings] = useState<ColumnMappingSuggestion[]>([]);
    const [columnMappings, setColumnMappings] = useState<ColumnMapping[]>([]);
    const [headerValues, setHeaderValues] = useState<HeaderValues>({ fiscal_year: new Date().getFullYear(), department: '', branch: '', currency: 'USD', description: '' });
    const [validationResult, setValidationResult] = useState<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
    const [connections, setConnections] = useState<{ id: number; name: string; db_type: string }[]>([]);
    const [tables, setTables] = useState<{ schema_name: string; table_name: string; full_name: string }[]>([]);
    const [dbConfig, setDbConfig] = useState<{ connection_id: number | null; schema_name: string; table_name: string; where_clause: string }>({ connection_id: null, schema_name: '', table_name: '', where_clause: '' });
    const [apiConfig, setApiConfig] = useState<{ url: string; method: string; auth_type: string; auth_credentials: Record<string, string>; data_path: string; headers: Record<string, string> }>({ url: '', method: 'GET', auth_type: 'none', auth_credentials: {}, data_path: '', headers: {} });
    const [targetSchema, setTargetSchema] = useState<{ name: string; type: string; required: boolean; description: string }[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [importResult, setImportResult] = useState<{ success: boolean; message: string; budget_id?: number; budget_code?: string } | null>(null);

    useEffect(() => {
      budgetUploadAPI.getTargetSchema().then(schema => {
        setTargetSchema(schema.line_item_fields);
      }).catch(() => {});
      connectionsAPI.list().then(setConnections).catch(() => {});
    }, []);

    useEffect(() => {
      if (dbConfig.connection_id) {
        connectionsAPI.getTables(dbConfig.connection_id).then(setTables).catch(() => setTables([]));
      }
    }, [dbConfig.connection_id]);

    const handleDrag = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(e.type === "dragenter" || e.type === "dragover");
    };

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      if (e.dataTransfer.files?.[0]) setUploadedFile(e.dataTransfer.files[0]);
    };

    const handlePreview = async () => {
      setIsLoading(true);
      setError(null);
      try {
        let result;
        if (sourceType === 'excel' || sourceType === 'csv') {
          if (!uploadedFile) throw new Error('Please select a file');
          result = await budgetUploadAPI.previewFile(uploadedFile, sourceType, { rows: 10 });
        } else if (sourceType === 'sql_server' || sourceType === 'postgresql') {
          if (!dbConfig.connection_id || !dbConfig.table_name) throw new Error('Please select connection and table');
          result = await budgetUploadAPI.previewDatabase(sourceType, { connection_id: dbConfig.connection_id, schema_name: dbConfig.schema_name || undefined, table_name: dbConfig.table_name, where_clause: dbConfig.where_clause || undefined }, 10);
        } else if (sourceType === 'api') {
          if (!apiConfig.url) throw new Error('Please enter API URL');
          result = await budgetUploadAPI.previewAPI({ url: apiConfig.url, method: apiConfig.method, auth_type: apiConfig.auth_type as 'none' | 'basic' | 'bearer' | 'api_key', auth_credentials: apiConfig.auth_credentials, data_path: apiConfig.data_path || undefined, headers: Object.keys(apiConfig.headers).length ? apiConfig.headers : undefined }, 10);
        }
        if (result?.success) {
          setPreviewData({ columns: result.columns, data: result.data, row_count: result.row_count });
          setSuggestedMappings(result.suggested_mappings || []);
          const initialMappings = (result.suggested_mappings || []).filter(s => s.suggested_target).map(s => ({ source_column: s.source_column, target_field: s.suggested_target! }));
          setColumnMappings(initialMappings);
          setStep('mapping');
        } else {
          throw new Error(result?.message || 'Preview failed');
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Preview failed');
      } finally {
        setIsLoading(false);
      }
    };

    const handleValidateMapping = async () => {
      if (!previewData) return;
      try {
        const result = await budgetUploadAPI.validateMapping(previewData.columns.map(c => c.name), columnMappings, 'line_items');
        setValidationResult(result);
      } catch {
        setValidationResult({ valid: false, errors: ['Validation failed'], warnings: [] });
      }
    };

    const handleImport = async () => {
      setIsLoading(true);
      setError(null);
      try {
        let result;
        if (sourceType === 'excel' || sourceType === 'csv') {
          if (!uploadedFile) throw new Error('No file selected');
          result = await budgetUploadAPI.importFromFile(uploadedFile, sourceType, columnMappings, headerValues, user?.username);
        } else if (sourceType === 'sql_server' || sourceType === 'postgresql') {
          result = await budgetUploadAPI.importFromDatabase(sourceType, { connection_id: dbConfig.connection_id!, schema_name: dbConfig.schema_name || undefined, table_name: dbConfig.table_name, where_clause: dbConfig.where_clause || undefined }, columnMappings, headerValues, user?.username);
        } else if (sourceType === 'api') {
          result = await budgetUploadAPI.importFromAPI({ url: apiConfig.url, method: apiConfig.method, auth_type: apiConfig.auth_type as 'none' | 'basic' | 'bearer' | 'api_key', auth_credentials: apiConfig.auth_credentials, data_path: apiConfig.data_path || undefined }, columnMappings, headerValues, user?.username);
        }
        if (result?.success) {
          setImportResult(result);
          setStep('import');
          fetchBudgets();
        } else {
          throw new Error(result?.message || 'Import failed');
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Import failed');
      } finally {
        setIsLoading(false);
      }
    };

    const resetWizard = () => {
      setStep('source');
      setSourceType(null);
      setUploadedFile(null);
      setPreviewData(null);
      setSuggestedMappings([]);
      setColumnMappings([]);
      setValidationResult(null);
      setImportResult(null);
      setDbConfig({ connection_id: null, schema_name: '', table_name: '', where_clause: '' });
      setApiConfig({ url: '', method: 'GET', auth_type: 'none', auth_credentials: {}, data_path: '', headers: {} });
    };

    const sourceOptions = [
      { type: 'excel' as SourceType, icon: FileSpreadsheet, label: 'Excel', desc: '.xlsx, .xls files' },
      { type: 'csv' as SourceType, icon: FileText, label: 'CSV', desc: 'Comma-separated values' },
      { type: 'sql_server' as SourceType, icon: Database, label: 'SQL Server', desc: 'Microsoft SQL Server' },
      { type: 'postgresql' as SourceType, icon: Database, label: 'PostgreSQL', desc: 'PostgreSQL database' },
      { type: 'api' as SourceType, icon: Globe, label: 'REST API', desc: 'External API endpoint' },
    ];

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Upload Budget</h1>
          {step !== 'source' && (
            <button onClick={resetWizard} className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1">
              <X className="w-4 h-4" /> Start Over
            </button>
          )}
        </div>

        {/* Progress Steps */}
        <div className="flex items-center gap-2 text-sm">
          {['source', 'configure', 'mapping', 'import'].map((s, i) => (
            <React.Fragment key={s}>
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${step === s ? 'bg-primary-100 text-primary-700 font-medium' : s === 'import' && importResult?.success ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                <span className="w-5 h-5 rounded-full bg-current bg-opacity-20 flex items-center justify-center text-xs">{i + 1}</span>
                {s === 'source' ? 'Source' : s === 'configure' ? 'Configure' : s === 'mapping' ? 'Map Columns' : 'Import'}
              </div>
              {i < 3 && <ChevronRight className="w-4 h-4 text-gray-300" />}
            </React.Fragment>
          ))}
        </div>

        {error && <ErrorMessage message={error} />}

        {/* Step 1: Select Source */}
        {step === 'source' && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Select Data Source</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {sourceOptions.map(opt => (
                <button key={opt.type} onClick={() => { setSourceType(opt.type); setStep('configure'); }} className={`p-4 border-2 rounded-xl text-center hover:border-primary-500 hover:bg-primary-50 transition-colors ${sourceType === opt.type ? 'border-primary-500 bg-primary-50' : 'border-gray-200'}`}>
                  <opt.icon className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                  <p className="font-medium text-gray-900">{opt.label}</p>
                  <p className="text-xs text-gray-500 mt-1">{opt.desc}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Configure Source */}
        {step === 'configure' && sourceType && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Configure {sourceOptions.find(o => o.type === sourceType)?.label} Source</h2>
            
            {(sourceType === 'excel' || sourceType === 'csv') && (
              <div className="space-y-4">
                <div className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${dragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'}`} onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600 mb-3">Drop your {sourceType.toUpperCase()} file here or</p>
                  <input type="file" accept={sourceType === 'excel' ? '.xlsx,.xls' : '.csv'} className="hidden" id="file-upload-universal" onChange={(e) => setUploadedFile(e.target.files?.[0] || null)} />
                  <label htmlFor="file-upload-universal" className="inline-block px-4 py-2 bg-primary-600 text-white rounded-lg cursor-pointer hover:bg-primary-700">Choose File</label>
                </div>
                {uploadedFile && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="w-5 h-5 text-green-600" />
                      <span className="font-medium">{uploadedFile.name}</span>
                      <span className="text-sm text-gray-500">({(uploadedFile.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button onClick={() => setUploadedFile(null)} className="text-red-600 hover:text-red-700"><X className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
            )}

            {(sourceType === 'sql_server' || sourceType === 'postgresql') && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Connection</label>
                    <select value={dbConfig.connection_id || ''} onChange={(e) => setDbConfig({ ...dbConfig, connection_id: Number(e.target.value) || null, table_name: '' })} className="w-full border rounded-lg px-3 py-2">
                      <option value="">Select connection...</option>
                      {connections.filter(c => c.db_type === sourceType).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Table</label>
                    <select value={dbConfig.table_name} onChange={(e) => { const t = tables.find(t => t.full_name === e.target.value); setDbConfig({ ...dbConfig, table_name: t?.table_name || '', schema_name: t?.schema_name || '' }); }} className="w-full border rounded-lg px-3 py-2" disabled={!dbConfig.connection_id}>
                      <option value="">Select table...</option>
                      {tables.map(t => <option key={t.full_name} value={t.full_name}>{t.full_name}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">WHERE Clause (optional)</label>
                  <input type="text" value={dbConfig.where_clause} onChange={(e) => setDbConfig({ ...dbConfig, where_clause: e.target.value })} placeholder="e.g., fiscal_year = 2025" className="w-full border rounded-lg px-3 py-2" />
                </div>
              </div>
            )}

            {sourceType === 'api' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API URL</label>
                  <input type="text" value={apiConfig.url} onChange={(e) => setApiConfig({ ...apiConfig, url: e.target.value })} placeholder="https://api.example.com/data" className="w-full border rounded-lg px-3 py-2" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Method</label>
                    <select value={apiConfig.method} onChange={(e) => setApiConfig({ ...apiConfig, method: e.target.value })} className="w-full border rounded-lg px-3 py-2">
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Auth Type</label>
                    <select value={apiConfig.auth_type} onChange={(e) => setApiConfig({ ...apiConfig, auth_type: e.target.value })} className="w-full border rounded-lg px-3 py-2">
                      <option value="none">None</option>
                      <option value="basic">Basic Auth</option>
                      <option value="bearer">Bearer Token</option>
                      <option value="api_key">API Key</option>
                    </select>
                  </div>
                </div>
                {apiConfig.auth_type === 'basic' && (
                  <div className="grid grid-cols-2 gap-4">
                    <input type="text" placeholder="Username" value={apiConfig.auth_credentials.username || ''} onChange={(e) => setApiConfig({ ...apiConfig, auth_credentials: { ...apiConfig.auth_credentials, username: e.target.value } })} className="border rounded-lg px-3 py-2" />
                    <input type="password" placeholder="Password" value={apiConfig.auth_credentials.password || ''} onChange={(e) => setApiConfig({ ...apiConfig, auth_credentials: { ...apiConfig.auth_credentials, password: e.target.value } })} className="border rounded-lg px-3 py-2" />
                  </div>
                )}
                {apiConfig.auth_type === 'bearer' && (
                  <input type="text" placeholder="Bearer Token" value={apiConfig.auth_credentials.token || ''} onChange={(e) => setApiConfig({ ...apiConfig, auth_credentials: { token: e.target.value } })} className="w-full border rounded-lg px-3 py-2" />
                )}
                {apiConfig.auth_type === 'api_key' && (
                  <div className="grid grid-cols-2 gap-4">
                    <input type="text" placeholder="API Key" value={apiConfig.auth_credentials.key || ''} onChange={(e) => setApiConfig({ ...apiConfig, auth_credentials: { ...apiConfig.auth_credentials, key: e.target.value } })} className="border rounded-lg px-3 py-2" />
                    <input type="text" placeholder="Header Name (e.g., X-API-Key)" value={apiConfig.auth_credentials.header_name || ''} onChange={(e) => setApiConfig({ ...apiConfig, auth_credentials: { ...apiConfig.auth_credentials, header_name: e.target.value } })} className="border rounded-lg px-3 py-2" />
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Data Path (optional)</label>
                  <input type="text" value={apiConfig.data_path} onChange={(e) => setApiConfig({ ...apiConfig, data_path: e.target.value })} placeholder="e.g., data.items or results" className="w-full border rounded-lg px-3 py-2" />
                </div>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setStep('source')} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Back</button>
              <button onClick={handlePreview} disabled={isLoading || ((sourceType === 'excel' || sourceType === 'csv') && !uploadedFile) || ((sourceType === 'sql_server' || sourceType === 'postgresql') && !dbConfig.table_name) || (sourceType === 'api' && !apiConfig.url)} className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                {isLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Loading...</> : <><Table className="w-4 h-4" /> Preview Data</>}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Column Mapping */}
        {step === 'mapping' && previewData && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Map Columns to Budget Fields</h2>
              <p className="text-sm text-gray-600 mb-4">Map your source columns to the required budget fields. Required fields are marked with *.</p>
              
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h3 className="font-medium text-gray-700 mb-3">Column Mapping</h3>
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {previewData.columns.map(col => {
                      const mapping = columnMappings.find(m => m.source_column === col.name);
                      const suggestion = suggestedMappings.find(s => s.source_column === col.name);
                      return (
                        <div key={col.name} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                          <div className="flex-1">
                            <p className="text-sm font-medium">{col.name}</p>
                            <p className="text-xs text-gray-500">{col.type}</p>
                          </div>
                          <ArrowRight className="w-4 h-4 text-gray-400" />
                          <select value={mapping?.target_field || ''} onChange={(e) => { const newMappings = columnMappings.filter(m => m.source_column !== col.name); if (e.target.value) newMappings.push({ source_column: col.name, target_field: e.target.value }); setColumnMappings(newMappings); setValidationResult(null); }} className={`w-40 text-sm border rounded px-2 py-1 ${suggestion?.required && !mapping ? 'border-red-300 bg-red-50' : ''}`}>
                            <option value="">-- Skip --</option>
                            {targetSchema.map(f => <option key={f.name} value={f.name}>{f.name}{f.required ? ' *' : ''}</option>)}
                          </select>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium text-gray-700 mb-3">Budget Header</h3>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Fiscal Year *</label>
                      <input type="number" value={headerValues.fiscal_year} onChange={(e) => setHeaderValues({ ...headerValues, fiscal_year: Number(e.target.value) })} className="w-full border rounded-lg px-3 py-2" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Department</label>
                      <input type="text" value={headerValues.department || ''} onChange={(e) => setHeaderValues({ ...headerValues, department: e.target.value })} className="w-full border rounded-lg px-3 py-2" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Branch</label>
                      <input type="text" value={headerValues.branch || ''} onChange={(e) => setHeaderValues({ ...headerValues, branch: e.target.value })} className="w-full border rounded-lg px-3 py-2" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Currency</label>
                      <input type="text" value={headerValues.currency || 'USD'} onChange={(e) => setHeaderValues({ ...headerValues, currency: e.target.value })} className="w-full border rounded-lg px-3 py-2" />
                    </div>
                  </div>
                </div>
              </div>

              {validationResult && (
                <div className={`mt-4 p-3 rounded-lg ${validationResult.valid ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  {validationResult.valid ? (
                    <p className="text-green-700 flex items-center gap-2"><Check className="w-4 h-4" /> Mapping is valid. Ready to import.</p>
                  ) : (
                    <div>
                      <p className="text-red-700 font-medium">Validation Errors:</p>
                      <ul className="text-sm text-red-600 mt-1 list-disc list-inside">{validationResult.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
                    </div>
                  )}
                  {validationResult.warnings.length > 0 && (
                    <div className="mt-2">
                      <p className="text-yellow-700 text-sm">Warnings:</p>
                      <ul className="text-sm text-yellow-600 list-disc list-inside">{validationResult.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-3 mt-6">
                <button onClick={() => setStep('configure')} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Back</button>
                <button onClick={handleValidateMapping} className="px-4 py-2 border border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50">Validate Mapping</button>
                <button onClick={handleImport} disabled={isLoading || !validationResult?.valid} className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                  {isLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Importing...</> : <><Upload className="w-4 h-4" /> Import Budget</>}
                </button>
              </div>
            </div>

            {/* Data Preview */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="font-medium text-gray-700 mb-3">Data Preview ({previewData.row_count} rows shown)</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>{previewData.columns.map(col => <th key={col.name} className="px-3 py-2 text-left font-medium text-gray-600">{col.name}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {previewData.data.slice(0, 5).map((row, i) => (
                      <tr key={i}>{previewData.columns.map(col => <td key={col.name} className="px-3 py-2 text-gray-700">{String(row[col.name] ?? '')}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Import Result */}
        {step === 'import' && importResult && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
            {importResult.success ? (
              <>
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Import Successful!</h2>
                <p className="text-gray-600 mb-4">{importResult.message}</p>
                <p className="text-sm text-gray-500 mb-6">Budget Code: <span className="font-mono font-medium">{importResult.budget_code}</span></p>
                <div className="flex gap-3 justify-center">
                  <button onClick={resetWizard} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Upload Another</button>
                  <button onClick={async () => { try { const budget = await budgetAPI.get(importResult.budget_id!); setSelectedBudget(budget); setCurrentPage('details'); } catch { setCurrentPage('dashboard'); } }} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">View Budget</button>
                </div>
              </>
            ) : (
              <>
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <X className="w-8 h-8 text-red-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Import Failed</h2>
                <p className="text-red-600 mb-6">{importResult.message}</p>
                <button onClick={() => setStep('mapping')} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">Try Again</button>
              </>
            )}
          </div>
        )}

        {/* Template Download */}
        {step === 'source' && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="bg-blue-100 p-3 rounded-lg">
                <Download className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Need an Excel template?</h3>
                <p className="text-gray-600 mb-4">Download our Excel template to ensure your data is in the correct format for quick upload.</p>
                <button onClick={handleDownloadTemplate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Download Template</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Collapsible Navigation State
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['budgeting', 'fpna']));

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  // Navigation Item Component
  const NavItem = ({ page, icon: Icon, label, indent = false }: { page: string; icon: React.ElementType; label: string; indent?: boolean }) => (
    <button
      onClick={() => {
        setCurrentPage(page);
        if (page === 'data-entry') {
          setSelectedBudget(null);
          setError(null);
        }
      }}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${
        indent ? 'pl-10' : ''
      } ${
        currentPage === page
          ? 'bg-primary-100 text-primary-700 font-medium shadow-sm'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`}
    >
      <Icon className={`w-5 h-5 ${currentPage === page ? 'text-primary-600' : 'text-gray-400'}`} />
      <span className="text-sm">{label}</span>
    </button>
  );

  // Section Header Component
  const SectionHeader = ({ id, icon: Icon, label, expanded }: { id: string; icon: React.ElementType; label: string; expanded: boolean }) => (
    <button
      onClick={() => toggleSection(id)}
      className="w-full flex items-center justify-between px-4 py-3 text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
    >
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-gray-500" />
        <span className="font-semibold text-sm">{label}</span>
      </div>
      <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
    </button>
  );

  // Sidebar
  const Sidebar = () => (
    <div className="w-72 bg-white border-r border-gray-200 h-full flex flex-col shadow-sm">
      {/* Logo Section */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center shadow-lg">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">FP&A Platform</h1>
            <p className="text-xs text-gray-500">Financial Planning & Analysis</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {/* Dashboard - Always visible */}
        <NavItem page="dashboard" icon={TrendingUp} label="Dashboard" />
        
        {/* Budgeting Section */}
        <div className="pt-2">
          <SectionHeader id="budgeting" icon={FileSpreadsheet} label="Budget Management" expanded={expandedSections.has('budgeting')} />
          {expandedSections.has('budgeting') && (
            <div className="mt-1 space-y-0.5">
              <NavItem page="data-entry" icon={FileSpreadsheet} label="Budget Entry" indent />
              <NavItem page="upload" icon={Upload} label="Import Data" indent />
              <NavItem page="approvals" icon={Users} label="Approvals" indent />
              <NavItem page="analytics" icon={BarChart2} label="Analytics" indent />
              <NavItem page="variance-report" icon={TrendingUp} label="Plan vs Fact" indent />
            </div>
          )}
        </div>

        {/* FP&A Core Section */}
        <div className="pt-2">
          <SectionHeader id="fpna" icon={Layers} label="FP&A Core" expanded={expandedSections.has('fpna')} />
          {expandedSections.has('fpna') && (
            <div className="mt-1 space-y-0.5">
              <NavItem page="budget-planning" icon={Calculator} label="Budget Planning" indent />
              <NavItem page="coa" icon={Layers} label="Chart of Accounts" indent />
              <NavItem page="currencies" icon={Banknote} label="Currencies & FX" indent />
              <NavItem page="drivers" icon={Calculator} label="Drivers & Rules" indent />
              <NavItem page="templates" icon={LayoutTemplate} label="Budget Templates" indent />
              <NavItem page="snapshots" icon={Database} label="Baselines" indent />
            </div>
          )}
        </div>

        {/* Data Integration Section */}
        <div className="pt-2">
          <SectionHeader id="integration" icon={RefreshCw} label="Data Integration" expanded={expandedSections.has('integration')} />
          {expandedSections.has('integration') && (
            <div className="mt-1 space-y-0.5">
              <NavItem page="data-integration" icon={Database} label="Integration Hub" indent />
              <NavItem page="dwh-integration" icon={Database} label="DWH Legacy" indent />
              <NavItem page="etl" icon={RefreshCw} label="ETL Jobs" indent />
            </div>
          )}
        </div>

        {/* Settings Section */}
        <div className="pt-2">
          <SectionHeader id="settings" icon={Settings} label="Administration" expanded={expandedSections.has('settings')} />
          {expandedSections.has('settings') && (
            <div className="mt-1 space-y-0.5">
              <NavItem page="users" icon={Users} label="User Management" indent />
              <NavItem page="settings" icon={Settings} label="System Settings" indent />
            </div>
          )}
        </div>
      </nav>

      {/* User Profile Section */}
      <div className="p-4 border-t border-gray-100 bg-gray-50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center shadow">
            <span className="text-white font-semibold text-sm">
              {(user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || user?.username}</p>
            <p className="text-xs text-gray-500 truncate">{(user?.roles || []).join(', ') || 'User'}</p>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            title="Logout"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  // Dedicated login page when not authenticated
  if (!user) {
    return (
      <LoginPage
        onLogin={handleLogin}
        error={loginError}
      />
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <AppHeader
        username={user.username}
        fullName={user.full_name}
        roles={user.roles || []}
        onLogout={handleLogout}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex-1 overflow-auto">
          <div className="p-8">
          {currentPage === 'dashboard' && <Dashboard />}
          {currentPage === 'details' && <BudgetDetails />}
          {currentPage === 'data-entry' && (
            selectedBudget ? (
              <BudgetDetails />
            ) : (
              <DataEntryBudgetList
                budgets={budgets}
                loading={loading}
                error={error}
                onSelectBudget={selectBudgetForDataEntry}
                onRefresh={fetchBudgets}
              />
            )
          )}
          {currentPage === 'upload' && <UniversalUpload />}
          {currentPage === 'approvals' && <ApprovalsPage />}
          {currentPage === 'analytics' && <AnalyticsPage />}
          {currentPage === 'variance-report' && <VarianceReportPage />}
          {currentPage === 'connections' && <ManageConnectionsPage />}
          {currentPage === 'etl' && <ETLPage />}
          {currentPage === 'data-integration' && <DataIntegrationPage />}
          {currentPage === 'dwh-integration' && <DWHIntegrationPage />}
          {currentPage === 'coa' && <COAPage />}
          {currentPage === 'currencies' && <CurrenciesPage />}
          {currentPage === 'drivers' && <DriversPage />}
          {currentPage === 'templates' && <TemplatesPage />}
          {currentPage === 'snapshots' && <SnapshotsPage />}
          {currentPage === 'budget-planning' && <BudgetPlanningNew />}
          {currentPage === 'budget-planning-old' && <BudgetPlanning />}
          {currentPage === 'users' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center">
                  <Users className="w-6 h-6 text-primary-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
                  <p className="text-gray-600">Manage users, roles, and permissions</p>
                </div>
              </div>
              <div className="text-center py-12 text-gray-500">
                <Users className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium">User management module</p>
                <p className="text-sm mt-2">Configure user access and role assignments</p>
              </div>
            </div>
          )}
          {currentPage === 'settings' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center">
                  <Settings className="w-6 h-6 text-primary-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">System Settings</h1>
                  <p className="text-gray-600">Configure platform settings and preferences</p>
                </div>
              </div>
              <div className="text-center py-12 text-gray-500">
                <Settings className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium">System configuration</p>
                <p className="text-sm mt-2">Manage application settings and integrations</p>
              </div>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FPNAApp;