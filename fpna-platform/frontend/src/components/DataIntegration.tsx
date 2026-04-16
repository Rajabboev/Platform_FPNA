import React, { useState, useEffect, useCallback } from 'react';
import {
  Database,
  Download,
  Upload,
  RefreshCw,
  CheckCircle,
  Clock,
  AlertCircle,
  Play,
  ArrowRight,
  ArrowDown,
  Table,
  Eye,
  Settings,
  Bell,
  TrendingUp,
  TrendingDown,
  FileText,
  History,
  GitBranch,
  Target,
  Zap,
  Filter,
  ChevronDown,
  ChevronRight,
  Users,
  Building2,
  LayoutTemplate,
  Calculator,
  Send,
  Check,
  X,
  Plug,
  Plus,
  Trash2,
  Edit,
  Copy,
  ExternalLink,
  Info,
} from 'lucide-react';
import {
  connectionsAPI,
  baselineAPI,
  templatesAPI,
  driversAPI,
  dwhIntegrationAPI,
} from '../services/api';

// ============================================
// Shared UI Components
// ============================================
const formatNumber = (num: number): string => {
  if (num === null || num === undefined) return '-';
  if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(2) + 'T';
  if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(2) + 'B';
  if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(2) + 'M';
  if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(2) + 'K';
  return num.toLocaleString();
};

const StatusBadge: React.FC<{ status: string; size?: 'sm' | 'md' }> = ({ status, size = 'md' }) => {
  const colors: Record<string, string> = {
    COMPLETED: 'bg-green-100 text-green-700 border-green-200',
    PENDING: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    IN_PROGRESS: 'bg-blue-100 text-blue-700 border-blue-200',
    DRAFT: 'bg-gray-100 text-gray-700 border-gray-200',
    SUBMITTED: 'bg-blue-100 text-blue-700 border-blue-200',
    APPROVED: 'bg-green-100 text-green-700 border-green-200',
    REJECTED: 'bg-red-100 text-red-700 border-red-200',
    EXPORTED: 'bg-purple-100 text-purple-700 border-purple-200',
    ACTIVE: 'bg-green-100 text-green-700 border-green-200',
    INACTIVE: 'bg-gray-100 text-gray-700 border-gray-200',
    SUCCESS: 'bg-green-100 text-green-700 border-green-200',
    FAILED: 'bg-red-100 text-red-700 border-red-200',
  };
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-xs';
  return (
    <span className={`${sizeClasses} rounded-full font-medium border ${colors[status] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
      {status}
    </span>
  );
};

const Card: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <div className={`bg-white rounded-xl shadow-sm border border-gray-200 ${className}`}>{children}</div>
);

const StatCard: React.FC<{
  label: string;
  value: string | number;
  icon: React.ElementType;
  color?: string;
  trend?: { value: number; label: string };
  onClick?: () => void;
}> = ({ label, value, icon: Icon, color = 'blue', trend, onClick }) => {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
    indigo: 'bg-indigo-50 text-indigo-600',
  };
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl p-4 border border-gray-200 ${onClick ? 'cursor-pointer hover:border-gray-300 hover:shadow-sm transition-all' : ''}`}
    >
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg ${colors[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <div className={`flex items-center text-sm ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend.value >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
            {Math.abs(trend.value).toFixed(1)}%
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

const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  label: string;
  badge?: number;
}> = ({ active, onClick, icon: Icon, label, badge }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
      active ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
    }`}
  >
    <Icon className="w-4 h-4" />
    {label}
    {badge !== undefined && badge > 0 && (
      <span className={`ml-1 px-1.5 py-0.5 text-xs rounded-full ${active ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-200 text-gray-600'}`}>
        {badge}
      </span>
    )}
  </button>
);

const Alert: React.FC<{ type: 'error' | 'success' | 'info'; message: string; onClose?: () => void }> = ({
  type,
  message,
  onClose,
}) => {
  const styles = {
    error: 'bg-red-50 border-red-200 text-red-700',
    success: 'bg-green-50 border-green-200 text-green-700',
    info: 'bg-blue-50 border-blue-200 text-blue-700',
  };
  const icons = {
    error: AlertCircle,
    success: CheckCircle,
    info: Info,
  };
  const Icon = icons[type];
  return (
    <div className={`${styles[type]} px-4 py-3 rounded-lg border flex items-center gap-2`}>
      <Icon className="w-5 h-5 flex-shrink-0" />
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose} className="p-1 hover:bg-black/5 rounded">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

// ============================================
// Main Data Integration Page
// ============================================
export const DataIntegrationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'connections' | 'ingestion' | 'templates' | 'egress'>('overview');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Database className="w-6 h-6 text-indigo-600" />
            Data Integration Hub
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            Central control for DWH connections, data pipelines, templates, and budget exports
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select className="border rounded-lg px-3 py-2 text-sm bg-white">
            <option value={2026}>FY 2026</option>
            <option value={2025}>FY 2025</option>
          </select>
        </div>
      </div>

      {/* Alerts */}
      {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess(null)} />}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
        <TabButton active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} icon={TrendingUp} label="Overview" />
        <TabButton active={activeTab === 'connections'} onClick={() => setActiveTab('connections')} icon={Plug} label="Connections" />
        <TabButton active={activeTab === 'ingestion'} onClick={() => setActiveTab('ingestion')} icon={Download} label="Data Ingestion" />
        <TabButton active={activeTab === 'templates'} onClick={() => setActiveTab('templates')} icon={LayoutTemplate} label="Templates" />
        <TabButton active={activeTab === 'egress'} onClick={() => setActiveTab('egress')} icon={Upload} label="Export" />
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && <OverviewPanel setError={setError} setSuccess={setSuccess} />}
      {activeTab === 'connections' && <ConnectionsPanel setError={setError} setSuccess={setSuccess} />}
      {activeTab === 'ingestion' && <IngestionPanel setError={setError} setSuccess={setSuccess} />}
      {activeTab === 'templates' && <TemplatesPanel setError={setError} setSuccess={setSuccess} />}
      {activeTab === 'egress' && <EgressPanel setError={setError} setSuccess={setSuccess} />}
    </div>
  );
};

// ============================================
// Overview Panel
// ============================================
const OverviewPanel: React.FC<{ setError: (e: string | null) => void; setSuccess: (s: string | null) => void }> = ({
  setError,
}) => {
  const [workflowStatus, setWorkflowStatus] = useState<any>(null);
  const [connections, setConnections] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [status, conns, tmpls] = await Promise.all([
        baselineAPI.getWorkflowStatus(2026),
        connectionsAPI.list(),
        templatesAPI.list({ is_active: true }),
      ]);
      setWorkflowStatus(status);
      setConnections(conns);
      setTemplates(tmpls);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const steps = workflowStatus?.steps || {};

  return (
    <div className="space-y-6">
      {/* Workflow Pipeline */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Budget Planning Pipeline - FY 2026</h2>
        </div>
        <div className="p-6">
          <div className="flex items-center justify-between">
            {/* Step 1: DWH */}
            <div className="flex-1 text-center">
              <div
                className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                  steps['1_ingest']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                }`}
              >
                <Database className="w-8 h-8" />
              </div>
              <p className="mt-2 font-medium text-gray-900">DWH Source</p>
              <p className="text-sm text-gray-500">{steps['1_ingest']?.records || 0} records</p>
              <StatusBadge status={steps['1_ingest']?.status || 'PENDING'} size="sm" />
            </div>

            <ArrowRight className="w-8 h-8 text-gray-300" />

            {/* Step 2: Baseline */}
            <div className="flex-1 text-center">
              <div
                className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                  steps['2_calculate']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                }`}
              >
                <Calculator className="w-8 h-8" />
              </div>
              <p className="mt-2 font-medium text-gray-900">Baseline</p>
              <p className="text-sm text-gray-500">{steps['2_calculate']?.baselines || 0} accounts</p>
              <StatusBadge status={steps['2_calculate']?.status || 'PENDING'} size="sm" />
            </div>

            <ArrowRight className="w-8 h-8 text-gray-300" />

            {/* Step 3: Templates */}
            <div className="flex-1 text-center">
              <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center bg-blue-100 text-blue-600`}>
                <LayoutTemplate className="w-8 h-8" />
              </div>
              <p className="mt-2 font-medium text-gray-900">Templates</p>
              <p className="text-sm text-gray-500">{templates.length} active</p>
              <StatusBadge status={templates.length > 0 ? 'ACTIVE' : 'PENDING'} size="sm" />
            </div>

            <ArrowRight className="w-8 h-8 text-gray-300" />

            {/* Step 4: Planned */}
            <div className="flex-1 text-center">
              <div
                className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                  steps['3_plan']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                }`}
              >
                <FileText className="w-8 h-8" />
              </div>
              <p className="mt-2 font-medium text-gray-900">Planned Budget</p>
              <p className="text-sm text-gray-500">
                {Object.values(steps['3_plan']?.by_status || {}).reduce((a: number, b: any) => a + (b.count || 0), 0)} items
              </p>
              <StatusBadge status={steps['3_plan']?.status || 'PENDING'} size="sm" />
            </div>

            <ArrowRight className="w-8 h-8 text-gray-300" />

            {/* Step 5: Export */}
            <div className="flex-1 text-center">
              <div
                className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                  steps['4_export']?.status === 'COMPLETED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                }`}
              >
                <Upload className="w-8 h-8" />
              </div>
              <p className="mt-2 font-medium text-gray-900">Export to DWH</p>
              <p className="text-sm text-gray-500">{steps['4_export']?.exported || 0} exported</p>
              <StatusBadge status={steps['4_export']?.status || 'PENDING'} size="sm" />
            </div>
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Active Connections" value={connections.length} icon={Plug} color="blue" />
        <StatCard label="Active Templates" value={templates.length} icon={LayoutTemplate} color="purple" />
        <StatCard
          label="Baselines Created"
          value={steps['2_calculate']?.baselines || 0}
          icon={Calculator}
          color="green"
        />
        <StatCard
          label="Budgets Exported"
          value={steps['4_export']?.exported || 0}
          icon={Upload}
          color="indigo"
        />
      </div>

      {/* Quick Actions */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Quick Actions</h2>
        </div>
        <div className="p-4 grid grid-cols-4 gap-4">
          <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Download className="w-5 h-5 text-blue-600" />
            </div>
            <div className="text-left">
              <p className="font-medium text-gray-900">Run Ingestion</p>
              <p className="text-sm text-gray-500">Import from DWH</p>
            </div>
          </button>
          <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="p-2 bg-green-100 rounded-lg">
              <Calculator className="w-5 h-5 text-green-600" />
            </div>
            <div className="text-left">
              <p className="font-medium text-gray-900">Calculate Baselines</p>
              <p className="text-sm text-gray-500">Generate FY 2026</p>
            </div>
          </button>
          <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="p-2 bg-purple-100 rounded-lg">
              <LayoutTemplate className="w-5 h-5 text-purple-600" />
            </div>
            <div className="text-left">
              <p className="font-medium text-gray-900">Assign Templates</p>
              <p className="text-sm text-gray-500">To departments</p>
            </div>
          </button>
          <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <Upload className="w-5 h-5 text-indigo-600" />
            </div>
            <div className="text-left">
              <p className="font-medium text-gray-900">Export Budgets</p>
              <p className="text-sm text-gray-500">To DWH</p>
            </div>
          </button>
        </div>
      </Card>

      {/* Recent Activity */}
      <Card>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Recent Activity</h2>
          <button className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1">
            <History className="w-4 h-4" /> View All
          </button>
        </div>
        <div className="divide-y divide-gray-100">
          <div className="p-4 flex items-center gap-4">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-gray-900">Baseline calculation completed</p>
              <p className="text-sm text-gray-500">435 accounts processed for FY 2026</p>
            </div>
            <span className="text-sm text-gray-400">Just now</span>
          </div>
          <div className="p-4 flex items-center gap-4">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Download className="w-5 h-5 text-blue-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-gray-900">Data ingestion completed</p>
              <p className="text-sm text-gray-500">19,513 records imported from DWH</p>
            </div>
            <span className="text-sm text-gray-400">5 min ago</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Connections Panel
// ============================================
const ConnectionsPanel: React.FC<{ setError: (e: string | null) => void; setSuccess: (s: string | null) => void }> = ({
  setError,
  setSuccess,
}) => {
  const [connections, setConnections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingConnection, setEditingConnection] = useState<any>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    db_type: 'sql_server',
    host: 'localhost',
    port: 1433,
    database_name: '',
    username: '',
    password: '',
    use_ssl: false,
    description: '',
  });

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    setLoading(true);
    try {
      const data = await connectionsAPI.list();
      setConnections(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async (id: number) => {
    setTestingId(id);
    try {
      const result = await connectionsAPI.test(id);
      if (result.success) {
        setSuccess('Connection test successful!');
      } else {
        setError(`Connection test failed: ${result.error}`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Connection test failed');
    } finally {
      setTestingId(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingConnection) {
        await connectionsAPI.update(editingConnection.id, formData);
        setSuccess('Connection updated successfully');
      } else {
        await connectionsAPI.create(formData);
        setSuccess('Connection created successfully');
      }
      setShowForm(false);
      setEditingConnection(null);
      resetForm();
      loadConnections();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save connection');
    }
  };

  const handleEdit = (conn: any) => {
    setEditingConnection(conn);
    setFormData({
      name: conn.name,
      db_type: conn.db_type,
      host: conn.host,
      port: conn.port || 1433,
      database_name: conn.database_name,
      username: conn.username,
      password: '',
      use_ssl: conn.use_ssl || false,
      description: conn.description || '',
    });
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this connection?')) return;
    try {
      await connectionsAPI.delete(id);
      setSuccess('Connection deleted');
      loadConnections();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete connection');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      db_type: 'sql_server',
      host: 'localhost',
      port: 1433,
      database_name: '',
      username: '',
      password: '',
      use_ssl: false,
      description: '',
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">DWH Connections</h2>
          <p className="text-sm text-gray-500">Manage database connections for data integration</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setEditingConnection(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> Add Connection
        </button>
      </div>

      {/* Connection Form */}
      {showForm && (
        <Card>
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">{editingConnection ? 'Edit Connection' : 'New Connection'}</h3>
          </div>
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Connection Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Database Type</label>
                <select
                  value={formData.db_type}
                  onChange={(e) => setFormData({ ...formData, db_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="sql_server">SQL Server</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="oracle">Oracle</option>
                  <option value="mysql">MySQL</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
                <input
                  type="text"
                  value={formData.host}
                  onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
                <input
                  type="number"
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Database Name</label>
                <input
                  type="text"
                  value={formData.database_name}
                  onChange={(e) => setFormData({ ...formData, database_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password {editingConnection && '(leave blank to keep current)'}
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required={!editingConnection}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="use_ssl"
                checked={formData.use_ssl}
                onChange={(e) => setFormData({ ...formData, use_ssl: e.target.checked })}
                className="rounded border-gray-300"
              />
              <label htmlFor="use_ssl" className="text-sm text-gray-700">
                Use SSL/TLS encryption
              </label>
            </div>
            <div className="flex gap-2 pt-4">
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                {editingConnection ? 'Update Connection' : 'Create Connection'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setEditingConnection(null);
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* Connections List */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Host</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Database</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                  </td>
                </tr>
              ) : connections.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No connections configured. Click "Add Connection" to create one.
                  </td>
                </tr>
              ) : (
                connections.map((conn) => (
                  <tr key={conn.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-gray-400" />
                        <span className="font-medium text-gray-900">{conn.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{conn.db_type}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{conn.host}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{conn.database_name}</td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={conn.is_active ? 'ACTIVE' : 'INACTIVE'} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => testConnection(conn.id)}
                          disabled={testingId === conn.id}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"
                          title="Test connection"
                        >
                          {testingId === conn.id ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Play className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => handleEdit(conn)}
                          className="p-1.5 text-gray-600 hover:bg-gray-100 rounded"
                          title="Edit"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(conn.id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Ingestion Panel
// ============================================
const IngestionPanel: React.FC<{ setError: (e: string | null) => void; setSuccess: (s: string | null) => void }> = ({
  setError,
  setSuccess,
}) => {
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [dwhSummary, setDwhSummary] = useState<any>(null);
  const [baselineDataSummary, setBaselineDataSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    loadConnections();
    loadBaselineDataSummary();
  }, []);

  const loadConnections = async () => {
    try {
      const data = await connectionsAPI.list();
      setConnections(data);
      if (data.length > 0) {
        setSelectedConnection(data[0].id);
        loadDWHSummary(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load connections');
    }
  };

  const loadDWHSummary = async (connectionId: number) => {
    setLoading(true);
    try {
      const data = await dwhIntegrationAPI.getBalansSummary(connectionId);
      setDwhSummary(data);
    } catch (err: any) {
      console.error('Failed to load DWH summary:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadBaselineDataSummary = async () => {
    try {
      const data = await baselineAPI.getBaselineDataSummary();
      setBaselineDataSummary(data);
    } catch (err) {
      console.error('Failed to load baseline data summary:', err);
    }
  };

  const runIngestion = async () => {
    if (!selectedConnection) {
      setError('Please select a connection');
      return;
    }
    setIngesting(true);
    try {
      const result = await baselineAPI.ingest({
        connection_id: selectedConnection,
        start_year: 2023,
        end_year: 2025,
      });
      setSuccess(`Successfully imported ${result.records_imported} records from ${result.unique_accounts} accounts`);
      loadBaselineDataSummary();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ingestion failed');
    } finally {
      setIngesting(false);
    }
  };

  const calculateBaselines = async () => {
    setCalculating(true);
    try {
      const result = await baselineAPI.calculate({
        fiscal_year: 2026,
        method: 'simple_average',
        source_years: [2023, 2024, 2025],
      });
      setSuccess(`Created ${result.baselines_created} baseline budgets for FY 2026`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Calculation failed');
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Source Selection */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Data Source</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">DWH Connection</label>
              <select
                value={selectedConnection || ''}
                onChange={(e) => {
                  const id = parseInt(e.target.value);
                  setSelectedConnection(id);
                  if (id) loadDWHSummary(id);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">Select connection...</option>
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.database_name})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Table</label>
              <input
                type="text"
                value="dbo.balans_ato"
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Years</label>
              <input
                type="text"
                value="2023 - 2025"
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* DWH Summary */}
      {dwhSummary && (
        <Card>
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Database className="w-4 h-4" /> DWH Source Summary (balans_ato)
            </h3>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-5 gap-4 mb-4">
              <StatCard label="Total Records" value={formatNumber(dwhSummary.total_rows || 0)} icon={Table} color="blue" />
              <StatCard label="Unique Accounts" value={dwhSummary.unique_accounts || 0} icon={FileText} color="green" />
              <StatCard label="Monthly Snapshots" value={dwhSummary.unique_dates || 0} icon={Clock} color="purple" />
              <StatCard label="Currencies" value={dwhSummary.unique_currencies || 0} icon={RefreshCw} color="yellow" />
              <StatCard label="Branches" value={dwhSummary.unique_branches || 0} icon={Building2} color="red" />
            </div>
            <div className="text-sm text-gray-600">
              <strong>Date Range:</strong> {dwhSummary.date_range?.min} to {dwhSummary.date_range?.max}
            </div>
          </div>
        </Card>
      )}

      {/* Imported Data Summary */}
      <Card>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Imported Baseline Data (FPNA DB)</h3>
          <button
            onClick={runIngestion}
            disabled={!selectedConnection || ingesting}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {ingesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {ingesting ? 'Importing...' : 'Run Ingestion'}
          </button>
        </div>
        <div className="p-4">
          {baselineDataSummary?.by_year?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Year</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Accounts</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Records</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total Balance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {baselineDataSummary.by_year.map((row: any) => (
                    <tr key={row.year} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-900">{row.year}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{row.accounts}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{row.records.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right text-gray-900 font-medium">{formatNumber(row.total_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Database className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p>No data imported yet. Click "Run Ingestion" to import from DWH.</p>
            </div>
          )}
        </div>
      </Card>

      {/* Baseline Calculation */}
      <Card>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">Baseline Calculation</h3>
            <p className="text-sm text-gray-500">Generate baseline budgets for FY 2026 using simple average method</p>
          </div>
          <button
            onClick={calculateBaselines}
            disabled={calculating || !baselineDataSummary?.by_year?.length}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {calculating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
            {calculating ? 'Calculating...' : 'Calculate Baselines'}
          </button>
        </div>
        <div className="p-4">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Method:</span>
              <span className="font-medium text-gray-900">Simple Average</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Source Years:</span>
              <span className="font-medium text-gray-900">2023, 2024, 2025</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Target Year:</span>
              <span className="font-medium text-gray-900">FY 2026</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Templates Panel
// ============================================
const TemplatesPanel: React.FC<{ setError: (e: string | null) => void; setSuccess: (s: string | null) => void }> = ({
  setError,
  setSuccess,
}) => {
  const [templates, setTemplates] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [drivers, setDrivers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tmpls, assigns, drvrs] = await Promise.all([
        templatesAPI.list(),
        templatesAPI.listAssignments({ fiscal_year: 2026 }),
        driversAPI.list({ is_active: true }),
      ]);
      setTemplates(tmpls);
      setAssignments(assigns);
      setDrivers(drvrs);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Templates Overview */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Active Templates" value={templates.filter((t) => t.is_active).length} icon={LayoutTemplate} color="purple" />
        <StatCard label="Assignments (FY 2026)" value={assignments.length} icon={Users} color="blue" />
        <StatCard label="Active Drivers" value={drivers.length} icon={Calculator} color="green" />
      </div>

      {/* Templates List */}
      <Card>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Budget Templates</h3>
          <button className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Plus className="w-4 h-4" /> New Template
          </button>
        </div>
        <div className="divide-y divide-gray-200">
          {templates.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <LayoutTemplate className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p>No templates configured. Create one to get started.</p>
            </div>
          ) : (
            templates.map((template) => (
              <div
                key={template.id}
                className={`p-4 hover:bg-gray-50 cursor-pointer ${selectedTemplate?.id === template.id ? 'bg-blue-50' : ''}`}
                onClick={() => setSelectedTemplate(template)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${template.is_active ? 'bg-purple-100' : 'bg-gray-100'}`}>
                      <LayoutTemplate className={`w-5 h-5 ${template.is_active ? 'text-purple-600' : 'text-gray-400'}`} />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{template.name_en}</p>
                      <p className="text-sm text-gray-500">{template.code} • FY {template.fiscal_year}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm text-gray-600">{template.sections?.length || 0} sections</p>
                      <p className="text-xs text-gray-400">{template.template_type}</p>
                    </div>
                    <StatusBadge status={template.is_active ? 'ACTIVE' : 'INACTIVE'} size="sm" />
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Template Details */}
      {selectedTemplate && (
        <Card>
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-900">{selectedTemplate.name_en}</h3>
              <p className="text-sm text-gray-500">{selectedTemplate.code}</p>
            </div>
            <div className="flex gap-2">
              <button className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
                <Copy className="w-4 h-4" /> Clone
              </button>
              <button className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
                <Edit className="w-4 h-4" /> Edit
              </button>
            </div>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-sm text-gray-500">Fiscal Year</p>
                <p className="font-medium text-gray-900">{selectedTemplate.fiscal_year}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Type</p>
                <p className="font-medium text-gray-900">{selectedTemplate.template_type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Include Baseline</p>
                <p className="font-medium text-gray-900">{selectedTemplate.include_baseline ? 'Yes' : 'No'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Include Variance</p>
                <p className="font-medium text-gray-900">{selectedTemplate.include_variance ? 'Yes' : 'No'}</p>
              </div>
            </div>
            {selectedTemplate.instructions && (
              <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-700">{selectedTemplate.instructions}</div>
            )}
          </div>
        </Card>
      )}

      {/* Assignments */}
      <Card>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Template Assignments (FY 2026)</h3>
          <button className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700">
            <Plus className="w-4 h-4" /> Assign Template
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Department</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Template</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Assigned To</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {assignments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No template assignments for FY 2026. Click "Assign Template" to create one.
                  </td>
                </tr>
              ) : (
                assignments.map((assignment) => (
                  <tr key={assignment.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-gray-400" />
                        <span className="font-medium text-gray-900">{assignment.business_unit_name || 'N/A'}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{assignment.template_name || assignment.template_code}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{assignment.assigned_to_name || 'Unassigned'}</td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={assignment.status} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{assignment.due_date || '-'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button className="p-1.5 text-blue-600 hover:bg-blue-50 rounded" title="View">
                          <Eye className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 text-gray-600 hover:bg-gray-100 rounded" title="Edit">
                          <Edit className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Drivers */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Available Drivers</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-4 gap-3">
            {drivers.slice(0, 8).map((driver) => (
              <div key={driver.id} className="p-3 border border-gray-200 rounded-lg hover:border-gray-300">
                <div className="flex items-center gap-2 mb-1">
                  <Calculator className="w-4 h-4 text-green-600" />
                  <span className="font-medium text-gray-900 text-sm">{driver.name_en}</span>
                </div>
                <p className="text-xs text-gray-500">{driver.code}</p>
                <p className="text-xs text-gray-400 mt-1">{driver.driver_type}</p>
              </div>
            ))}
          </div>
          {drivers.length > 8 && (
            <p className="text-sm text-gray-500 mt-3 text-center">+ {drivers.length - 8} more drivers</p>
          )}
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Egress Panel
// ============================================
const EgressPanel: React.FC<{ setError: (e: string | null) => void; setSuccess: (s: string | null) => void }> = ({
  setError,
  setSuccess,
}) => {
  const [connections, setConnections] = useState<any[]>([]);
  const [plannedBudgets, setPlannedBudgets] = useState<any>(null);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [conns, planned] = await Promise.all([
        connectionsAPI.list(),
        baselineAPI.getPlannedSummary(2026),
      ]);
      setConnections(conns);
      setPlannedBudgets(planned);
      if (conns.length > 0) {
        setSelectedConnection(conns[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const exportToDWH = async () => {
    if (!selectedConnection) {
      setError('Please select a connection');
      return;
    }
    setExporting(true);
    try {
      const result = await baselineAPI.exportToDWH({
        connection_id: selectedConnection,
        fiscal_year: 2026,
        target_table: 'fpna_budget_planned',
        status_filter: 'APPROVED',
      });
      setSuccess(`Exported ${result.budgets_exported} budgets to DWH (Batch: ${result.batch_id?.slice(0, 8)}...)`);
      loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const byStatus = plannedBudgets?.by_status || {};

  return (
    <div className="space-y-6">
      {/* Budget Status Summary */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard label="Draft" value={byStatus.DRAFT?.count || 0} icon={FileText} color="yellow" />
        <StatCard label="Submitted" value={byStatus.SUBMITTED?.count || 0} icon={Send} color="blue" />
        <StatCard label="Approved" value={byStatus.APPROVED?.count || 0} icon={Check} color="green" />
        <StatCard label="Rejected" value={byStatus.REJECTED?.count || 0} icon={X} color="red" />
        <StatCard label="Exported" value={byStatus.EXPORTED?.count || 0} icon={Upload} color="purple" />
      </div>

      {/* Export Configuration */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Export Approved Budgets to DWH</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Target Connection</label>
              <select
                value={selectedConnection || ''}
                onChange={(e) => setSelectedConnection(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">Select connection...</option>
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.database_name})
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
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fiscal Year</label>
              <input
                type="text"
                value="2026"
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status Filter</label>
              <input
                type="text"
                value="APPROVED"
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
              />
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium text-gray-900">Ready to Export</p>
              <p className="text-sm text-gray-500">
                {byStatus.APPROVED?.count || 0} approved budgets totaling{' '}
                {formatNumber(byStatus.APPROVED?.amount || 0)} UZS
              </p>
            </div>
            <button
              onClick={exportToDWH}
              disabled={exporting || !selectedConnection || !(byStatus.APPROVED?.count > 0)}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {exporting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {exporting ? 'Exporting...' : 'Export to DWH'}
            </button>
          </div>
        </div>
      </Card>

      {/* Export History */}
      <Card>
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Export History</h3>
        </div>
        <div className="p-4">
          {byStatus.EXPORTED?.count > 0 ? (
            <div className="flex items-center gap-4 p-4 bg-purple-50 rounded-lg">
              <div className="p-3 bg-purple-100 rounded-full">
                <CheckCircle className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <p className="font-medium text-gray-900">{byStatus.EXPORTED.count} budgets exported</p>
                <p className="text-sm text-gray-500">Total amount: {formatNumber(byStatus.EXPORTED.amount)} UZS</p>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Upload className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p>No budgets exported yet.</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

export default DataIntegrationPage;
