// FP&A System Modules - COA, Currencies, Drivers, Templates, Snapshots
import React, { useState, useEffect } from 'react';
import {
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  Pencil,
  ChevronRight,
  ChevronDown,
  Check,
  X,
  RefreshCw,
  DollarSign,
  Calculator,
  FileText,
  Database,
  Settings,
  Play,
  Clock,
  TrendingUp,
  Layers,
  Building2,
  Banknote,
  ArrowRightLeft,
  Target,
  Zap,
  LayoutTemplate,
  ClipboardList,
  Calendar,
  Users,
  Send,
} from 'lucide-react';
import {
  coaAPI,
  coaDimensionAPI,
  currenciesAPI,
  driversAPI,
  templatesAPI,
  snapshotsAPI,
  departmentAPI,
} from '../services/api';

// ============================================
// Shared Components
// ============================================

const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-64">
    <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
  </div>
);

const ErrorMessage = ({ message }: { message: string }) => (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
    <div>
      <p className="text-red-800 font-medium">Error</p>
      <p className="text-red-700 text-sm mt-1">{message}</p>
    </div>
  </div>
);

const SuccessMessage = ({ message }: { message: string }) => (
  <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
    <Check className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
    <div>
      <p className="text-green-800 font-medium">Success</p>
      <p className="text-green-700 text-sm mt-1">{message}</p>
    </div>
  </div>
);

const PageHeader = ({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) => (
  <div className="flex items-center justify-between mb-6">
    <div>
      <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      {subtitle && <p className="text-gray-600 mt-1">{subtitle}</p>}
    </div>
    {actions && <div className="flex gap-2">{actions}</div>}
  </div>
);

const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-white rounded-xl shadow-sm border border-gray-200 ${className}`}>
    {children}
  </div>
);

const TabButton = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
  <button
    onClick={onClick}
    className={`px-4 py-2 font-medium rounded-lg transition-colors ${
      active
        ? 'bg-primary-100 text-primary-700'
        : 'text-gray-600 hover:bg-gray-100'
    }`}
  >
    {children}
  </button>
);

// ============================================
// COA (Chart of Accounts) Page
// ============================================

interface AccountClass {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  class_type: string;
  nature: string;
  is_active: boolean;
}

interface AccountGroup {
  id: number;
  code: string;
  class_code: string;
  name_en: string;
  name_uz: string;
  is_active: boolean;
}

interface AccountCategory {
  id: number;
  code: string;
  group_code: string;
  name_en: string;
  name_uz: string;
  is_active: boolean;
}

interface Account {
  id: number;
  code: string;
  category_code: string;
  name_en: string;
  name_uz: string;
  is_budgetable: boolean;
  is_active: boolean;
}

interface BusinessUnit {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  unit_type: string;
  is_active: boolean;
}

export const COAPage = () => {
  const [activeTab, setActiveTab] = useState<'dimension' | 'accounts' | 'budgeting-groups'>('dimension');
  const [hierarchy, setHierarchy] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [budgetingGroups, setBudgetingGroups] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterBsClass, setFilterBsClass] = useState<string>('');
  const [filterBudgetingGroup, setFilterBudgetingGroup] = useState<string>('');
  
  const [expandedBsClasses, setExpandedBsClasses] = useState<Set<number>>(new Set());
  const [expandedBsGroups, setExpandedBsGroups] = useState<Set<string>>(new Set());
  const [expandedBudgetingGroups, setExpandedBudgetingGroups] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [hierarchyData, accountsData, groupsData, statsData] = await Promise.all([
        coaDimensionAPI.getHierarchy(),
        coaDimensionAPI.listAccounts({ limit: 1000 }),
        coaDimensionAPI.getBudgetingGroups(),
        coaDimensionAPI.getStats(),
      ]);
      setHierarchy(hierarchyData.hierarchy || []);
      setAccounts(accountsData.accounts || []);
      setBudgetingGroups(groupsData.groups || []);
      setStats(statsData);
      
      if (hierarchyData.hierarchy) {
        setExpandedBsClasses(new Set(hierarchyData.hierarchy.map((c: any) => c.bs_flag)));
      }
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load COA Dimension data');
    } finally {
      setLoading(false);
    }
  };

  const handleImportDimension = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await coaDimensionAPI.importFromUploads();
      setSuccess(`Imported COA Dimension: ${result.imported} accounts`);
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to import COA Dimension');
    } finally {
      setLoading(false);
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

  const toggleBsGroup = (key: string) => {
    const newExpanded = new Set(expandedBsGroups);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedBsGroups(newExpanded);
  };

  const toggleBudgetingGroup = (groupId: number) => {
    const newExpanded = new Set(expandedBudgetingGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedBudgetingGroups(newExpanded);
  };

  const filteredAccounts = accounts.filter(acc => {
    const matchesSearch = !searchTerm || 
      acc.coa_code?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      acc.coa_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesBsClass = !filterBsClass || acc.bs_flag?.toString() === filterBsClass;
    const matchesBudgetingGroup = !filterBudgetingGroup || acc.budgeting_groups?.toString() === filterBudgetingGroup;
    return matchesSearch && matchesBsClass && matchesBudgetingGroup;
  });

  const DimensionHierarchyView = () => (
    <div className="space-y-2">
      {hierarchy.map((bsClass) => (
        <div key={bsClass.bs_flag} className="border border-gray-200 rounded-lg overflow-hidden">
          {/* Level 1: BS Class */}
          <button
            onClick={() => toggleBsClass(bsClass.bs_flag)}
            className="w-full flex items-center gap-3 p-4 bg-gradient-to-r from-blue-50 to-white hover:from-blue-100 transition-colors"
          >
            {expandedBsClasses.has(bsClass.bs_flag) ? (
              <ChevronDown className="w-5 h-5 text-blue-600" />
            ) : (
              <ChevronRight className="w-5 h-5 text-blue-600" />
            )}
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">Level 1</span>
            <span className="font-bold text-gray-900 text-lg">{bsClass.bs_name}</span>
            <span className="text-gray-500">({bsClass.account_count} accounts)</span>
          </button>
          
          {expandedBsClasses.has(bsClass.bs_flag) && (
            <div className="border-t border-gray-200">
              {bsClass.bs_groups?.map((bsGroup: any) => {
                const groupKey = `${bsClass.bs_flag}-${bsGroup.bs_group}`;
                return (
                  <div key={groupKey} className="border-b border-gray-100 last:border-b-0">
                    {/* Level 2: BS Group */}
                    <button
                      onClick={() => toggleBsGroup(groupKey)}
                      className="w-full flex items-center gap-3 p-3 pl-10 hover:bg-gray-50 transition-colors"
                    >
                      {expandedBsGroups.has(groupKey) ? (
                        <ChevronDown className="w-4 h-4 text-gray-500" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-gray-500" />
                      )}
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">Level 2</span>
                      <span className="font-mono font-semibold text-gray-700">{bsGroup.bs_group}</span>
                      <span className="text-gray-800">{bsGroup.group_name}</span>
                      <span className="ml-auto text-sm text-gray-500">
                        {bsGroup.budgeting_groups?.length || 0} budgeting groups
                      </span>
                    </button>
                    
                    {expandedBsGroups.has(groupKey) && (
                      <div className="bg-gray-50">
                        {bsGroup.budgeting_groups?.map((budgetGroup: any) => (
                          <div key={budgetGroup.budgeting_group_id} className="border-t border-gray-100">
                            {/* Level 3: Budgeting Group */}
                            <button
                              onClick={() => toggleBudgetingGroup(budgetGroup.budgeting_group_id)}
                              className="w-full flex items-center gap-3 p-2 pl-16 hover:bg-gray-100 transition-colors"
                            >
                              {expandedBudgetingGroups.has(budgetGroup.budgeting_group_id) ? (
                                <ChevronDown className="w-4 h-4 text-gray-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              )}
                              <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">Level 3</span>
                              <span className="text-gray-700 font-medium">{budgetGroup.budgeting_group_name || 'Unassigned'}</span>
                              <span className="ml-auto text-xs text-gray-500">
                                {budgetGroup.accounts?.length || 0} accounts
                              </span>
                            </button>
                            
                            {expandedBudgetingGroups.has(budgetGroup.budgeting_group_id) && budgetGroup.accounts && (
                              <div className="bg-white py-1">
                                {/* Level 4: COA Accounts */}
                                {budgetGroup.accounts.map((acc: any) => (
                                  <div key={acc.coa_code} className="flex items-center gap-3 py-1.5 pl-24 pr-4 hover:bg-blue-50/30">
                                    <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">Level 4</span>
                                    <span className="font-mono text-sm text-blue-600 font-medium">{acc.coa_code}</span>
                                    <span className="text-gray-700 text-sm truncate">{acc.coa_name}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
      {hierarchy.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No COA Dimension data. Click "Import from Excel" to load data.
        </div>
      )}
    </div>
  );

  const AccountsTable = () => (
    <div>
      {/* Filters */}
      <div className="flex gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search by code or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <select
          value={filterBsClass}
          onChange={(e) => setFilterBsClass(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All BS Classes</option>
          <option value="1">Assets</option>
          <option value="2">Liabilities</option>
          <option value="3">Capital</option>
          <option value="9">Off-balance</option>
        </select>
        <select
          value={filterBudgetingGroup}
          onChange={(e) => setFilterBudgetingGroup(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Budgeting Groups</option>
          {budgetingGroups.map(g => (
            <option key={g.group_id} value={g.group_id}>{g.group_name}</option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              <th className="text-left p-3 font-semibold text-gray-700">COA Code</th>
              <th className="text-left p-3 font-semibold text-gray-700">Account Name</th>
              <th className="text-left p-3 font-semibold text-gray-700">BS Class</th>
              <th className="text-left p-3 font-semibold text-gray-700">BS Group</th>
              <th className="text-left p-3 font-semibold text-gray-700">Budgeting Group</th>
              <th className="text-center p-3 font-semibold text-gray-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredAccounts.slice(0, 100).map((acc) => (
              <tr key={acc.id} className="border-b border-gray-100 hover:bg-blue-50/30">
                <td className="p-3 font-mono font-medium text-blue-600">{acc.coa_code}</td>
                <td className="p-3 text-gray-900">{acc.coa_name}</td>
                <td className="p-3 text-gray-600">{acc.bs_name}</td>
                <td className="p-3 text-gray-600">{acc.bs_group} - {acc.group_name}</td>
                <td className="p-3">
                  {acc.budgeting_groups_name ? (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      {acc.budgeting_groups_name}
                    </span>
                  ) : (
                    <span className="text-gray-400 text-xs">Not assigned</span>
                  )}
                </td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    acc.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {acc.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredAccounts.length > 100 && (
          <p className="p-4 text-center text-gray-500">Showing first 100 of {filteredAccounts.length} accounts</p>
        )}
        {filteredAccounts.length === 0 && (
          <p className="p-8 text-center text-gray-500">No accounts match your filters</p>
        )}
      </div>
    </div>
  );

  const BudgetingGroupsView = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {budgetingGroups.map((group) => (
        <div key={group.group_id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between mb-2">
            <div>
              <h3 className="font-semibold text-gray-900">{group.group_name}</h3>
              <p className="text-sm text-gray-500">ID: {group.group_id}</p>
            </div>
            <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
              {group.account_count} accounts
            </span>
          </div>
          <div className="text-sm text-gray-600 mt-2">
            <div>BS Class: {group.bs_name || 'Mixed'}</div>
            <div>Category: {group.category || 'N/A'}</div>
          </div>
        </div>
      ))}
      {budgetingGroups.length === 0 && (
        <div className="col-span-full text-center py-8 text-gray-500">
          No budgeting groups found. Import COA Dimension data first.
        </div>
      )}
    </div>
  );

  if (loading && hierarchy.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Chart of Accounts & Hierarchy"
        subtitle="COA Dimension with 4-level hierarchy: BS Class → BS Group → Budgeting Group → COA Account"
        actions={
          <div className="flex gap-2">
            <button
              onClick={handleImportDimension}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              <Database className="w-4 h-4" />
              Import from Excel
            </button>
            <button
              onClick={fetchData}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        }
      />

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="bg-white border rounded-lg p-4">
            <div className="text-sm text-gray-500">Total Accounts</div>
            <div className="text-2xl font-bold text-blue-600">{stats.total_accounts}</div>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <div className="text-sm text-gray-500">Active Accounts</div>
            <div className="text-2xl font-bold text-green-600">{stats.active_accounts}</div>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <div className="text-sm text-gray-500">BS Groups</div>
            <div className="text-2xl font-bold text-purple-600">{stats.bs_groups}</div>
          </div>
          <div className="bg-white border rounded-lg p-4">
            <div className="text-sm text-gray-500">Budgeting Groups</div>
            <div className="text-2xl font-bold text-amber-600">{stats.budgeting_groups}</div>
          </div>
        </div>
      )}

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'dimension'} onClick={() => setActiveTab('dimension')}>
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4" />
              4-Level Hierarchy
            </div>
          </TabButton>
          <TabButton active={activeTab === 'accounts'} onClick={() => setActiveTab('accounts')}>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Accounts ({accounts.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'budgeting-groups'} onClick={() => setActiveTab('budgeting-groups')}>
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              Budgeting Groups ({budgetingGroups.length})
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'dimension' && <DimensionHierarchyView />}
          {activeTab === 'accounts' && <AccountsTable />}
          {activeTab === 'budgeting-groups' && <BudgetingGroupsView />}
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Currencies Page
// ============================================

interface Currency {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
  is_base_currency: boolean;
}

interface FXRate {
  id: number;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: number;
  rate_source: string;
}

export const CurrenciesPage = () => {
  const [activeTab, setActiveTab] = useState<'currencies' | 'rates' | 'budget-rates'>('currencies');
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [rates, setRates] = useState<FXRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [convertAmount, setConvertAmount] = useState<string>('1000');
  const [convertFrom, setConvertFrom] = useState<string>('USD');
  const [convertTo, setConvertTo] = useState<string>('UZS');
  const [convertResult, setConvertResult] = useState<{ converted_amount: number; rate_used: number } | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [currenciesData, ratesData] = await Promise.all([
        currenciesAPI.list(),
        currenciesAPI.listRates({ limit: 50 }),
      ]);
      setCurrencies(currenciesData);
      setRates(ratesData);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load currencies');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedCurrencies = async () => {
    try {
      setLoading(true);
      await currenciesAPI.seed();
      setSuccess('Default currencies seeded successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed currencies');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedRates = async () => {
    try {
      setLoading(true);
      await currenciesAPI.seedRates();
      setSuccess('Sample FX rates seeded successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed rates');
    } finally {
      setLoading(false);
    }
  };

  const handleConvert = async () => {
    try {
      const result = await currenciesAPI.convert({
        amount: parseFloat(convertAmount),
        from_currency: convertFrom,
        to_currency: convertTo,
      });
      setConvertResult(result);
    } catch (err: unknown) {
      setError((err as Error).message || 'Conversion failed');
    }
  };

  const CurrenciesTable = () => (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={handleSeedCurrencies}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Database className="w-4 h-4" />
          Seed Default Currencies
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Code</th>
              <th className="text-left p-4 font-semibold text-gray-700">Symbol</th>
              <th className="text-left p-4 font-semibold text-gray-700">Name (EN)</th>
              <th className="text-left p-4 font-semibold text-gray-700">Name (UZ)</th>
              <th className="text-center p-4 font-semibold text-gray-700">Decimals</th>
              <th className="text-center p-4 font-semibold text-gray-700">Base</th>
              <th className="text-center p-4 font-semibold text-gray-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {currencies.map((currency) => (
              <tr key={currency.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-mono font-bold text-primary-600">{currency.code}</td>
                <td className="p-4 text-xl">{currency.symbol}</td>
                <td className="p-4 text-gray-900">{currency.name_en}</td>
                <td className="p-4 text-gray-600">{currency.name_uz}</td>
                <td className="p-4 text-center text-gray-600">{currency.decimal_places}</td>
                <td className="p-4 text-center">
                  {currency.is_base_currency && (
                    <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">BASE</span>
                  )}
                </td>
                <td className="p-4 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    currency.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {currency.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const RatesView = () => (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
          <input
            type="number"
            value={convertAmount}
            onChange={(e) => setConvertAmount(e.target.value)}
            className="w-32 px-3 py-2 border border-gray-300 rounded-lg"
            placeholder="Amount"
          />
          <select
            value={convertFrom}
            onChange={(e) => setConvertFrom(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            {currencies.map((c) => (
              <option key={c.code} value={c.code}>{c.code}</option>
            ))}
          </select>
          <ArrowRightLeft className="w-5 h-5 text-gray-400" />
          <select
            value={convertTo}
            onChange={(e) => setConvertTo(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            {currencies.map((c) => (
              <option key={c.code} value={c.code}>{c.code}</option>
            ))}
          </select>
          <button
            onClick={handleConvert}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Convert
          </button>
          {convertResult && (
            <div className="text-lg font-semibold text-green-600">
              = {convertResult.converted_amount.toLocaleString()} {convertTo}
              <span className="text-sm text-gray-500 ml-2">(Rate: {convertResult.rate_used})</span>
            </div>
          )}
        </div>
        <button
          onClick={handleSeedRates}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Database className="w-4 h-4" />
          Seed Sample Rates
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Date</th>
              <th className="text-left p-4 font-semibold text-gray-700">From</th>
              <th className="text-left p-4 font-semibold text-gray-700">To</th>
              <th className="text-right p-4 font-semibold text-gray-700">Rate</th>
              <th className="text-left p-4 font-semibold text-gray-700">Source</th>
            </tr>
          </thead>
          <tbody>
            {rates.map((rate) => (
              <tr key={rate.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 text-gray-600">{rate.rate_date}</td>
                <td className="p-4 font-mono font-medium text-primary-600">{rate.from_currency}</td>
                <td className="p-4 font-mono text-gray-600">{rate.to_currency}</td>
                <td className="p-4 text-right font-mono font-semibold">{parseFloat(String(rate.rate)).toLocaleString()}</td>
                <td className="p-4 text-gray-500">{rate.rate_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  if (loading && currencies.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Currencies & FX Rates"
        subtitle="Manage currencies and exchange rates"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        }
      />

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'currencies'} onClick={() => setActiveTab('currencies')}>
            <div className="flex items-center gap-2">
              <Banknote className="w-4 h-4" />
              Currencies ({currencies.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'rates'} onClick={() => setActiveTab('rates')}>
            <div className="flex items-center gap-2">
              <ArrowRightLeft className="w-4 h-4" />
              FX Rates ({rates.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'budget-rates'} onClick={() => setActiveTab('budget-rates')}>
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4" />
              Budget Rates
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'currencies' && <CurrenciesTable />}
          {activeTab === 'rates' && <RatesView />}
          {activeTab === 'budget-rates' && (
            <div className="text-center py-8 text-gray-500">
              Budget FX rates planning coming soon...
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Drivers Page
// ============================================

interface Driver {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  driver_type: string;
  scope: string;
  source_account_pattern: string | null;
  target_account_pattern: string | null;
  default_value: number | null;
  unit: string;
  is_active: boolean;
  is_system: boolean;
}

interface GoldenRule {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  rule_type: string;
  source_account_pattern: string;
  target_account_pattern: string;
  calculation_formula: string;
  priority: number;
  is_active: boolean;
}

export const DriversPage = () => {
  const [activeTab, setActiveTab] = useState<'drivers' | 'golden-rules' | 'calculations'>('drivers');
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [goldenRules, setGoldenRules] = useState<GoldenRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [driversData, rulesData] = await Promise.all([
        driversAPI.list(),
        driversAPI.listGoldenRules(),
      ]);
      setDrivers(driversData);
      setGoldenRules(rulesData);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load drivers');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedDrivers = async () => {
    try {
      setLoading(true);
      await driversAPI.seed();
      setSuccess('Default drivers seeded successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed drivers');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedGoldenRules = async () => {
    try {
      setLoading(true);
      await driversAPI.seedGoldenRules();
      setSuccess('Golden rules seeded successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed golden rules');
    } finally {
      setLoading(false);
    }
  };

  const getDriverTypeColor = (type: string) => {
    switch (type) {
      case 'yield_rate': return 'bg-green-100 text-green-700';
      case 'cost_rate': return 'bg-red-100 text-red-700';
      case 'growth_rate': return 'bg-blue-100 text-blue-700';
      case 'provision_rate': return 'bg-yellow-100 text-yellow-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const DriversTable = () => (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={handleSeedDrivers}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Database className="w-4 h-4" />
          Seed Default Drivers
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Code</th>
              <th className="text-left p-4 font-semibold text-gray-700">Name</th>
              <th className="text-left p-4 font-semibold text-gray-700">Type</th>
              <th className="text-left p-4 font-semibold text-gray-700">Source → Target</th>
              <th className="text-right p-4 font-semibold text-gray-700">Default</th>
              <th className="text-center p-4 font-semibold text-gray-700">System</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => (
              <tr key={driver.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-mono font-medium text-primary-600">{driver.code}</td>
                <td className="p-4">
                  <div className="text-gray-900">{driver.name_en}</div>
                  <div className="text-gray-500 text-sm">{driver.name_uz}</div>
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getDriverTypeColor(driver.driver_type)}`}>
                    {driver.driver_type.replace('_', ' ')}
                  </span>
                </td>
                <td className="p-4 font-mono text-sm text-gray-600">
                  {driver.source_account_pattern || '-'} → {driver.target_account_pattern || '-'}
                </td>
                <td className="p-4 text-right font-mono">
                  {driver.default_value != null ? `${driver.default_value}${driver.unit}` : '-'}
                </td>
                <td className="p-4 text-center">
                  {driver.is_system && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">SYSTEM</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const GoldenRulesTable = () => (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={handleSeedGoldenRules}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Database className="w-4 h-4" />
          Seed Golden Rules
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Code</th>
              <th className="text-left p-4 font-semibold text-gray-700">Name</th>
              <th className="text-left p-4 font-semibold text-gray-700">Type</th>
              <th className="text-left p-4 font-semibold text-gray-700">Source → Target</th>
              <th className="text-left p-4 font-semibold text-gray-700">Formula</th>
              <th className="text-center p-4 font-semibold text-gray-700">Priority</th>
            </tr>
          </thead>
          <tbody>
            {goldenRules.map((rule) => (
              <tr key={rule.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-mono font-medium text-primary-600">{rule.code}</td>
                <td className="p-4">
                  <div className="text-gray-900">{rule.name_en}</div>
                  <div className="text-gray-500 text-sm">{rule.name_uz}</div>
                </td>
                <td className="p-4">
                  <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                    {rule.rule_type.replace('_', ' ')}
                  </span>
                </td>
                <td className="p-4 font-mono text-sm text-gray-600">
                  {rule.source_account_pattern} → {rule.target_account_pattern}
                </td>
                <td className="p-4 font-mono text-sm text-gray-600">{rule.calculation_formula}</td>
                <td className="p-4 text-center font-semibold text-gray-600">{rule.priority}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  if (loading && drivers.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Drivers & Golden Rules"
        subtitle="Manage calculation drivers and automatic P&L rules"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        }
      />

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'drivers'} onClick={() => setActiveTab('drivers')}>
            <div className="flex items-center gap-2">
              <Calculator className="w-4 h-4" />
              Drivers ({drivers.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'golden-rules'} onClick={() => setActiveTab('golden-rules')}>
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Golden Rules ({goldenRules.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'calculations'} onClick={() => setActiveTab('calculations')}>
            <div className="flex items-center gap-2">
              <Play className="w-4 h-4" />
              Run Calculations
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'drivers' && <DriversTable />}
          {activeTab === 'golden-rules' && <GoldenRulesTable />}
          {activeTab === 'calculations' && (
            <div className="text-center py-8 text-gray-500">
              Driver calculations interface coming soon...
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

// ============================================
// Templates Page
// ============================================

interface BudgetTemplate {
  id: number;
  code: string;
  name_en: string;
  name_uz: string;
  template_type: string;
  status: string;
  fiscal_year: number | null;
  include_baseline: boolean;
  include_prior_year: boolean;
  include_variance: boolean;
  is_active: boolean;
}

interface TemplateSection {
  id: number;
  template_id: number;
  code: string;
  name_en: string;
  name_uz: string;
  account_pattern: string | null;
  is_editable: boolean;
  is_required: boolean;
  display_order: number;
}

interface TemplateAssignment {
  id: number;
  template_id: number;
  business_unit_id: number;
  fiscal_year: number;
  status: string;
  deadline: string | null;
  template?: BudgetTemplate;
  business_unit?: BusinessUnit;
}

export const TemplatesPage = () => {
  const [activeTab, setActiveTab] = useState<'templates' | 'sections' | 'assignments'>('templates');
  const [templates, setTemplates] = useState<BudgetTemplate[]>([]);
  const [sections, setSections] = useState<TemplateSection[]>([]);
  const [assignments, setAssignments] = useState<TemplateAssignment[]>([]);
  const [businessUnits, setBusinessUnits] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Assignment modal state
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assignForm, setAssignForm] = useState({
    template_id: 0,
    business_unit_id: 0,
    department_id: 0,
    fiscal_year: new Date().getFullYear() + 1,
    deadline: '',
  });
  const [assignSaving, setAssignSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [templatesData, sectionsData, assignmentsData, buData, deptData] = await Promise.all([
        templatesAPI.list(),
        templatesAPI.listSections(),
        templatesAPI.listAssignments(),
        coaAPI.listBusinessUnits().catch(() => []),
        departmentAPI.list().catch(() => ({ departments: [] })),
      ]);
      setTemplates(templatesData);
      setSections(sectionsData);
      setAssignments(assignmentsData);
      setBusinessUnits(buData || []);
      setDepartments(deptData.departments || deptData || []);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };
  
  const handleCreateAssignment = async () => {
    if (!assignForm.template_id || (!assignForm.business_unit_id && !assignForm.department_id)) {
      setError('Please select a template and either a business unit or department');
      return;
    }
    
    try {
      setAssignSaving(true);
      setError(null);
      await templatesAPI.createAssignment({
        template_id: assignForm.template_id,
        business_unit_id: assignForm.business_unit_id || undefined,
        department_id: assignForm.department_id || undefined,
        fiscal_year: assignForm.fiscal_year,
        deadline: assignForm.deadline || undefined,
      });
      setSuccess('Template assigned successfully');
      setShowAssignModal(false);
      setAssignForm({
        template_id: 0,
        business_unit_id: 0,
        department_id: 0,
        fiscal_year: new Date().getFullYear() + 1,
        deadline: '',
      });
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to create assignment');
    } finally {
      setAssignSaving(false);
    }
  };
  
  const handleDeleteAssignment = async (assignmentId: number) => {
    if (!confirm('Are you sure you want to delete this assignment?')) return;
    
    try {
      setLoading(true);
      await templatesAPI.deleteAssignment(assignmentId);
      setSuccess('Assignment deleted successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to delete assignment');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedTemplates = async () => {
    try {
      setLoading(true);
      await templatesAPI.seed();
      setSuccess('Default templates seeded successfully');
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed templates');
    } finally {
      setLoading(false);
    }
  };

  const getTemplateTypeColor = (type: string) => {
    switch (type) {
      case 'revenue': return 'bg-green-100 text-green-700';
      case 'expense': return 'bg-red-100 text-red-700';
      case 'balance_sheet': return 'bg-blue-100 text-blue-700';
      case 'standard': return 'bg-purple-100 text-purple-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-700';
      case 'draft': return 'bg-yellow-100 text-yellow-700';
      case 'archived': return 'bg-gray-100 text-gray-600';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const TemplatesTable = () => (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={handleSeedTemplates}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Database className="w-4 h-4" />
          Seed Default Templates
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Code</th>
              <th className="text-left p-4 font-semibold text-gray-700">Name</th>
              <th className="text-left p-4 font-semibold text-gray-700">Type</th>
              <th className="text-center p-4 font-semibold text-gray-700">Year</th>
              <th className="text-center p-4 font-semibold text-gray-700">Features</th>
              <th className="text-center p-4 font-semibold text-gray-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((template) => (
              <tr key={template.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-mono font-medium text-primary-600">{template.code}</td>
                <td className="p-4">
                  <div className="text-gray-900">{template.name_en}</div>
                  <div className="text-gray-500 text-sm">{template.name_uz}</div>
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getTemplateTypeColor(template.template_type)}`}>
                    {template.template_type.replace('_', ' ')}
                  </span>
                </td>
                <td className="p-4 text-center text-gray-600">{template.fiscal_year || '-'}</td>
                <td className="p-4">
                  <div className="flex gap-1 justify-center">
                    {template.include_baseline && (
                      <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">Baseline</span>
                    )}
                    {template.include_prior_year && (
                      <span className="px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded text-xs">Prior</span>
                    )}
                    {template.include_variance && (
                      <span className="px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded text-xs">Variance</span>
                    )}
                  </div>
                </td>
                <td className="p-4 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(template.status)}`}>
                    {template.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const SectionsTable = () => (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left p-4 font-semibold text-gray-700">Code</th>
            <th className="text-left p-4 font-semibold text-gray-700">Name</th>
            <th className="text-left p-4 font-semibold text-gray-700">Template</th>
            <th className="text-left p-4 font-semibold text-gray-700">Account Pattern</th>
            <th className="text-center p-4 font-semibold text-gray-700">Editable</th>
            <th className="text-center p-4 font-semibold text-gray-700">Required</th>
            <th className="text-center p-4 font-semibold text-gray-700">Order</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((section) => (
            <tr key={section.id} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="p-4 font-mono font-medium text-primary-600">{section.code}</td>
              <td className="p-4">
                <div className="text-gray-900">{section.name_en}</div>
                <div className="text-gray-500 text-sm">{section.name_uz}</div>
              </td>
              <td className="p-4 text-gray-600">
                {templates.find(t => t.id === section.template_id)?.code || section.template_id}
              </td>
              <td className="p-4 font-mono text-sm text-gray-600">{section.account_pattern || '-'}</td>
              <td className="p-4 text-center">
                {section.is_editable ? (
                  <Check className="w-5 h-5 text-green-600 mx-auto" />
                ) : (
                  <X className="w-5 h-5 text-gray-400 mx-auto" />
                )}
              </td>
              <td className="p-4 text-center">
                {section.is_required ? (
                  <Check className="w-5 h-5 text-green-600 mx-auto" />
                ) : (
                  <X className="w-5 h-5 text-gray-400 mx-auto" />
                )}
              </td>
              <td className="p-4 text-center text-gray-600">{section.display_order}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const AssignmentsTable = () => (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowAssignModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          Assign Template
        </button>
      </div>
      <div className="overflow-x-auto">
        {assignments.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <ClipboardList className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No template assignments yet</p>
            <p className="text-sm mt-2">Click "Assign Template" to assign templates to departments or business units</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left p-4 font-semibold text-gray-700">Template</th>
                <th className="text-left p-4 font-semibold text-gray-700">Assigned To</th>
                <th className="text-center p-4 font-semibold text-gray-700">Fiscal Year</th>
                <th className="text-left p-4 font-semibold text-gray-700">Deadline</th>
                <th className="text-center p-4 font-semibold text-gray-700">Status</th>
                <th className="text-center p-4 font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment: any) => (
                <tr key={assignment.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="p-4">
                    <div className="font-medium text-gray-900">
                      {assignment.template_name || assignment.template?.name_en || `Template #${assignment.template_id}`}
                    </div>
                    <div className="text-xs text-gray-500">{assignment.template_code}</div>
                  </td>
                  <td className="p-4">
                    <div className="text-gray-900 font-medium">
                      {assignment.business_unit_name || assignment.department_name || 
                       assignment.business_unit?.name_en || assignment.department?.name_en || 
                       (assignment.business_unit_id ? `Business Unit #${assignment.business_unit_id}` : 
                        assignment.department_id ? `Department #${assignment.department_id}` : 'Not assigned')}
                    </div>
                    {assignment.business_unit_code && (
                      <div className="text-xs text-gray-500">Code: {assignment.business_unit_code}</div>
                    )}
                  </td>
                  <td className="p-4 text-center">
                    <span className="font-semibold text-lg">{assignment.fiscal_year}</span>
                  </td>
                  <td className="p-4">
                    {assignment.deadline ? (
                      <div className="flex items-center gap-2 text-gray-600">
                        <Calendar className="w-4 h-4" />
                        {new Date(assignment.deadline).toLocaleDateString()}
                      </div>
                    ) : (
                      <span className="text-gray-400">No deadline</span>
                    )}
                  </td>
                  <td className="p-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(assignment.status)}`}>
                      {assignment.status?.replace('_', ' ').toUpperCase() || 'PENDING'}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button 
                        onClick={() => handleDeleteAssignment(assignment.id)}
                        className="text-red-600 hover:text-red-700 p-1"
                        title="Delete assignment"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );

  if (loading && templates.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Budget Templates"
        subtitle="Manage budget templates and assignments"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        }
      />

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'templates'} onClick={() => setActiveTab('templates')}>
            <div className="flex items-center gap-2">
              <LayoutTemplate className="w-4 h-4" />
              Templates ({templates.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'sections'} onClick={() => setActiveTab('sections')}>
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4" />
              Sections ({sections.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'assignments'} onClick={() => setActiveTab('assignments')}>
            <div className="flex items-center gap-2">
              <ClipboardList className="w-4 h-4" />
              Assignments ({assignments.length})
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'templates' && <TemplatesTable />}
          {activeTab === 'sections' && <SectionsTable />}
          {activeTab === 'assignments' && <AssignmentsTable />}
        </div>
      </Card>
      
      {/* Assignment Modal */}
      {showAssignModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b">
              <h3 className="text-lg font-semibold">Assign Template</h3>
              <p className="text-sm text-gray-500">Assign a budget template to a department or business unit</p>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Template <span className="text-red-500">*</span>
                </label>
                <select
                  value={assignForm.template_id}
                  onChange={(e) => setAssignForm({ ...assignForm, template_id: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value={0}>Select a template...</option>
                  {templates.filter(t => t.status === 'active').map((t) => (
                    <option key={t.id} value={t.id}>{t.name_en} ({t.code})</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Department
                </label>
                <select
                  value={assignForm.department_id}
                  onChange={(e) => setAssignForm({ ...assignForm, department_id: parseInt(e.target.value), business_unit_id: 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value={0}>Select a department...</option>
                  {departments.map((d: any) => (
                    <option key={d.id} value={d.id}>{d.name_en} ({d.code})</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Unit (optional)
                </label>
                <select
                  value={assignForm.business_unit_id}
                  onChange={(e) => setAssignForm({ ...assignForm, business_unit_id: parseInt(e.target.value), department_id: 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value={0}>Select a business unit...</option>
                  {businessUnits.map((bu: any) => (
                    <option key={bu.id} value={bu.id}>{bu.name_en} ({bu.code})</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Fiscal Year <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  value={assignForm.fiscal_year}
                  onChange={(e) => setAssignForm({ ...assignForm, fiscal_year: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Deadline
                </label>
                <input
                  type="date"
                  value={assignForm.deadline}
                  onChange={(e) => setAssignForm({ ...assignForm, deadline: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t bg-gray-50">
              <button
                onClick={() => {
                  setShowAssignModal(false);
                  setAssignForm({
                    template_id: 0,
                    business_unit_id: 0,
                    department_id: 0,
                    fiscal_year: new Date().getFullYear() + 1,
                    deadline: '',
                  });
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateAssignment}
                disabled={assignSaving || !assignForm.template_id}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {assignSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Assign Template
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================
// Snapshots & Baselines Page
// ============================================

interface Snapshot {
  id: number;
  snapshot_date: string;
  account_code: string;
  currency: string;
  balance: number;
  balance_uzs: number;
  fx_rate: number;
  data_source: string | null;
  is_validated: boolean;
}

interface Baseline {
  id: number;
  fiscal_year: number;
  account_code: string;
  currency: string;
  jan: number;
  feb: number;
  mar: number;
  apr: number;
  may: number;
  jun: number;
  jul: number;
  aug: number;
  sep: number;
  oct: number;
  nov: number;
  dec: number;
  annual_total: number;
  calculation_method: string;
  is_active: boolean;
}

export const SnapshotsPage = () => {
  const [activeTab, setActiveTab] = useState<'snapshots' | 'baselines'>('snapshots');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [fiscalYear, setFiscalYear] = useState<number>(new Date().getFullYear());

  useEffect(() => {
    fetchData();
  }, [fiscalYear]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [snapshotsData, baselinesData] = await Promise.all([
        snapshotsAPI.list({ limit: 100 }),
        snapshotsAPI.listBaselines({ fiscal_year: fiscalYear }).catch(() => []),
      ]);
      setSnapshots(snapshotsData);
      setBaselines(baselinesData);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCalculateBaselines = async () => {
    try {
      setLoading(true);
      const result = await snapshotsAPI.calculateBaselines({
        fiscal_year: fiscalYear,
        method: 'average',
        apply_trend: true,
      });
      setSuccess(`Calculated ${result.baselines_created} baselines for ${fiscalYear}`);
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to calculate baselines');
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
    return num.toFixed(0);
  };

  const SnapshotsTable = () => (
    <div className="overflow-x-auto">
      {snapshots.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Database className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>No snapshots imported yet</p>
          <p className="text-sm mt-2">Import historical balance data from DWH to create baselines</p>
        </div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Date</th>
              <th className="text-left p-4 font-semibold text-gray-700">Account</th>
              <th className="text-left p-4 font-semibold text-gray-700">Currency</th>
              <th className="text-right p-4 font-semibold text-gray-700">Balance</th>
              <th className="text-right p-4 font-semibold text-gray-700">Balance (UZS)</th>
              <th className="text-left p-4 font-semibold text-gray-700">Source</th>
              <th className="text-center p-4 font-semibold text-gray-700">Validated</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((snapshot) => (
              <tr key={snapshot.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 text-gray-600">{snapshot.snapshot_date}</td>
                <td className="p-4 font-mono font-medium text-primary-600">{snapshot.account_code}</td>
                <td className="p-4 font-mono text-gray-600">{snapshot.currency}</td>
                <td className="p-4 text-right font-mono">{formatNumber(snapshot.balance)}</td>
                <td className="p-4 text-right font-mono text-gray-600">{formatNumber(snapshot.balance_uzs)}</td>
                <td className="p-4 text-gray-500">{snapshot.data_source || '-'}</td>
                <td className="p-4 text-center">
                  {snapshot.is_validated ? (
                    <Check className="w-5 h-5 text-green-600 mx-auto" />
                  ) : (
                    <Clock className="w-5 h-5 text-yellow-500 mx-auto" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  const BaselinesTable = () => (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-4">
          <label className="text-gray-700 font-medium">Fiscal Year:</label>
          <select
            value={fiscalYear}
            onChange={(e) => setFiscalYear(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            {[2024, 2025, 2026, 2027].map((year) => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleCalculateBaselines}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          <Calculator className="w-4 h-4" />
          Calculate Baselines
        </button>
      </div>

      {baselines.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>No baselines calculated for {fiscalYear}</p>
          <p className="text-sm mt-2">Import snapshots first, then calculate baselines</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left p-3 font-semibold text-gray-700">Account</th>
                <th className="text-right p-3 font-semibold text-gray-700">Jan</th>
                <th className="text-right p-3 font-semibold text-gray-700">Feb</th>
                <th className="text-right p-3 font-semibold text-gray-700">Mar</th>
                <th className="text-right p-3 font-semibold text-gray-700">Apr</th>
                <th className="text-right p-3 font-semibold text-gray-700">May</th>
                <th className="text-right p-3 font-semibold text-gray-700">Jun</th>
                <th className="text-right p-3 font-semibold text-gray-700">Jul</th>
                <th className="text-right p-3 font-semibold text-gray-700">Aug</th>
                <th className="text-right p-3 font-semibold text-gray-700">Sep</th>
                <th className="text-right p-3 font-semibold text-gray-700">Oct</th>
                <th className="text-right p-3 font-semibold text-gray-700">Nov</th>
                <th className="text-right p-3 font-semibold text-gray-700">Dec</th>
                <th className="text-right p-3 font-semibold text-gray-700 bg-gray-100">Total</th>
              </tr>
            </thead>
            <tbody>
              {baselines.map((baseline) => (
                <tr key={baseline.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="p-3 font-mono font-medium text-primary-600">{baseline.account_code}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.jan)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.feb)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.mar)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.apr)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.may)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.jun)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.jul)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.aug)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.sep)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.oct)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.nov)}</td>
                  <td className="p-3 text-right font-mono">{formatNumber(baseline.dec)}</td>
                  <td className="p-3 text-right font-mono font-semibold bg-gray-50">{formatNumber(baseline.annual_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  if (loading && snapshots.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Snapshots & Baselines"
        subtitle="Historical data and baseline budget calculations"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        }
      />

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'snapshots'} onClick={() => setActiveTab('snapshots')}>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Snapshots ({snapshots.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'baselines'} onClick={() => setActiveTab('baselines')}>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Baselines ({baselines.length})
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'snapshots' && <SnapshotsTable />}
          {activeTab === 'baselines' && <BaselinesTable />}
        </div>
      </Card>
    </div>
  );
};

export default {
  COAPage,
  CurrenciesPage,
  DriversPage,
  TemplatesPage,
  SnapshotsPage,
};
