// src/components/FPNAApp.tsx - Connected to Real Backend
import React, { useState, useEffect } from 'react';
import { 
  Upload, 
  Download, 
  FileSpreadsheet, 
  TrendingUp, 
  DollarSign, 
  Users, 
  Calendar,
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
  Settings2,
  RefreshCw,
  Play
} from 'lucide-react';
import { budgetAPI, authAPI, approvalsAPI, connectionsAPI, etlAPI } from '../services/api';
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
  const [uploadProgress, setUploadProgress] = useState(false);

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

  const handleUpload = async () => {
    if (!uploadedFile) return;

    setUploadProgress(true);
    setError(null);
    try {
      const uploadedBy = user?.username || 'unknown';
      const result = await budgetAPI.upload(uploadedFile, uploadedBy);
      alert(`Budget uploaded successfully! Code: ${result.budget_code}`);
      setUploadedFile(null);
      setCurrentPage('dashboard');
      await fetchBudgets();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload budget');
      console.error('Error uploading:', err);
    } finally {
      setUploadProgress(false);
    }
  };

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

  // Dashboard Page
  const Dashboard = () => {
    const stats = {
      total: budgets.length,
      totalAmount: budgets.reduce((sum, b) => sum + Number(b.total_amount), 0),
      pending: budgets.filter(b => b.status.includes('PENDING')).length,
      approved: budgets.filter(b => b.status === 'APPROVED').length,
    };

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <button 
            onClick={() => setCurrentPage('upload')}
            className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Upload Budget
          </button>
        </div>

        {error && <ErrorMessage message={error} />}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Budgets</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stats.total}</p>
              </div>
              <div className="bg-blue-100 p-3 rounded-lg">
                <FileSpreadsheet className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Amount</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  ${(stats.totalAmount / 1000000).toFixed(2)}M
                </p>
              </div>
              <div className="bg-green-100 p-3 rounded-lg">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Pending Approval</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stats.pending}</p>
              </div>
              <div className="bg-yellow-100 p-3 rounded-lg">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Approved</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stats.approved}</p>
              </div>
              <div className="bg-green-100 p-3 rounded-lg">
                <Check className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Budgets Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">All Budgets</h2>
            <button 
              onClick={fetchBudgets}
              className="text-primary-600 hover:text-primary-700 text-sm font-medium"
            >
              Refresh
            </button>
          </div>
          
          {loading ? (
            <LoadingSpinner />
          ) : budgets.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <FileSpreadsheet className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>No budgets found. Upload your first budget!</p>
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
                      <td className="px-6 py-4 text-sm font-semibold text-gray-900">
                        ${Number(budget.total_amount).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <StatusBadge status={budget.status} />
                      </td>
                      <td className="px-6 py-4 text-sm space-x-2">
                        <button 
                          onClick={() => fetchBudgetDetails(budget.id)}
                          className="text-primary-600 hover:text-primary-700 font-medium"
                        >
                          View
                        </button>
                        {(budget.status === 'DRAFT' || budget.status === 'REJECTED') && (
                          <>
                            <button 
                              onClick={() => handleSubmitBudget(budget.id)}
                              className="text-green-600 hover:text-green-700 font-medium"
                            >
                              {budget.status === 'REJECTED' ? 'Resubmit' : 'Submit'}
                            </button>
                            <button 
                              onClick={() => handleDeleteBudget(budget.id)}
                              className="text-red-600 hover:text-red-700 font-medium"
                            >
                              Delete
                            </button>
                          </>
                        )}
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
        description: (selectedBudget as Record<string, unknown>).description ?? '',
        notes: (selectedBudget as Record<string, unknown>).notes ?? '',
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
              <div><label className="block text-sm text-gray-600 mb-1">Table</label><select className="w-full border rounded px-3 py-2" value={form.source_schema ? `${form.source_schema}.${form.source_table}` : form.source_table} onChange={(e) => { const v = e.target.value; const p = parseTable(v); setForm((f) => ({ ...f, source_table: p.table, source_schema: p.schema || undefined })); }}><option value="">— Select —</option>{sourceTables.map((t) => <option key={t.full_name} value={t.full_name}>{t.full_name}</option>)}</select></div>
              <div className="md:col-span-2 font-medium text-gray-700 mt-4">Target</div>
              <div><label className="block text-sm text-gray-600 mb-1">Type</label><select className="w-full border rounded px-3 py-2" value={form.target_type} onChange={(e) => setForm((f) => ({ ...f, target_type: e.target.value, target_connection_id: null }))}><option value="fpna_app">FPNA App DB</option><option value="dwh_connection">DWH Connection</option></select></div>
              <div>{form.target_type === 'dwh_connection' && (<><label className="block text-sm text-gray-600 mb-1">Connection</label><select className="w-full border rounded px-3 py-2" value={form.target_connection_id ?? ''} onChange={(e) => setForm((f) => ({ ...f, target_connection_id: e.target.value ? Number(e.target.value) : null }))}><option value="">— Select —</option>{connections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></>)}</div>
              <div><label className="block text-sm text-gray-600 mb-1">Table</label><select className="w-full border rounded px-3 py-2" value={form.target_schema ? `${form.target_schema}.${form.target_table}` : form.target_table} onChange={(e) => { const v = e.target.value; const p = parseTable(v); setForm((f) => ({ ...f, target_table: p.table, target_schema: p.schema || undefined })); }}><option value="">— Select —</option>{targetTables.map((t) => <option key={t.full_name} value={t.full_name}>{t.full_name}</option>)}</select><input className="w-full border rounded px-3 py-2 mt-1" placeholder="Or type new table name" value={form.target_table && !targetTables.some((t) => t.full_name === form.target_table) ? form.target_table : ''} onChange={(e) => setForm((f) => ({ ...f, target_table: e.target.value, target_schema: '' }))} /></div>
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

  // Excel Upload Page
  const ExcelUpload = () => {
    const [dragActive, setDragActive] = useState(false);

    const handleDrag = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.type === "dragenter" || e.type === "dragover") {
        setDragActive(true);
      } else if (e.type === "dragleave") {
        setDragActive(false);
      }
    };

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        setUploadedFile(e.dataTransfer.files[0]);
      }
    };

    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Upload Budget</h1>

        {error && <ErrorMessage message={error} />}

        {/* Upload Area */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
              dragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Drop your Excel file here
            </h3>
            <p className="text-gray-600 mb-4">or click to browse</p>
            <input
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              id="file-upload"
              onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
            />
            <label
              htmlFor="file-upload"
              className="inline-block px-6 py-3 bg-primary-600 text-white rounded-lg cursor-pointer hover:bg-primary-700"
            >
              Choose File
            </label>
            <p className="text-sm text-gray-500 mt-4">
              Supported formats: .xlsx, .xls (Max 10MB)
            </p>
          </div>

          {uploadedFile && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-5 h-5 text-green-600" />
                <div>
                  <p className="font-medium text-gray-900">{uploadedFile.name}</p>
                  <p className="text-sm text-gray-600">{(uploadedFile.size / 1024).toFixed(2)} KB</p>
                </div>
              </div>
              <button
                onClick={() => setUploadedFile(null)}
                className="text-red-600 hover:text-red-700"
                disabled={uploadProgress}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}

          {uploadedFile && (
            <div className="mt-6 flex gap-3">
              <button 
                onClick={handleUpload}
                disabled={uploadProgress}
                className="flex-1 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {uploadProgress ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    Upload Budget
                  </>
                )}
              </button>
              <button 
                onClick={() => setUploadedFile(null)}
                disabled={uploadProgress}
                className="px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Template Download */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="bg-blue-100 p-3 rounded-lg">
              <Download className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Need a template?
              </h3>
              <p className="text-gray-600 mb-4">
                Download our Excel template to ensure your data is in the correct format.
              </p>
              <button 
                onClick={handleDownloadTemplate}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Download Template
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Sidebar
  const Sidebar = () => (
    <div className="w-64 bg-white border-r border-gray-200 h-screen flex flex-col">
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-2xl font-bold text-primary-600">FPNA</h1>
        <p className="text-sm text-gray-600 mt-1">Financial Planning Platform</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        <button
          onClick={() => setCurrentPage('dashboard')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'dashboard'
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <TrendingUp className="w-5 h-5" />
          <span className="font-medium">Dashboard</span>
        </button>

        <button
          onClick={() => setCurrentPage('upload')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'upload'
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <Upload className="w-5 h-5" />
          <span className="font-medium">Upload Budget</span>
        </button>

        <button
          onClick={() => { setCurrentPage('data-entry'); setSelectedBudget(null); setError(null); }}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'data-entry' ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <FileSpreadsheet className="w-5 h-5" />
          <span className="font-medium">Data Entry</span>
        </button>

        <button
          onClick={() => setCurrentPage('approvals')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'approvals' ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <Users className="w-5 h-5" />
          <span className="font-medium">Approvals</span>
        </button>

        <button
          onClick={() => setCurrentPage('analytics')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'analytics' ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <BarChart2 className="w-5 h-5" />
          <span className="font-medium">Analytics</span>
        </button>
        <button
          onClick={() => setCurrentPage('connections')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'connections' ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <Database className="w-5 h-5" />
          <span className="font-medium">Manage Connections</span>
        </button>
        <button
          onClick={() => setCurrentPage('etl')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            currentPage === 'etl' ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
          }`}
        >
          <RefreshCw className="w-5 h-5" />
          <span className="font-medium">ETL</span>
        </button>
      </nav>

      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
            <span className="text-primary-700 font-semibold text-sm">
              {(user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || user?.username}</p>
            <p className="text-xs text-gray-600">{(user?.roles || []).join(', ') || 'User'}</p>
          </div>
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
          {currentPage === 'upload' && <ExcelUpload />}
          {currentPage === 'approvals' && <ApprovalsPage />}
          {currentPage === 'analytics' && <AnalyticsPage />}
          {currentPage === 'connections' && <ManageConnectionsPage />}
          {currentPage === 'etl' && <ETLPage />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FPNAApp;