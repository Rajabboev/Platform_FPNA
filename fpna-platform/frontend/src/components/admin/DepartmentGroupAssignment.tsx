import React, { useState, useEffect } from 'react';
import {
  Building2,
  Layers,
  Check,
  X,
  Loader2,
  AlertCircle,
  Save,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { departmentAPI, coaDimensionAPI } from '../../services/api';

interface Department {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  is_active: boolean;
  is_baseline_only: boolean;
  budgeting_groups: number[];
}

interface BudgetingGroup {
  group_id: number;
  group_name: string;
  bs_flag: number;
  bs_name: string;
  account_count: number;
}

interface Props {
  onClose?: () => void;
}

const DepartmentGroupAssignment: React.FC<Props> = ({ onClose }) => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [budgetingGroups, setBudgetingGroups] = useState<BudgetingGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const [selectedDept, setSelectedDept] = useState<Department | null>(null);
  const [assignedGroups, setAssignedGroups] = useState<Set<number>>(new Set());
  const [expandedBsClasses, setExpandedBsClasses] = useState<Set<number>>(new Set([1, 2, 3, 9]));

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [deptData, groupsData] = await Promise.all([
        departmentAPI.list(),
        coaDimensionAPI.getBudgetingGroups(),
      ]);
      setDepartments(deptData.departments || deptData || []);
      // API returns array directly, not wrapped in { groups: [] }
      setBudgetingGroups(Array.isArray(groupsData) ? groupsData : groupsData.groups || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDept = async (dept: Department) => {
    setSelectedDept(dept);
    setAssignedGroups(new Set(dept.budgeting_groups || []));
    setSuccess(null);
  };

  const toggleGroup = (groupId: number) => {
    const newAssigned = new Set(assignedGroups);
    if (newAssigned.has(groupId)) {
      newAssigned.delete(groupId);
    } else {
      newAssigned.add(groupId);
    }
    setAssignedGroups(newAssigned);
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

  const selectAllInClass = (bsFlag: number) => {
    const groupsInClass = budgetingGroups.filter(g => g.bs_flag === bsFlag);
    const newAssigned = new Set(assignedGroups);
    groupsInClass.forEach(g => newAssigned.add(g.group_id));
    setAssignedGroups(newAssigned);
  };

  const deselectAllInClass = (bsFlag: number) => {
    const groupsInClass = budgetingGroups.filter(g => g.bs_flag === bsFlag);
    const newAssigned = new Set(assignedGroups);
    groupsInClass.forEach(g => newAssigned.delete(g.group_id));
    setAssignedGroups(newAssigned);
  };

  const handleSave = async () => {
    if (!selectedDept) return;
    
    try {
      setSaving(true);
      setError(null);
      await departmentAPI.assignGroups(selectedDept.id, Array.from(assignedGroups));
      setSuccess(`Successfully assigned ${assignedGroups.size} budgeting groups to ${selectedDept.name_en}`);
      
      // Refresh department list
      const deptData = await departmentAPI.list();
      setDepartments(deptData.departments || deptData || []);
      
      // Update selected dept
      const updatedDept = (deptData.departments || deptData || []).find((d: Department) => d.id === selectedDept.id);
      if (updatedDept) {
        setSelectedDept(updatedDept);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save assignments');
    } finally {
      setSaving(false);
    }
  };

  // Group budgeting groups by BS class
  const groupsByBsClass = budgetingGroups.reduce((acc, group) => {
    const bsFlag = group.bs_flag || 0;
    if (!acc[bsFlag]) {
      acc[bsFlag] = {
        bs_flag: bsFlag,
        bs_name: group.bs_name || `Class ${bsFlag}`,
        groups: [],
      };
    }
    acc[bsFlag].groups.push(group);
    return acc;
  }, {} as Record<number, { bs_flag: number; bs_name: string; groups: BudgetingGroup[] }>);

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
          <h2 className="text-lg font-semibold text-gray-900">Department-to-Group Assignment</h2>
          <p className="text-sm text-gray-500">Assign budgeting groups to departments for budget planning</p>
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

      <div className="flex h-[500px]">
        {/* Department List */}
        <div className="w-1/3 border-r overflow-y-auto">
          <div className="p-3 bg-gray-50 border-b sticky top-0">
            <h3 className="font-medium text-gray-700 flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              Departments ({departments.length})
            </h3>
          </div>
          <div className="divide-y">
            {departments.map((dept) => (
              <button
                key={dept.id}
                onClick={() => handleSelectDept(dept)}
                className={`w-full text-left p-3 hover:bg-gray-50 transition-colors ${
                  selectedDept?.id === dept.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                }`}
              >
                <div className="font-medium text-gray-900">{dept.name_en}</div>
                <div className="text-xs text-gray-500 flex items-center gap-2 mt-1">
                  <span>{dept.code}</span>
                  {dept.is_baseline_only && (
                    <span className="px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded">Baseline Only</span>
                  )}
                  <span className="text-blue-600">{dept.budgeting_groups?.length || 0} groups</span>
                </div>
              </button>
            ))}
            {departments.length === 0 && (
              <div className="p-4 text-center text-gray-500">No departments found</div>
            )}
          </div>
        </div>

        {/* Budgeting Groups Selection */}
        <div className="flex-1 overflow-y-auto">
          {selectedDept ? (
            <>
              <div className="p-3 bg-gray-50 border-b sticky top-0 z-10 flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-700 flex items-center gap-2">
                    <Layers className="w-4 h-4" />
                    Budgeting Groups for {selectedDept.name_en}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {assignedGroups.size} of {budgetingGroups.length} groups selected
                  </p>
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Assignments
                </button>
              </div>

              <div className="p-2">
                {Object.values(groupsByBsClass).map((bsClass) => (
                  <div key={bsClass.bs_flag} className="mb-2 border rounded-lg overflow-hidden">
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
                        <span className="font-medium text-gray-800">{bsClass.bs_name}</span>
                        <span className="text-xs text-gray-500">
                          ({bsClass.groups.filter(g => assignedGroups.has(g.group_id)).length}/{bsClass.groups.length} selected)
                        </span>
                      </div>
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => selectAllInClass(bsClass.bs_flag)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Select All
                        </button>
                        <button
                          onClick={() => deselectAllInClass(bsClass.bs_flag)}
                          className="text-xs text-gray-600 hover:underline"
                        >
                          Deselect All
                        </button>
                      </div>
                    </button>

                    {expandedBsClasses.has(bsClass.bs_flag) && (
                      <div className="divide-y">
                        {bsClass.groups.map((group) => (
                          <label
                            key={group.group_id}
                            className="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={assignedGroups.has(group.group_id)}
                              onChange={() => toggleGroup(group.group_id)}
                              className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                            />
                            <div className="flex-1">
                              <div className="font-medium text-gray-800">{group.group_name}</div>
                              <div className="text-xs text-gray-500">{group.account_count} accounts</div>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <Building2 className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>Select a department to assign budgeting groups</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DepartmentGroupAssignment;
