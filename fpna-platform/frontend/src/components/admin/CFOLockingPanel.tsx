import React, { useState, useEffect } from 'react';
import {
  Lock,
  Unlock,
  Layers,
  Check,
  X,
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Search,
  Calendar,
  User,
} from 'lucide-react';
import { budgetPlanningAPI } from '../../services/api';

interface BudgetingGroupLock {
  budgeting_group_id: number;
  budgeting_group_name: string;
  bs_flag: number;
  bs_class_name: string;
  bs_group: string;
  bs_group_name: string;
  locked_by_cfo: boolean;
  cfo_lock_reason: string | null;
  total_baseline: number;
  total_adjusted: number;
}

interface Props {
  fiscalYear: number;
  onClose?: () => void;
}

const formatCurrency = (num: number): string => {
  if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(1)}T`;
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toFixed(0);
};

const CFOLockingPanel: React.FC<Props> = ({ fiscalYear, onClose }) => {
  const [groups, setGroups] = useState<BudgetingGroupLock[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLocked, setFilterLocked] = useState<'all' | 'locked' | 'unlocked'>('all');
  const [expandedBsClasses, setExpandedBsClasses] = useState<Set<number>>(new Set([1, 2, 3, 9]));
  
  const [lockReasonModal, setLockReasonModal] = useState<{ groupId: number; groupName: string } | null>(null);
  const [lockReason, setLockReason] = useState('');

  useEffect(() => {
    loadData();
  }, [fiscalYear]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await budgetPlanningAPI.getAllBudgetingGroups(fiscalYear);
      setGroups(data.groups || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleLock = async (groupId: number, reason?: string) => {
    try {
      setActionLoading(groupId);
      setError(null);
      await budgetPlanningAPI.lockGroup(groupId, fiscalYear, reason);
      setSuccess(`Group locked successfully`);
      await loadData();
      setLockReasonModal(null);
      setLockReason('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to lock group');
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnlock = async (groupId: number) => {
    try {
      setActionLoading(groupId);
      setError(null);
      await budgetPlanningAPI.unlockGroup(groupId, fiscalYear);
      setSuccess(`Group unlocked successfully`);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to unlock group');
    } finally {
      setActionLoading(null);
    }
  };

  const toggleBsClass = (bsFlag: number) => {
    const newExpanded = new Set(expandedBsClasses);
    if (newExpanded.has(bsFlag)) {
      newExpanded.delete(bsFlag);
    } else {
      newExpanded.add(bsFlag);
    }
    setExpandedBsClasses(newExpanded);
  };

  const lockAllInClass = async (bsFlag: number) => {
    const groupsInClass = groups.filter(g => g.bs_flag === bsFlag && !g.locked_by_cfo);
    for (const group of groupsInClass) {
      await handleLock(group.budgeting_group_id, 'Bulk lock by BS class');
    }
  };

  const unlockAllInClass = async (bsFlag: number) => {
    const groupsInClass = groups.filter(g => g.bs_flag === bsFlag && g.locked_by_cfo);
    for (const group of groupsInClass) {
      await handleUnlock(group.budgeting_group_id);
    }
  };

  // Filter and search
  const filteredGroups = groups.filter(group => {
    const matchesSearch = !searchTerm || 
      group.budgeting_group_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.bs_group?.includes(searchTerm);
    
    const matchesFilter = 
      filterLocked === 'all' ||
      (filterLocked === 'locked' && group.locked_by_cfo) ||
      (filterLocked === 'unlocked' && !group.locked_by_cfo);
    
    return matchesSearch && matchesFilter;
  });

  // Group by BS class
  const groupsByBsClass = filteredGroups.reduce((acc, group) => {
    const bsFlag = group.bs_flag || 0;
    if (!acc[bsFlag]) {
      acc[bsFlag] = {
        bs_flag: bsFlag,
        bs_class_name: group.bs_class_name || `Class ${bsFlag}`,
        groups: [],
      };
    }
    acc[bsFlag].groups.push(group);
    return acc;
  }, {} as Record<number, { bs_flag: number; bs_class_name: string; groups: BudgetingGroupLock[] }>);

  const lockedCount = groups.filter(g => g.locked_by_cfo).length;
  const unlockedCount = groups.filter(g => !g.locked_by_cfo).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Lock className="w-5 h-5 text-amber-600" />
            CFO Locking Panel - FY {fiscalYear}
          </h2>
          <p className="text-sm text-gray-500">Lock budgeting groups to prevent department adjustments (baseline only)</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 p-4 bg-gray-50 border-b">
        <div className="bg-white rounded-lg p-3 border">
          <div className="text-sm text-gray-500">Total Groups</div>
          <div className="text-2xl font-bold text-gray-900">{groups.length}</div>
        </div>
        <div className="bg-white rounded-lg p-3 border border-amber-200">
          <div className="text-sm text-amber-600 flex items-center gap-1">
            <Lock className="w-3 h-3" /> Locked
          </div>
          <div className="text-2xl font-bold text-amber-600">{lockedCount}</div>
        </div>
        <div className="bg-white rounded-lg p-3 border border-green-200">
          <div className="text-sm text-green-600 flex items-center gap-1">
            <Unlock className="w-3 h-3" /> Unlocked
          </div>
          <div className="text-2xl font-bold text-green-600">{unlockedCount}</div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="m-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="w-4 h-4" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="m-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700">
          <Check className="w-4 h-4" />
          {success}
          <button onClick={() => setSuccess(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 p-4 border-b">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by group name or BS group..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilterLocked('all')}
            className={`px-3 py-2 rounded-lg text-sm ${filterLocked === 'all' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}
          >
            All
          </button>
          <button
            onClick={() => setFilterLocked('locked')}
            className={`px-3 py-2 rounded-lg text-sm flex items-center gap-1 ${filterLocked === 'locked' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}
          >
            <Lock className="w-3 h-3" /> Locked
          </button>
          <button
            onClick={() => setFilterLocked('unlocked')}
            className={`px-3 py-2 rounded-lg text-sm flex items-center gap-1 ${filterLocked === 'unlocked' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
          >
            <Unlock className="w-3 h-3" /> Unlocked
          </button>
        </div>
      </div>

      {/* Groups List */}
      <div className="max-h-[400px] overflow-y-auto">
        {Object.values(groupsByBsClass).map((bsClass) => {
          const lockedInClass = bsClass.groups.filter(g => g.locked_by_cfo).length;
          return (
            <div key={bsClass.bs_flag} className="border-b last:border-b-0">
              <button
                onClick={() => toggleBsClass(bsClass.bs_flag)}
                className="w-full flex items-center justify-between p-3 bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {expandedBsClasses.has(bsClass.bs_flag) ? (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  )}
                  <span className="font-semibold text-gray-800">{bsClass.bs_class_name}</span>
                  <span className="text-xs text-gray-500">
                    ({lockedInClass}/{bsClass.groups.length} locked)
                  </span>
                </div>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => lockAllInClass(bsClass.bs_flag)}
                    className="text-xs text-amber-600 hover:underline flex items-center gap-1"
                  >
                    <Lock className="w-3 h-3" /> Lock All
                  </button>
                  <button
                    onClick={() => unlockAllInClass(bsClass.bs_flag)}
                    className="text-xs text-green-600 hover:underline flex items-center gap-1"
                  >
                    <Unlock className="w-3 h-3" /> Unlock All
                  </button>
                </div>
              </button>

              {expandedBsClasses.has(bsClass.bs_flag) && (
                <div className="divide-y">
                  {bsClass.groups.map((group) => (
                    <div
                      key={group.budgeting_group_id}
                      className={`flex items-center justify-between p-3 pl-8 ${
                        group.locked_by_cfo ? 'bg-amber-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          {group.locked_by_cfo ? (
                            <Lock className="w-4 h-4 text-amber-600" />
                          ) : (
                            <Unlock className="w-4 h-4 text-gray-400" />
                          )}
                          <span className="font-medium text-gray-800">{group.budgeting_group_name}</span>
                          <span className="text-xs text-gray-500 font-mono">{group.bs_group}</span>
                        </div>
                        {group.cfo_lock_reason && (
                          <div className="text-xs text-amber-600 ml-6 mt-1">
                            Reason: {group.cfo_lock_reason}
                          </div>
                        )}
                        <div className="text-xs text-gray-500 ml-6 mt-1">
                          Baseline: {formatCurrency(group.total_baseline)} | Adjusted: {formatCurrency(group.total_adjusted)}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {group.locked_by_cfo ? (
                          <button
                            onClick={() => handleUnlock(group.budgeting_group_id)}
                            disabled={actionLoading === group.budgeting_group_id}
                            className="flex items-center gap-1 px-3 py-1.5 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 disabled:opacity-50 text-sm"
                          >
                            {actionLoading === group.budgeting_group_id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Unlock className="w-3 h-3" />
                            )}
                            Unlock
                          </button>
                        ) : (
                          <button
                            onClick={() => setLockReasonModal({ groupId: group.budgeting_group_id, groupName: group.budgeting_group_name })}
                            disabled={actionLoading === group.budgeting_group_id}
                            className="flex items-center gap-1 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 disabled:opacity-50 text-sm"
                          >
                            {actionLoading === group.budgeting_group_id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Lock className="w-3 h-3" />
                            )}
                            Lock
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {filteredGroups.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            No budgeting groups found matching your criteria
          </div>
        )}
      </div>

      {/* Lock Reason Modal */}
      {lockReasonModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <Lock className="w-5 h-5 text-amber-600" />
                Lock Budgeting Group
              </h3>
              <p className="text-sm text-gray-500">{lockReasonModal.groupName}</p>
            </div>
            <div className="p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Lock Reason (optional)
              </label>
              <textarea
                value={lockReason}
                onChange={(e) => setLockReason(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 h-24"
                placeholder="e.g., Baseline approved by CFO, no adjustments needed"
              />
              <p className="text-xs text-gray-500 mt-2">
                Locking this group will prevent department users from making adjustments. They will only see baseline values.
              </p>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t bg-gray-50">
              <button
                onClick={() => {
                  setLockReasonModal(null);
                  setLockReason('');
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={() => handleLock(lockReasonModal.groupId, lockReason)}
                disabled={actionLoading === lockReasonModal.groupId}
                className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                {actionLoading === lockReasonModal.groupId ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Lock className="w-4 h-4" />
                )}
                Lock Group
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CFOLockingPanel;
