import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2, AlertCircle, Check, X, Plus, Pencil, Trash2,
  ChevronRight, ChevronDown, RefreshCw, Building2, Users,
  Layers, Database, Link2, Search,
} from 'lucide-react';
import { departmentAPI, coaDimensionAPI } from '../../services/api';

// ── Types ──────────────────────────────────────────────────────────────────
interface BudgetingGroupInfo {
  group_id: number;
  group_name: string;
  category: string;
  bs_flag: number;
  bs_name: string;
  account_count: number;
}

interface DepartmentInfo {
  id: number;
  code: string;
  name_en: string;
  name_uz?: string;
  name_ru?: string;
  description?: string;
  parent_id?: number;
  head_user_id?: number;
  manager_user_id?: number;
  head_user_name?: string;
  manager_user_name?: string;
  is_active: boolean;
  is_baseline_only: boolean;
  display_order: number;
  budgeting_group_ids: number[];
  product_keys?: string[];
  /** FP&A taxonomy key this unit owns (Loans, Deposits, …). */
  primary_product_key?: string | null;
  product_label_en?: string | null;
  product_pillar?: string | null;
  /** Must match DWH segment_key after ingest (case-insensitive). Empty = consolidated baseline. */
  dwh_segment_value?: string | null;
}

interface TaxonomyItem {
  key: string;
  label_en: string;
  pillar: string;
}

interface HierarchyClass {
  bs_flag: number;
  bs_name: string;
  account_count: number;
  bs_groups: {
    bs_group: string;
    group_name: string;
    products?: {
      product_key: string;
      product_label_en: string;
      product_pillar?: string;
      display_group?: string;
      accounts: { coa_code: string; coa_name: string }[];
    }[];
    /** @deprecated API shape — use `products` */
    budgeting_groups?: {
      product_key?: string;
      budgeting_group_id?: number | null;
      budgeting_group_name?: string;
      product_label_en?: string;
      accounts?: { coa_code: string; coa_name: string }[];
    }[];
  }[];
}

// ── Budget Structure Page ──────────────────────────────────────────────────
const BudgetStructure: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mapping' | 'hierarchy' | 'departments'>('mapping');
  const [departments, setDepartments] = useState<DepartmentInfo[]>([]);
  const [budgetingGroups, setBudgetingGroups] = useState<BudgetingGroupInfo[]>([]);
  const [hierarchy, setHierarchy] = useState<HierarchyClass[]>([]);
  const [taxonomyItems, setTaxonomyItems] = useState<TaxonomyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [deptData, groupsData, hierData, taxData] = await Promise.all([
        departmentAPI.list(),
        coaDimensionAPI.getBudgetingGroups().catch(() => ({ groups: [] })),
        coaDimensionAPI.getHierarchy().catch(() => ({ hierarchy: [] })),
        coaDimensionAPI.getProductTaxonomy().catch(() => ({ items: [] })),
      ]);
      setDepartments(Array.isArray(deptData) ? deptData : deptData.departments || []);
      setBudgetingGroups(groupsData.groups || groupsData || []);
      setHierarchy(hierData.hierarchy || []);
      setTaxonomyItems(taxData.items || []);
      setInitialLoaded(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
      setInitialLoaded(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const clearMessages = () => { setError(null); setSuccess(null); };

  if (loading && !initialLoaded) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Budget Structure</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Product-owner units (FP&A taxonomy), legacy group mapping, and COA hierarchy
          </p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-800 dark:text-gray-300 dark:border-slate-600">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="text-red-800 dark:text-red-300 flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4 text-red-400" /></button>
        </div>
      )}
      {success && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 flex items-center gap-3">
          <Check className="w-5 h-5 text-green-600" />
          <span className="text-green-800 dark:text-green-300 flex-1">{success}</span>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4 text-green-400" /></button>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700">
        <div className="p-4 border-b border-gray-200 dark:border-slate-700 flex gap-2">
          {(['mapping', 'hierarchy', 'departments'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); clearMessages(); }}
              className={`px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2 ${
                activeTab === tab ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-slate-800'
              }`}
            >
              {tab === 'mapping' && <><Link2 className="w-4 h-4" /> Dept → Groups</>}
              {tab === 'hierarchy' && <><Layers className="w-4 h-4" /> Budget Hierarchy</>}
              {tab === 'departments' && <><Building2 className="w-4 h-4" /> Product owners ({departments.length})</>}
            </button>
          ))}
        </div>

        <div className="p-4">
          {activeTab === 'mapping' && (
            <MappingTab
              departments={departments}
              budgetingGroups={budgetingGroups}
              onRefresh={fetchData}
              onError={setError}
              onSuccess={setSuccess}
            />
          )}
          {activeTab === 'hierarchy' && (
            <HierarchyTab hierarchy={hierarchy} departments={departments} budgetingGroups={budgetingGroups} />
          )}
          {activeTab === 'departments' && (
            <DepartmentsTab
              departments={departments}
              taxonomyItems={taxonomyItems}
              onRefresh={fetchData}
              onError={setError}
              onSuccess={setSuccess}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// ── Tab 1: Department → Group Mapping ──────────────────────────────────────
const MappingTab: React.FC<{
  departments: DepartmentInfo[];
  budgetingGroups: BudgetingGroupInfo[];
  onRefresh: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ departments, budgetingGroups, onRefresh, onError, onSuccess }) => {
  const [selectedDept, setSelectedDept] = useState<number | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedGroupIds, setSelectedGroupIds] = useState<Set<number>>(new Set());

  const dept = departments.find(d => d.id === selectedDept);
  const deptGroups = budgetingGroups.filter(g => dept?.budgeting_group_ids.includes(g.group_id));

  const openAssignModal = () => {
    if (!dept) return;
    setSelectedGroupIds(new Set(dept.budgeting_group_ids));
    setShowAssignModal(true);
  };

  const handleSaveAssignment = async () => {
    if (!dept) return;
    try {
      setAssigning(true);
      await departmentAPI.assignGroups(dept.id, Array.from(selectedGroupIds));
      onSuccess(`Updated group assignments for ${dept.name_en}`);
      setShowAssignModal(false);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to assign groups');
    } finally {
      setAssigning(false);
    }
  };

  const toggleGroup = (groupId: number) => {
    setSelectedGroupIds(prev => {
      const next = new Set(prev);
      next.has(groupId) ? next.delete(groupId) : next.add(groupId);
      return next;
    });
  };

  // Group budgeting groups by BS class for the assign modal
  const groupsByClass: Record<string, BudgetingGroupInfo[]> = {};
  for (const g of budgetingGroups) {
    const key = g.bs_name || `Class ${g.bs_flag}`;
    if (!groupsByClass[key]) groupsByClass[key] = [];
    groupsByClass[key].push(g);
  }

  return (
    <div className="grid grid-cols-3 gap-6">
      {/* Left: Department List */}
      <div className="col-span-1 space-y-2">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Product owners</h3>
        {departments.length === 0 && (
          <p className="text-gray-400 text-sm">No product owner units yet. Use the Product owners tab or Seed from taxonomy.</p>
        )}
        {departments.map(d => (
          <button
            key={d.id}
            onClick={() => setSelectedDept(d.id)}
            className={`w-full text-left p-3 rounded-lg border transition-colors ${
              selectedDept === d.id
                ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                : 'border-gray-200 dark:border-slate-700 hover:border-gray-300 hover:bg-gray-50 dark:hover:bg-slate-800'
            }`}
          >
            <div className="font-medium text-gray-900 dark:text-white">{d.name_en}</div>
            {d.primary_product_key && (
              <div className="text-xs text-primary-600 dark:text-primary-400 font-mono mt-0.5">{d.primary_product_key}</div>
            )}
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-3">
              <span className="font-mono">{d.code}</span>
              <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded">
                {d.budgeting_group_ids.length} groups
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Right: Assigned Groups */}
      <div className="col-span-2">
        {!dept ? (
          <div className="flex items-center justify-center h-64 text-gray-400">
            <div className="text-center">
              <Building2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>Select a department to view its budgeting groups</p>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{dept.name_en}</h3>
                <p className="text-sm text-gray-500">
                  {dept.head_user_name && <span>Head: {dept.head_user_name}</span>}
                  {dept.manager_user_name && <span className="ml-3">Manager: {dept.manager_user_name}</span>}
                </p>
              </div>
              <button
                onClick={openAssignModal}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                <Link2 className="w-4 h-4" /> Assign Groups
              </button>
            </div>

            {deptGroups.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Layers className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>No budgeting groups assigned yet</p>
                <button onClick={openAssignModal} className="mt-3 text-primary-600 hover:underline text-sm">
                  Assign groups now
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {deptGroups.map(g => (
                  <div key={g.group_id} className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">{g.group_name}</div>
                        <div className="text-xs text-gray-500 mt-1">{g.bs_name}</div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        g.category === 'ASSET' ? 'bg-blue-100 text-blue-700' :
                        g.category === 'LIABILITY' ? 'bg-red-100 text-red-700' :
                        g.category === 'CAPITAL' ? 'bg-green-100 text-green-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {g.category}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-2">{g.account_count} COA accounts</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Assign Modal */}
      {showAssignModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b dark:border-slate-700">
              <h3 className="text-lg font-semibold">Assign Budgeting Groups to {dept?.name_en}</h3>
              <p className="text-sm text-gray-500 mt-1">Select groups this department will manage</p>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {Object.entries(groupsByClass).map(([className, groups]) => (
                <div key={className}>
                  <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">{className}</h4>
                  <div className="space-y-1">
                    {groups.map(g => (
                      <label key={g.group_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedGroupIds.has(g.group_id)}
                          onChange={() => toggleGroup(g.group_id)}
                          className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                        />
                        <span className="text-gray-900 dark:text-white">{g.group_name}</span>
                        <span className="text-xs text-gray-400 ml-auto">{g.account_count} accounts</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              {budgetingGroups.length === 0 && (
                <p className="text-gray-400 text-center py-8">No budgeting groups available. Import COA dimension first.</p>
              )}
            </div>
            <div className="flex justify-between items-center p-4 border-t dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 rounded-b-xl">
              <span className="text-sm text-gray-500">{selectedGroupIds.size} selected</span>
              <div className="flex gap-2">
                <button onClick={() => setShowAssignModal(false)} className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg">Cancel</button>
                <button onClick={handleSaveAssignment} disabled={assigning} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">
                  {assigning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Tab 2: Budget Hierarchy ────────────────────────────────────────────────
const HierarchyTab: React.FC<{
  hierarchy: HierarchyClass[];
  departments: DepartmentInfo[];
  budgetingGroups: BudgetingGroupInfo[];
}> = ({ hierarchy, departments }) => {
  const [expandedClasses, setExpandedClasses] = useState<Set<number>>(() => new Set(hierarchy.map(c => c.bs_flag)));
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const hierarchyBucketId = (bg: { product_key?: string; budgeting_group_id?: number | null }) =>
    bg.product_key || `bg:${bg.budgeting_group_id ?? 'none'}`;

  const bucketsForBsGroup = (bsGroup: HierarchyClass['bs_groups'][0]) =>
    bsGroup.products ?? bsGroup.budgeting_groups ?? [];

  const groupToDepts: Record<string, string[]> = {};
  for (const d of departments) {
    const pks = new Set<string>(d.product_keys || []);
    if (d.primary_product_key) pks.add(d.primary_product_key);
    for (const pk of pks) {
      if (!groupToDepts[pk]) groupToDepts[pk] = [];
      groupToDepts[pk].push(d.name_en);
    }
    for (const gid of d.budgeting_group_ids) {
      const id = `bg:${gid}`;
      if (!groupToDepts[id]) groupToDepts[id] = [];
      groupToDepts[id].push(d.name_en);
    }
  }

  const toggleClass = (flag: number) => {
    setExpandedClasses(prev => {
      const next = new Set(prev);
      next.has(flag) ? next.delete(flag) : next.add(flag);
      return next;
    });
  };

  const toggleGroup = (bucketId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      next.has(bucketId) ? next.delete(bucketId) : next.add(bucketId);
      return next;
    });
  };

  const classColors: Record<number, string> = {
    1: 'border-l-blue-500', 2: 'border-l-red-500', 3: 'border-l-green-500', 4: 'border-l-amber-500', 9: 'border-l-gray-400',
  };

  return (
    <div className="space-y-3">
      {hierarchy.map(bsClass => (
        <div key={bsClass.bs_flag} className={`border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden border-l-4 ${classColors[bsClass.bs_flag] || 'border-l-gray-300'}`}>
          <button
            onClick={() => toggleClass(bsClass.bs_flag)}
            className="w-full flex items-center gap-3 p-4 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
          >
            {expandedClasses.has(bsClass.bs_flag) ? <ChevronDown className="w-5 h-5 text-gray-500" /> : <ChevronRight className="w-5 h-5 text-gray-500" />}
            <span className="font-bold text-gray-900 dark:text-white text-lg">{bsClass.bs_name}</span>
            <span className="text-sm text-gray-500 ml-auto">{bsClass.account_count} accounts</span>
          </button>

          {expandedClasses.has(bsClass.bs_flag) && (
            <div className="border-t border-gray-200 dark:border-slate-700">
              {bsClass.bs_groups?.map(bsGroup => (
                <div key={bsGroup.bs_group}>
                  {bucketsForBsGroup(bsGroup).map((bg: any) => {
                    const bid = hierarchyBucketId(bg);
                    const deptNames = groupToDepts[bid] || [];
                    return (
                      <div key={bid} className="border-b border-gray-100 dark:border-slate-700/50 last:border-b-0">
                        <button
                          onClick={() => toggleGroup(bid)}
                          className="w-full flex items-center gap-3 p-3 pl-10 hover:bg-gray-50 dark:hover:bg-slate-800"
                        >
                          {expandedGroups.has(bid) ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                          <span className="font-medium text-gray-800 dark:text-gray-200">{bg.product_label_en || bg.budgeting_group_name || 'Unassigned'}</span>
                          {deptNames.length > 0 && (
                            <div className="flex gap-1 ml-2">
                              {deptNames.map(name => (
                                <span key={name} className="px-2 py-0.5 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded text-xs">
                                  {name}
                                </span>
                              ))}
                            </div>
                          )}
                          <span className="text-xs text-gray-400 ml-auto">{bg.accounts?.length || 0} accounts</span>
                        </button>

                        {expandedGroups.has(bid) && bg.accounts && (
                          <div className="bg-gray-50 dark:bg-slate-800/50 py-1">
                            {bg.accounts.map((acc: any) => (
                              <div key={acc.coa_code} className="flex items-center gap-3 py-1.5 pl-20 pr-4">
                                <span className="font-mono text-sm text-blue-600 dark:text-blue-400 font-medium">{acc.coa_code}</span>
                                <span className="text-gray-700 dark:text-gray-300 text-sm truncate">{acc.coa_name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {hierarchy.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Database className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No COA hierarchy data. Import COA Dimension first.</p>
        </div>
      )}
    </div>
  );
};

// ── Tab 3: Product owner departments CRUD ────────────────────────────────────
const DepartmentsTab: React.FC<{
  departments: DepartmentInfo[];
  taxonomyItems: TaxonomyItem[];
  onRefresh: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ departments, taxonomyItems, onRefresh, onError, onSuccess }) => {
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<DepartmentInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [form, setForm] = useState({
    code: '', name_en: '', name_uz: '', name_ru: '', description: '', parent_id: 0, display_order: 0, is_baseline_only: false, dwh_segment_value: '', primary_product_key: '',
  });

  const taxonomyChoices = taxonomyItems.filter(t => t.key !== 'UNCLASSIFIED');

  const openCreate = () => {
    setEditing(null);
    setForm({
      code: '', name_en: '', name_uz: '', name_ru: '', description: '', parent_id: 0, display_order: 0, is_baseline_only: false, dwh_segment_value: '', primary_product_key: '',
    });
    setShowForm(true);
  };

  const openEdit = (dept: DepartmentInfo) => {
    setEditing(dept);
    setForm({
      code: dept.code,
      name_en: dept.name_en,
      name_uz: dept.name_uz || '',
      name_ru: dept.name_ru || '',
      description: dept.description || '',
      parent_id: dept.parent_id || 0,
      display_order: dept.display_order,
      is_baseline_only: dept.is_baseline_only,
      dwh_segment_value: dept.dwh_segment_value || '',
      primary_product_key: dept.primary_product_key || '',
    });
    setShowForm(true);
  };

  const handleSeedFromTaxonomy = async () => {
    if (!confirm('Create or align one department per FP&A product (except Unclassified)? Existing product access rows are replaced per department.')) return;
    try {
      setSeeding(true);
      const res = await departmentAPI.seedProductOwners();
      onSuccess(res.message || `Created ${res.created_departments}, updated ${res.updated_departments}`);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || err.message || 'Seed failed');
    } finally {
      setSeeding(false);
    }
  };

  const handleSave = async () => {
    if (!form.code || !form.name_en) { onError('Code and name are required'); return; }
    try {
      setSaving(true);
      const payload: Record<string, unknown> = {
        name_en: form.name_en,
        name_uz: form.name_uz || undefined,
        name_ru: form.name_ru || undefined,
        description: form.description || undefined,
        parent_id: form.parent_id || undefined,
        display_order: form.display_order,
        is_baseline_only: form.is_baseline_only,
        dwh_segment_value: form.dwh_segment_value.trim() || undefined,
        primary_product_key: form.primary_product_key.trim()
          ? form.primary_product_key.trim().toUpperCase()
          : null,
      };
      if (editing) {
        await departmentAPI.update(editing.id, payload);
        onSuccess(`Updated product owner ${form.name_en}`);
      } else {
        await departmentAPI.create({
          code: form.code,
          name_en: form.name_en,
          name_uz: form.name_uz || undefined,
          name_ru: form.name_ru || undefined,
          description: form.description || undefined,
          parent_id: form.parent_id || undefined,
          display_order: form.display_order,
          is_baseline_only: form.is_baseline_only,
          dwh_segment_value: form.dwh_segment_value.trim() || undefined,
          primary_product_key: form.primary_product_key.trim()
            ? form.primary_product_key.trim().toUpperCase()
            : undefined,
        });
        onSuccess(`Created product owner ${form.name_en}`);
      }
      setShowForm(false);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to save department');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (dept: DepartmentInfo) => {
    if (!confirm(`Deactivate department "${dept.name_en}"?`)) return;
    try {
      await departmentAPI.delete(dept.id);
      onSuccess(`Deactivated ${dept.name_en}`);
      onRefresh();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Failed to delete');
    }
  };

  return (
    <div>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Each row is a <strong>product owner</strong> (e.g. Loans, Deposits): the FP&A taxonomy level that submits budget plans for that product. Use “Seed from taxonomy” to align names and access with the canonical product list.
      </p>
      <div className="flex flex-wrap justify-end gap-2 mb-4">
        <button
          type="button"
          onClick={handleSeedFromTaxonomy}
          disabled={seeding}
          className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50"
        >
          {seeding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
          Seed from taxonomy
        </button>
        <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
          <Plus className="w-4 h-4" /> Add product owner
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Code</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">FP&A product</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">DWH segment</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Name</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Head</th>
              <th className="text-left p-3 font-semibold text-gray-700 dark:text-gray-300">Manager</th>
              <th className="text-center p-3 font-semibold text-gray-700 dark:text-gray-300">Groups</th>
              <th className="text-center p-3 font-semibold text-gray-700 dark:text-gray-300">Status</th>
              <th className="text-center p-3 font-semibold text-gray-700 dark:text-gray-300">Actions</th>
            </tr>
          </thead>
          <tbody>
            {departments.map(d => (
              <tr key={d.id} className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-800/50">
                <td className="p-3 font-mono font-medium text-primary-600">{d.code}</td>
                <td className="p-3">
                  {d.primary_product_key ? (
                    <div>
                      <span className="font-mono text-xs text-primary-600 dark:text-primary-400">{d.primary_product_key}</span>
                      <div className="text-gray-600 dark:text-gray-400 text-xs">{d.product_label_en || '—'} · {d.product_pillar || '—'}</div>
                    </div>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="p-3 font-mono text-xs text-gray-600 dark:text-gray-400">{d.dwh_segment_value || '—'}</td>
                <td className="p-3">
                  <div className="text-gray-900 dark:text-white">{d.name_en}</div>
                  {d.name_uz && <div className="text-gray-500 text-xs">{d.name_uz}</div>}
                </td>
                <td className="p-3 text-gray-600 dark:text-gray-400">{d.head_user_name || '—'}</td>
                <td className="p-3 text-gray-600 dark:text-gray-400">{d.manager_user_name || '—'}</td>
                <td className="p-3 text-center">
                  <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs font-medium">
                    {d.budgeting_group_ids.length}
                  </span>
                </td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${d.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                    {d.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="p-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <button onClick={() => openEdit(d)} className="p-1 text-gray-400 hover:text-primary-600"><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => handleDelete(d)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl w-full max-w-md">
            <div className="p-4 border-b dark:border-slate-700">
              <h3 className="text-lg font-semibold">{editing ? 'Edit' : 'New'} product owner</h3>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">FP&A product (taxonomy)</label>
                <select
                  value={form.primary_product_key}
                  onChange={(e) => {
                    const v = e.target.value;
                    setForm((f) => {
                      const t = taxonomyChoices.find(x => x.key === v);
                      const next = { ...f, primary_product_key: v };
                      if (t && !editing) {
                        if (!f.code.trim()) next.code = t.key;
                        if (!f.name_en.trim()) next.name_en = t.label_en;
                      }
                      return next;
                    });
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">— None (legacy / manual access only) —</option>
                  {taxonomyChoices.map(t => (
                    <option key={t.key} value={t.key}>{t.label_en} ({t.key}) · {t.pillar}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">One active department may own each product key.</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Code *</label>
                  <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} disabled={!!editing}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500 disabled:opacity-50" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Order</label>
                  <input type="number" value={form.display_order} onChange={e => setForm({ ...form, display_order: parseInt(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (EN) *</label>
                <input value={form.name_en} onChange={e => setForm({ ...form, name_en: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (UZ)</label>
                  <input value={form.name_uz} onChange={e => setForm({ ...form, name_uz: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (RU)</label>
                  <input value={form.name_ru} onChange={e => setForm({ ...form, name_ru: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Parent unit (optional roll-up)</label>
                <select value={form.parent_id} onChange={e => setForm({ ...form, parent_id: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500">
                  <option value={0}>None (top-level)</option>
                  {departments.filter(d => d.id !== editing?.id).map(d => (
                    <option key={d.id} value={d.id}>{d.name_en}</option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_baseline_only} onChange={e => setForm({ ...form, is_baseline_only: e.target.checked })}
                  className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500" />
                <span className="text-gray-700 dark:text-gray-300">Baseline only (no adjustments)</span>
              </label>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">DWH baseline segment</label>
                <input
                  value={form.dwh_segment_value}
                  onChange={(e) => setForm({ ...form, dwh_segment_value: e.target.value })}
                  placeholder="e.g. RETAIL — must match ingest column; leave empty for bank-wide totals"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Set only if Step 1 ingest maps a segment column. If any department has a value here, plans are built per segment.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 rounded-b-xl">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg">Cancel</button>
              <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                {editing ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BudgetStructure;
