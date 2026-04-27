// src/components/FPNAApp.tsx - Connected to Real Backend
import React, { useState, useEffect } from 'react';
import {
  FileSpreadsheet,
  TrendingUp,
  Users,
  ChevronDown,
  Check,
  X,
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  BarChart2,
  Pencil,
  Database,
  Plug,
  ArrowRight,
  RefreshCw,
  Play,
  Layers,
  Banknote,
  Calculator,
  Settings,
  BarChart,
  Activity,
  Sparkles,
  FlaskConical,
} from 'lucide-react';
import { authAPI, approvalsAPI, connectionsAPI, etlAPI } from '../services/api';
import { BudgetStructure, DriversPage, CurrenciesPage, MetadataLogicV2Page } from './fpna';
import { AIAssistant } from './AIAssistant';
import { DataIntegrationPage } from './DataIntegration';
import { VarianceReportPage } from './VarianceReport';
import BudgetPlanningNew from './BudgetPlanningNew';
import ExecutiveDashboard from './ExecutiveDashboard';
import { AnalysisDashboard } from './AnalysisDashboard';
import ReportingHub from './ReportingHub';
import DepartmentBudgetTemplate from './budget/DepartmentBudgetTemplate';
import LoginPage from './LoginPage';
import AppHeader from './AppHeader';
import UserManagementPage from './UserManagementPage';

// Status Badge Component
const StatusBadge = ({ status }: { status: string }) => {
  const statusColors: Record<string, string> = {
    DRAFT: 'badge-neutral',
    APPROVED: 'badge-success',
    REJECTED: 'badge-danger',
    EXPORTED: 'badge-primary',
    SUBMITTED: 'badge-info',
    PENDING_L1: 'badge-warning',
    PENDING_L2: 'badge-warning',
    PENDING_L3: 'badge-warning',
    PENDING_L4: 'badge-warning',
  };

  return (
    <span className={`badge ${statusColors[status] || 'badge-neutral'}`}>
      {status.replace(/_/g, ' ')}
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
  const [user, setUser] = useState<{ id?: number; username: string; full_name?: string; roles?: string[] } | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') return 'light';
    const stored = window.localStorage.getItem('theme');
    return stored === 'dark' ? 'dark' : 'light';
  });

  // Role-based access
  const userRoles = user?.roles?.map(r => r.toUpperCase()) || [];
  const hasRole = (...roles: string[]) => roles.some(r => userRoles.includes(r));
  const isCLevel = hasRole('CFO', 'CEO', 'ADMIN', 'ANALYST');
  const isDeptUser = hasRole('DEPARTMENT_MANAGER');
  const isViewerOnly = !isCLevel && !isDeptUser;

  // Department ID for dept users (fetched after login)
  const [userDeptId, setUserDeptId] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      authAPI.getCurrentUser()
        .then((u: { id?: number; username?: string; full_name?: string; roles?: string[] }) =>
          setUser({
            id: u.id,
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

  useEffect(() => {
    try {
      window.localStorage.setItem('theme', theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  // Set default page based on role after login
  useEffect(() => {
    if (user) {
      const roles = user.roles?.map(r => r.toUpperCase()) || [];
      const isViewer = !roles.some(r => ['CFO', 'CEO', 'ADMIN', 'ANALYST'].includes(r)) && !roles.includes('DEPARTMENT_MANAGER');
      const isDept = roles.includes('DEPARTMENT_MANAGER');
      if (isViewer) setCurrentPage('reporting');
      else if (isDept) setCurrentPage('dept-budget');
      // C-level stays on 'dashboard' (default)
    }
  }, [user]);

  // Fetch department ID for dept users
  useEffect(() => {
    if (user && isDeptUser && user.id) {
      // Try to find the user's department from department assignments
      import('../services/api').then(({ departmentAPI }) => {
        departmentAPI.list().then((departments: { id: number; head_user_id?: number; manager_user_id?: number }[]) => {
          const myDept = departments.find(d =>
            d.head_user_id === user.id || d.manager_user_id === user.id
          );
          if (myDept) setUserDeptId(myDept.id);
        }).catch(() => {});
      });
    }
  }, [user, isDeptUser]);

  const handleLogin = async (username: string, password: string) => {
    setLoginError(null);
    try {
      const res = await authAPI.login(username, password) as {
        access_token?: string;
        user?: { id?: number; username?: string; full_name?: string; roles?: string[] };
      };
      localStorage.setItem('access_token', res.access_token || '');
      const u = res.user;
      setUser({
        id: u?.id,
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

  // Collapsible Navigation State
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['budgeting', 'fpna', 'reporting']));

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
  const NavItem = ({ page, icon: Icon, label, indent = false }: { page: string; icon: React.ElementType; label: string; indent?: boolean }) => {
    const isActive = currentPage === page;
    const isDark = theme === 'dark';

    return (
      <button
        onClick={() => {
          setCurrentPage(page);
          setError(null);
        }}
        className={`relative w-full flex items-center gap-2.5 rounded-lg py-2 pr-3 text-[13px] font-medium transition-all duration-150 ${
          indent ? 'pl-8' : 'pl-3'
        } ${
          isActive
            ? isDark
              ? 'bg-primary-900/30 text-primary-300'
              : 'bg-primary-50 text-primary-700'
            : isDark
            ? 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }`}
      >
        {isActive && (
          <span className={`absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-r-full ${isDark ? 'bg-primary-400' : 'bg-primary-600'}`} />
        )}
        <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? (isDark ? 'text-primary-400' : 'text-primary-600') : isDark ? 'text-slate-500' : 'text-slate-400'}`} />
        <span className="truncate">{label}</span>
      </button>
    );
  };

  // Section Header Component
  const SectionHeader = ({ id, icon: Icon, label, expanded }: { id: string; icon: React.ElementType; label: string; expanded: boolean }) => {
    const isDark = theme === 'dark';
    return (
      <button
        onClick={() => toggleSection(id)}
        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
          isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-700'
        }`}
      >
        <div className="flex items-center gap-2">
          <Icon className="w-3 h-3" />
          <span className="text-[10px] font-bold tracking-widest uppercase">{label}</span>
        </div>
        <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
      </button>
    );
  };

  // Sidebar
  const Sidebar = () => {
    const isDark = theme === 'dark';
    return (
      <div
        className={`w-64 h-full flex flex-col border-r transition-colors ${
          isDark ? 'bg-slate-950 border-slate-800' : 'bg-white border-slate-200'
        }`}
        style={{ boxShadow: isDark ? 'none' : '1px 0 0 0 #e2e8f0' }}
      >
        {/* Sidebar header - fiscal year badge */}
        <div className={`px-4 py-3.5 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg brand-gradient flex items-center justify-center shadow-sm shrink-0">
              <TrendingUp className="w-4 h-4 text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className={`text-[13px] font-bold truncate ${isDark ? 'text-slate-50' : 'text-slate-900'}`}>
                FP&A Workspace
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-[10px] font-semibold uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  FY 2026
                </span>
                <span className="w-1 h-1 rounded-full bg-emerald-500 inline-block" />
                <span className="text-[10px] text-emerald-600 font-medium">Active</span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {/* Dashboard - C-level only */}
        {isCLevel && <NavItem page="dashboard" icon={TrendingUp} label="Dashboard" />}

        {/* Budget Planning Section - C-level and dept users */}
        {(isCLevel || isDeptUser) && (
          <div className="pt-2">
            <SectionHeader id="budgeting" icon={FileSpreadsheet} label="Budget Planning" expanded={expandedSections.has('budgeting')} />
            {expandedSections.has('budgeting') && (
              <div className="mt-1 space-y-0.5">
                {isCLevel && <NavItem page="budget-planning" icon={Calculator} label="Plan Budgets" indent />}
                {isDeptUser && <NavItem page="dept-budget" icon={FileSpreadsheet} label="My Budget" indent />}
                {(isCLevel || isDeptUser) && <NavItem page="approvals" icon={Users} label="Approvals" indent />}
              </div>
            )}
          </div>
        )}

        {/* Analysis & Reporting Section */}
        <div className="pt-2">
          <SectionHeader id="reporting" icon={BarChart} label="Analysis & Reporting" expanded={expandedSections.has('reporting')} />
          {expandedSections.has('reporting') && (
            <div className="mt-1 space-y-0.5">
              {isCLevel && <NavItem page="variance-report" icon={Activity} label="Variance Analysis" indent />}
              <NavItem page="reporting" icon={BarChart2} label="Reporting Hub" indent />
              {isCLevel && <NavItem page="ai-assistant" icon={Sparkles} label="AI Assistant" indent />}
            </div>
          )}
        </div>

        {/* FP&A Core Section - C-level only */}
        {isCLevel && (
          <div className="pt-2">
            <SectionHeader id="fpna" icon={Layers} label="FP&A Core" expanded={expandedSections.has('fpna')} />
            {expandedSections.has('fpna') && (
              <div className="mt-1 space-y-0.5">
                <NavItem page="coa" icon={Layers} label="Budget Structure" indent />
                <NavItem page="drivers" icon={Calculator} label="Drivers" indent />
                <NavItem page="drivers-v2-test" icon={FlaskConical} label="Drivers V2 Test" indent />
                <NavItem page="currencies" icon={Banknote} label="Currencies & FX" indent />
              </div>
            )}
          </div>
        )}

        {/* Data Integration Section - C-level only */}
        {isCLevel && (
          <div className="pt-2">
            <SectionHeader id="integration" icon={RefreshCw} label="Data Integration" expanded={expandedSections.has('integration')} />
            {expandedSections.has('integration') && (
              <div className="mt-1 space-y-0.5">
                <NavItem page="data-integration" icon={Database} label="Integration Hub" indent />
              </div>
            )}
          </div>
        )}

        {/* Administration Section - Admin/CFO only */}
        {hasRole('ADMIN', 'CFO') && (
          <div className="pt-2">
            <SectionHeader id="settings" icon={Settings} label="Administration" expanded={expandedSections.has('settings')} />
            {expandedSections.has('settings') && (
              <div className="mt-1 space-y-0.5">
                <NavItem page="users" icon={Users} label="User Management" indent />
                <NavItem page="connections" icon={Plug} label="Data Connections" indent />
                <NavItem page="etl" icon={RefreshCw} label="ETL Jobs" indent />
              </div>
            )}
          </div>
        )}
        </nav>

        {/* User Profile Section */}
        <div className={`px-3 py-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          <div className={`flex items-center gap-2.5 px-2 py-2 rounded-lg ${isDark ? 'bg-slate-900/60' : 'bg-slate-50'}`}>
            <div className="w-8 h-8 brand-gradient rounded-lg flex items-center justify-center shadow-sm shrink-0">
              <span className="text-white font-bold text-[11px]">
                {(user?.full_name || user?.username || 'U').split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-[13px] font-semibold truncate ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                {user?.full_name || user?.username}
              </p>
              <p className={`text-[10px] truncate font-medium uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                {(user?.roles || [])[0] || 'User'}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className={`p-1.5 rounded-lg transition-colors shrink-0 ${isDark ? 'text-slate-600 hover:text-red-400 hover:bg-slate-800' : 'text-slate-400 hover:text-red-500 hover:bg-red-50'}`}
              title="Sign Out"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  };

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
    <div
      className={`flex flex-col h-screen transition-colors ${
        theme === 'dark' ? 'bg-slate-950 text-slate-50' : 'bg-surface-50 text-slate-900'
      }`}
    >
      <AppHeader
        username={user.username}
        fullName={user.full_name}
        roles={user.roles || []}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex-1 overflow-auto">
          <div className="max-w-screen-2xl mx-auto w-full px-6 py-6 lg:px-8 lg:py-7">
          {currentPage === 'dashboard' && <ExecutiveDashboard theme={theme} onNavigate={setCurrentPage} />}
          {currentPage === 'approvals' && <ApprovalsPage />}
          {currentPage === 'variance-report' && <VarianceReportPage />}
          {currentPage === 'data-integration' && <DataIntegrationPage />}
          {currentPage === 'coa' && <BudgetStructure />}
          {currentPage === 'currencies' && <CurrenciesPage />}
          {currentPage === 'drivers' && <DriversPage />}
          {currentPage === 'drivers-v2-test' && <MetadataLogicV2Page />}
          {currentPage === 'ai-assistant' && <AIAssistant theme={theme} fiscalYear={2026} />}
          {currentPage === 'budget-planning' && <BudgetPlanningNew />}
          {currentPage === 'reporting' && <ReportingHub theme={theme} />}
          {currentPage === 'analytics' && <AnalysisDashboard />}
          {currentPage === 'connections' && <ManageConnectionsPage />}
          {currentPage === 'etl' && <ETLPage />}
          {currentPage === 'dept-budget' && userDeptId && (
            <DepartmentBudgetTemplate departmentId={userDeptId} fiscalYear={2026} />
          )}
          {currentPage === 'dept-budget' && !userDeptId && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
              <FileSpreadsheet className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium text-gray-900">No Department Assigned</p>
              <p className="text-sm mt-2 text-gray-500">You are not assigned to any department yet. Contact your administrator.</p>
            </div>
          )}
          {currentPage === 'users' && (
            <UserManagementPage
              currentUserId={user.id}
              currentUser={user}
              canManageUsers={hasRole('ADMIN', 'CFO')}
            />
          )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FPNAApp;
