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
} from 'lucide-react';
import { budgetPlanningAPI, departmentAPI, connectionsAPI } from '../services/api';
import DepartmentBudgetTemplate from './budget/DepartmentBudgetTemplate';
import BudgetApprovalDashboard from './budget/BudgetApprovalDashboard';

interface WorkflowStatus {
  fiscal_year: number;
  total_plans: number;
  status_counts: Record<string, number>;
  all_approved: boolean;
  ready_for_export: number;
}

interface Department {
  id: number;
  code: string;
  name_en: string;
  is_active: boolean;
  is_baseline_only: boolean;
  budgeting_group_ids: number[];
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

  // Step 1: Initialize data
  const [sourceYears, setSourceYears] = useState<number[]>([]);
  const [calculationMethod, setCalculationMethod] = useState('simple_average');

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

  // Step 1: Initialize Budget Cycle
  const handleInitialize = async () => {
    if (!selectedConnection) {
      setError('Please select a DWH connection');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await budgetPlanningAPI.initialize(fiscalYear, {
        connection_id: selectedConnection,
        source_table: 'balans_ato',
        source_years: sourceYears,
        calculation_method: calculationMethod,
      });
      setSuccess(`Initialized budget cycle: ${result.plans?.plans_created || 0} department plans created`);
      loadWorkflowStatus();
    } catch (err: unknown) {
      let message = 'Initialization failed';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        message = axiosErr.response?.data?.detail || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Step 5: Export
  const handleExport = async () => {
    if (!selectedConnection) {
      setError('Please select a DWH connection');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await budgetPlanningAPI.exportToDWH(fiscalYear, selectedConnection);
      setSuccess(`Exported ${result.plans_exported} plans to DWH (batch: ${result.batch_id})`);
      loadWorkflowStatus();
    } catch (err: unknown) {
      let message = 'Export failed';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        message = axiosErr.response?.data?.detail || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const getStepStatus = (step: number): string => {
    if (!workflowStatus) return 'PENDING';
    
    const counts = workflowStatus.status_counts || {};
    const total = workflowStatus.total_plans || 0;
    
    switch (step) {
      case 1: // Initialize
        return total > 0 ? 'COMPLETED' : 'PENDING';
      case 2: // Assign Departments
        return total > 0 ? 'COMPLETED' : 'PENDING';
      case 3: // Department Entry
        const draft = counts.draft || 0;
        const submitted = counts.submitted || 0;
        if (draft > 0 || submitted > 0) return 'IN_PROGRESS';
        return total > 0 ? 'COMPLETED' : 'PENDING';
      case 4: // Approval
        const deptApproved = counts.dept_approved || 0;
        const cfoApproved = counts.cfo_approved || 0;
        if (deptApproved > 0) return 'IN_PROGRESS';
        if (cfoApproved === total && total > 0) return 'COMPLETED';
        return 'PENDING';
      case 5: // Export
        const exported = counts.exported || 0;
        if (exported === total && total > 0) return 'COMPLETED';
        if (exported > 0) return 'IN_PROGRESS';
        return 'PENDING';
      default:
        return 'PENDING';
    }
  };

  const renderStepContent = () => {
    switch (activeStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Initialize Budget Cycle for FY {fiscalYear}</h3>
              <p className="text-sm text-gray-600 mb-4">
                This will ingest historical data from DWH, calculate baselines by budgeting groups, 
                and create budget plans for all active departments.
              </p>
              <div className="grid grid-cols-4 gap-4 mb-4">
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
                    value={sourceYears.join(', ')}
                    disabled
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Calculation Method</label>
                  <select
                    value={calculationMethod}
                    onChange={(e) => setCalculationMethod(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="simple_average">Simple Average</option>
                    <option value="weighted_average">Weighted Average</option>
                    <option value="trend">Trend-based</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleInitialize}
                    disabled={loading || !selectedConnection}
                    className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
                    Initialize Budget Cycle
                  </button>
                </div>
              </div>
            </div>

            {workflowStatus && workflowStatus.total_plans > 0 && (
              <div className="bg-green-50 rounded-lg border border-green-200 p-4">
                <div className="flex items-center gap-2 text-green-800">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">Budget cycle initialized</span>
                </div>
                <p className="text-sm text-green-700 mt-1">
                  {workflowStatus.total_plans} department plans created for FY {fiscalYear}
                </p>
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Department Setup</h3>
              <p className="text-sm text-gray-600 mb-4">
                Manage departments and assign budgeting groups. Each department will receive 
                a budget template with their assigned groups.
              </p>
              
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">Code</th>
                      <th className="px-3 py-2 text-left">Department Name</th>
                      <th className="px-3 py-2 text-center">Baseline Only</th>
                      <th className="px-3 py-2 text-center">Assigned Groups</th>
                      <th className="px-3 py-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {departments.map((dept) => (
                      <tr key={dept.id} className="border-t">
                        <td className="px-3 py-2 font-mono">{dept.code}</td>
                        <td className="px-3 py-2">{dept.name_en}</td>
                        <td className="px-3 py-2 text-center">
                          {dept.is_baseline_only ? (
                            <span className="text-yellow-600">Yes</span>
                          ) : (
                            <span className="text-green-600">No</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">{dept.budgeting_group_ids?.length || 0}</td>
                        <td className="px-3 py-2 text-center">
                          <StatusBadge status={dept.is_active ? 'ACTIVE' : 'INACTIVE'} />
                        </td>
                      </tr>
                    ))}
                    {departments.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-3 py-8 text-center text-gray-500">
                          No departments configured. Create departments in the admin panel.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Department Budget Entry</h3>
              <p className="text-sm text-gray-600 mb-4">
                Select a department to view and edit their budget template. Apply drivers 
                at the group level to adjust baseline values.
              </p>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Select Department</label>
                <select
                  value={selectedDepartment || ''}
                  onChange={(e) => setSelectedDepartment(Number(e.target.value))}
                  className="w-full max-w-md border rounded-lg px-3 py-2"
                >
                  <option value="">Select department...</option>
                  {departments.filter(d => d.is_active).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name_en} ({d.code})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedDepartment && (
              <DepartmentBudgetTemplate
                departmentId={selectedDepartment}
                fiscalYear={fiscalYear}
                onStatusChange={loadWorkflowStatus}
              />
            )}
          </div>
        );

      case 4:
        return (
          <BudgetApprovalDashboard
            fiscalYear={fiscalYear}
            onViewPlan={(deptId) => {
              setSelectedDepartment(deptId);
              setActiveStep(3);
            }}
          />
        );

      case 5:
        return (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-4">
              <h3 className="font-semibold mb-4">Export Approved Budgets to DWH</h3>
              <p className="text-sm text-gray-600 mb-4">
                Export all CFO-approved budget plans to the Data Warehouse.
              </p>
              
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
                    value="fpna_budget_final"
                    disabled
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleExport}
                    disabled={loading || !selectedConnection || (workflowStatus?.ready_for_export || 0) === 0}
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
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {workflowStatus.ready_for_export || 0}
                    </div>
                    <div className="text-sm text-gray-600">Ready to Export</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {workflowStatus.status_counts?.exported || 0}
                    </div>
                    <div className="text-sm text-gray-600">Already Exported</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {workflowStatus.total_plans || 0}
                    </div>
                    <div className="text-sm text-gray-600">Total Plans</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-gray-600">{fiscalYear}</div>
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
          <p className="text-gray-600">COA Hierarchy-Based Group Budgeting</p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={fiscalYear}
            onChange={(e) => setFiscalYear(Number(e.target.value))}
            className="border rounded-lg px-4 py-2"
          >
            <option value={2028}>FY 2028</option>
            <option value={2027}>FY 2027</option>
            <option value={2026}>FY 2026</option>
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
      <div className="grid grid-cols-5 gap-4">
        <StepCard
          step={1}
          title="Initialize"
          description="Ingest DWH data & calculate baseline"
          status={getStepStatus(1)}
          icon={<Database className="w-5 h-5" />}
          isActive={activeStep === 1}
          onClick={() => setActiveStep(1)}
          stats={
            workflowStatus?.total_plans ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.total_plans} plans created
              </div>
            ) : null
          }
        />
        <StepCard
          step={2}
          title="Departments"
          description="Assign budgeting groups"
          status={getStepStatus(2)}
          icon={<Building2 className="w-5 h-5" />}
          isActive={activeStep === 2}
          onClick={() => setActiveStep(2)}
          stats={
            departments.length > 0 ? (
              <div className="text-xs text-gray-500">
                {departments.length} departments
              </div>
            ) : null
          }
        />
        <StepCard
          step={3}
          title="Entry"
          description="Department budget templates"
          status={getStepStatus(3)}
          icon={<FileSpreadsheet className="w-5 h-5" />}
          isActive={activeStep === 3}
          onClick={() => setActiveStep(3)}
          stats={
            workflowStatus?.status_counts ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.status_counts.draft || 0} draft, {workflowStatus.status_counts.submitted || 0} submitted
              </div>
            ) : null
          }
        />
        <StepCard
          step={4}
          title="Approval"
          description="Two-level approval workflow"
          status={getStepStatus(4)}
          icon={<ClipboardCheck className="w-5 h-5" />}
          isActive={activeStep === 4}
          onClick={() => setActiveStep(4)}
          stats={
            workflowStatus?.status_counts ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.status_counts.cfo_approved || 0} approved
              </div>
            ) : null
          }
        />
        <StepCard
          step={5}
          title="Export"
          description="Send to DWH"
          status={getStepStatus(5)}
          icon={<Upload className="w-5 h-5" />}
          isActive={activeStep === 5}
          onClick={() => setActiveStep(5)}
          stats={
            workflowStatus?.ready_for_export ? (
              <div className="text-xs text-gray-500">
                {workflowStatus.ready_for_export} ready
              </div>
            ) : null
          }
        />
      </div>

      {/* Step Content */}
      <div className="bg-gray-50 rounded-lg p-6">{renderStepContent()}</div>
    </div>
  );
};

export default BudgetPlanningNew;
