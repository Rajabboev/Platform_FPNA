import React, { useState, useEffect } from 'react';
import {
  Layers,
  Calculator,
  Check,
  X,
  Loader2,
  AlertCircle,
  Save,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Star,
  Info,
} from 'lucide-react';
import { driversAPI, coaDimensionAPI } from '../../services/api';

interface Driver {
  id: number;
  code: string;
  name_en: string;
  driver_type: string;
  description: string | null;
  formula_description: string | null;
  default_value: number | null;
  unit: string;
  is_active: boolean;
}

interface BudgetingGroup {
  group_id: number;
  group_name: string;
  bs_flag: number;
  bs_name: string;
  account_count: number;
}

interface DriverAssignment {
  id: number;
  driver_id: number;
  driver_code: string;
  driver_name: string;
  budgeting_group_id: number;
  is_default: boolean;
}

interface Props {
  onClose?: () => void;
}

const DriverGroupAssignment: React.FC<Props> = ({ onClose }) => {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [budgetingGroups, setBudgetingGroups] = useState<BudgetingGroup[]>([]);
  const [assignments, setAssignments] = useState<DriverAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const [selectedGroup, setSelectedGroup] = useState<BudgetingGroup | null>(null);
  const [assignedDrivers, setAssignedDrivers] = useState<Set<number>>(new Set());
  const [defaultDriverId, setDefaultDriverId] = useState<number | null>(null);
  const [expandedBsClasses, setExpandedBsClasses] = useState<Set<number>>(new Set([1, 2, 3, 9]));
  const [hoveredDriver, setHoveredDriver] = useState<number | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [driversData, groupsData, assignmentsData] = await Promise.all([
        driversAPI.list({ is_active: true }),
        coaDimensionAPI.getBudgetingGroups(),
        driversAPI.listGroupAssignments().catch(() => []),
      ]);
      setDrivers(Array.isArray(driversData) ? driversData : driversData.drivers || []);
      setBudgetingGroups(Array.isArray(groupsData) ? groupsData : groupsData.groups || []);
      setAssignments(Array.isArray(assignmentsData) ? assignmentsData : assignmentsData.assignments || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectGroup = (group: BudgetingGroup) => {
    setSelectedGroup(group);
    setSuccess(null);
    
    // Load current assignments for this group
    const groupAssignments = assignments.filter(a => a.budgeting_group_id === group.group_id);
    setAssignedDrivers(new Set(groupAssignments.map(a => a.driver_id)));
    
    const defaultAssignment = groupAssignments.find(a => a.is_default);
    setDefaultDriverId(defaultAssignment?.driver_id || null);
  };

  const toggleDriver = (driverId: number) => {
    const newAssigned = new Set(assignedDrivers);
    if (newAssigned.has(driverId)) {
      newAssigned.delete(driverId);
      if (defaultDriverId === driverId) {
        setDefaultDriverId(null);
      }
    } else {
      newAssigned.add(driverId);
    }
    setAssignedDrivers(newAssigned);
  };

  const setAsDefault = (driverId: number) => {
    if (assignedDrivers.has(driverId)) {
      setDefaultDriverId(driverId);
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

  const handleSave = async () => {
    if (!selectedGroup) return;
    
    try {
      setSaving(true);
      setError(null);
      
      await driversAPI.bulkAssignToGroup(
        selectedGroup.group_id,
        Array.from(assignedDrivers),
        defaultDriverId || undefined
      );
      
      setSuccess(`Successfully assigned ${assignedDrivers.size} drivers to ${selectedGroup.group_name}`);
      
      // Refresh assignments
      const assignmentsData = await driversAPI.listGroupAssignments();
      setAssignments(assignmentsData.assignments || []);
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

  // Group drivers by type
  const driversByType = drivers.reduce((acc, driver) => {
    const type = driver.driver_type || 'other';
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(driver);
    return acc;
  }, {} as Record<string, Driver[]>);

  const driverTypeLabels: Record<string, string> = {
    yield_rate: 'Yield Rates',
    cost_rate: 'Cost Rates',
    growth_rate: 'Growth Rates',
    provision_rate: 'Provision Rates',
    fx_rate: 'FX Rates',
    inflation_rate: 'Inflation Rates',
    headcount: 'Headcount',
    custom: 'Custom',
    other: 'Other',
  };

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
          <h2 className="text-lg font-semibold text-gray-900">Driver-to-Group Assignment</h2>
          <p className="text-sm text-gray-500">Assign allowed drivers to budgeting groups (CFO defines which drivers apply)</p>
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
        {/* Budgeting Groups List */}
        <div className="w-1/3 border-r overflow-y-auto">
          <div className="p-3 bg-gray-50 border-b sticky top-0">
            <h3 className="font-medium text-gray-700 flex items-center gap-2">
              <Layers className="w-4 h-4" />
              Budgeting Groups ({budgetingGroups.length})
            </h3>
          </div>
          <div>
            {Object.values(groupsByBsClass).map((bsClass) => (
              <div key={bsClass.bs_flag}>
                <button
                  onClick={() => toggleBsClass(bsClass.bs_flag)}
                  className="w-full flex items-center gap-2 p-2 bg-gray-100 hover:bg-gray-200 border-b text-sm font-medium text-gray-700"
                >
                  {expandedBsClasses.has(bsClass.bs_flag) ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                  {bsClass.bs_name}
                </button>
                {expandedBsClasses.has(bsClass.bs_flag) && (
                  <div className="divide-y">
                    {bsClass.groups.map((group) => {
                      const groupAssignments = assignments.filter(a => a.budgeting_group_id === group.group_id);
                      return (
                        <button
                          key={group.group_id}
                          onClick={() => handleSelectGroup(group)}
                          className={`w-full text-left p-3 hover:bg-gray-50 transition-colors ${
                            selectedGroup?.group_id === group.group_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                          }`}
                        >
                          <div className="font-medium text-gray-900 text-sm">{group.group_name}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {groupAssignments.length} drivers assigned
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Drivers Selection */}
        <div className="flex-1 overflow-y-auto">
          {selectedGroup ? (
            <>
              <div className="p-3 bg-gray-50 border-b sticky top-0 z-10 flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-700 flex items-center gap-2">
                    <Calculator className="w-4 h-4" />
                    Drivers for {selectedGroup.group_name}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {assignedDrivers.size} of {drivers.length} drivers selected
                    {defaultDriverId && <span className="ml-2 text-amber-600">• Default set</span>}
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
                {Object.entries(driversByType).map(([type, typeDrivers]) => (
                  <div key={type} className="mb-3">
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-2 py-1 bg-gray-100 rounded">
                      {driverTypeLabels[type] || type}
                    </div>
                    <div className="divide-y">
                      {typeDrivers.map((driver) => (
                        <div
                          key={driver.id}
                          className="flex items-center gap-3 p-3 hover:bg-gray-50"
                        >
                          <input
                            type="checkbox"
                            checked={assignedDrivers.has(driver.id)}
                            onChange={() => toggleDriver(driver.id)}
                            className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                          />
                          <div 
                            className="flex-1 relative"
                            onMouseEnter={() => setHoveredDriver(driver.id)}
                            onMouseLeave={() => setHoveredDriver(null)}
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-800">{driver.name_en}</span>
                              <span className="text-xs text-gray-500 font-mono">{driver.code}</span>
                              {driver.description && (
                                <Info className="w-3 h-3 text-gray-400 cursor-help" />
                              )}
                            </div>
                            {driver.default_value && (
                              <div className="text-xs text-gray-500">
                                Default: {driver.default_value}{driver.unit}
                              </div>
                            )}
                            
                            {/* Tooltip */}
                            {hoveredDriver === driver.id && driver.description && (
                              <div className="absolute z-50 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg left-0 bottom-full mb-2">
                                <div className="font-semibold mb-1">{driver.name_en}</div>
                                <p className="text-gray-300">{driver.description}</p>
                                {driver.formula_description && (
                                  <p className="text-green-300 mt-1">Formula: {driver.formula_description}</p>
                                )}
                              </div>
                            )}
                          </div>
                          
                          {assignedDrivers.has(driver.id) && (
                            <button
                              onClick={() => setAsDefault(driver.id)}
                              className={`p-1.5 rounded ${
                                defaultDriverId === driver.id
                                  ? 'bg-amber-100 text-amber-600'
                                  : 'text-gray-400 hover:bg-gray-100'
                              }`}
                              title={defaultDriverId === driver.id ? 'Default driver' : 'Set as default'}
                            >
                              <Star className={`w-4 h-4 ${defaultDriverId === driver.id ? 'fill-current' : ''}`} />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <Layers className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>Select a budgeting group to assign drivers</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DriverGroupAssignment;
