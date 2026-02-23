import React, { useState, useEffect } from 'react';
import {
  Check,
  X,
  Eye,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Send,
  Building2,
  RefreshCw,
} from 'lucide-react';
import { budgetPlanningAPI } from '../../services/api';

interface PlanSummary {
  id: number;
  department_id: number;
  department_code: string;
  department_name: string;
  status: string;
  total_baseline: number;
  total_adjusted: number;
  total_variance: number;
  submitted_at: string | null;
  dept_approved_at: string | null;
  cfo_approved_at: string | null;
}

interface WorkflowStatus {
  fiscal_year: number;
  total_plans: number;
  status_counts: Record<string, number>;
  all_approved: boolean;
  ready_for_export: number;
}

interface Props {
  fiscalYear: number;
  onViewPlan?: (departmentId: number) => void;
}

const formatCurrency = (num: number): string => {
  if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(1)}T`;
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toFixed(0);
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800',
    submitted: 'bg-blue-100 text-blue-800',
    dept_approved: 'bg-yellow-100 text-yellow-800',
    cfo_approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    exported: 'bg-purple-100 text-purple-800',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status.toUpperCase().replace('_', ' ')}
    </span>
  );
};

const BudgetApprovalDashboard: React.FC<Props> = ({ fiscalYear, onViewPlan }) => {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [rejectDialog, setRejectDialog] = useState<{ planId: number; deptId: number; deptName: string } | null>(null);

  // Helper to calculate variance percentage
  const calcVariancePct = (baseline: number, adjusted: number): number => {
    if (baseline === 0) return 0;
    return ((adjusted - baseline) / Math.abs(baseline)) * 100;
  };
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    loadData();
  }, [fiscalYear]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [plansData, statusData] = await Promise.all([
        budgetPlanningAPI.listPlans(fiscalYear),
        budgetPlanningAPI.getWorkflowStatus(fiscalYear),
      ]);
      setPlans(plansData.plans || []);
      setWorkflowStatus(statusData);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveDept = async (deptId: number) => {
    try {
      setActionLoading(deptId);
      await budgetPlanningAPI.approvePlanDept(deptId, fiscalYear);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCFOApproveAll = async () => {
    try {
      setActionLoading(-1);
      await budgetPlanningAPI.cfoApproveAll(fiscalYear);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async () => {
    if (!rejectDialog || !rejectReason.trim()) return;
    try {
      setActionLoading(rejectDialog.planId);
      await budgetPlanningAPI.rejectPlan(rejectDialog.deptId, fiscalYear, rejectReason);
      setRejectDialog(null);
      setRejectReason('');
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reject');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const submittedPlans = plans.filter(p => p.status === 'submitted');
  const deptApprovedPlans = plans.filter(p => p.status === 'dept_approved');
  const cfoApprovedPlans = plans.filter(p => p.status === 'cfo_approved');

  return (
    <div className="space-y-6">
      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2 text-red-700">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-2">
            <Building2 className="w-4 h-4" />
            <span className="text-sm">Total Plans</span>
          </div>
          <div className="text-2xl font-bold">{workflowStatus?.total_plans || 0}</div>
        </div>
        <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <Send className="w-4 h-4" />
            <span className="text-sm">Submitted</span>
          </div>
          <div className="text-2xl font-bold text-blue-700">{workflowStatus?.status_counts?.submitted || 0}</div>
        </div>
        <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
          <div className="flex items-center gap-2 text-yellow-600 mb-2">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Dept Approved</span>
          </div>
          <div className="text-2xl font-bold text-yellow-700">{workflowStatus?.status_counts?.dept_approved || 0}</div>
        </div>
        <div className="bg-green-50 rounded-lg border border-green-200 p-4">
          <div className="flex items-center gap-2 text-green-600 mb-2">
            <CheckCircle className="w-4 h-4" />
            <span className="text-sm">CFO Approved</span>
          </div>
          <div className="text-2xl font-bold text-green-700">{workflowStatus?.status_counts?.cfo_approved || 0}</div>
        </div>
        <div className="bg-purple-50 rounded-lg border border-purple-200 p-4">
          <div className="flex items-center gap-2 text-purple-600 mb-2">
            <Check className="w-4 h-4" />
            <span className="text-sm">Exported</span>
          </div>
          <div className="text-2xl font-bold text-purple-700">{workflowStatus?.status_counts?.exported || 0}</div>
        </div>
      </div>

      {/* CFO Approve All Button */}
      {deptApprovedPlans.length > 0 && (
        <div className="bg-green-50 rounded-lg border border-green-200 p-4 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-green-800">CFO Final Approval</h3>
            <p className="text-sm text-green-700">
              {deptApprovedPlans.length} plans are ready for CFO approval
            </p>
          </div>
          <button
            onClick={handleCFOApproveAll}
            disabled={actionLoading === -1}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {actionLoading === -1 ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            Approve All ({deptApprovedPlans.length})
          </button>
        </div>
      )}

      {/* Plans Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b bg-gray-50">
          <h3 className="font-semibold">Budget Plans - FY {fiscalYear}</h3>
          <button
            onClick={loadData}
            className="p-2 hover:bg-gray-100 rounded-lg"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Department</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Baseline</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Adjusted</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Variance</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Submitted</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => {
                const variancePct = calcVariancePct(plan.total_baseline, plan.total_adjusted);
                return (
                  <tr key={plan.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium">{plan.department_name}</div>
                        <div className="text-xs text-gray-500">{plan.department_code}</div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={plan.status} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{formatCurrency(plan.total_baseline)}</td>
                    <td className="px-4 py-3 text-right font-mono text-blue-700">{formatCurrency(plan.total_adjusted)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={variancePct >= 0 ? 'text-green-600' : 'text-red-600'}>
                        {variancePct >= 0 ? '+' : ''}{variancePct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {plan.submitted_at ? (
                        <div>
                          <div className="text-xs">{new Date(plan.submitted_at).toLocaleDateString()}</div>
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        {onViewPlan && (
                          <button
                            onClick={() => onViewPlan(plan.department_id)}
                            className="p-1.5 text-gray-600 hover:bg-gray-100 rounded"
                            title="View Details"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        )}
                        {plan.status === 'submitted' && (
                          <>
                            <button
                              onClick={() => handleApproveDept(plan.department_id)}
                              disabled={actionLoading === plan.department_id}
                              className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                              title="Approve (Dept)"
                            >
                              {actionLoading === plan.department_id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Check className="w-4 h-4" />
                              )}
                            </button>
                            <button
                              onClick={() => setRejectDialog({ planId: plan.id, deptId: plan.department_id, deptName: plan.department_name })}
                              className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                              title="Reject"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {plan.status === 'dept_approved' && (
                          <button
                            onClick={() => setRejectDialog({ planId: plan.id, deptId: plan.department_id, deptName: plan.department_name })}
                            className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                            title="Reject"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {plans.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    No budget plans found for FY {fiscalYear}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reject Dialog */}
      {rejectDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b">
              <h3 className="text-lg font-semibold">Reject Budget Plan</h3>
              <p className="text-sm text-gray-500">{rejectDialog.deptName}</p>
            </div>
            <div className="p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rejection Reason <span className="text-red-500">*</span>
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 h-24"
                placeholder="Please provide a reason for rejection..."
              />
            </div>
            <div className="flex justify-end gap-2 p-4 border-t bg-gray-50">
              <button
                onClick={() => {
                  setRejectDialog(null);
                  setRejectReason('');
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || actionLoading === rejectDialog.planId}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading === rejectDialog.planId ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <XCircle className="w-4 h-4" />
                )}
                Reject Plan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BudgetApprovalDashboard;
