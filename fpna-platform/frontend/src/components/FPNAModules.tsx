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
  currenciesAPI,
  driversAPI,
  templatesAPI,
  snapshotsAPI,
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
  const [activeTab, setActiveTab] = useState<'hierarchy' | 'accounts' | 'business-units'>('hierarchy');
  const [classes, setClasses] = useState<AccountClass[]>([]);
  const [groups, setGroups] = useState<AccountGroup[]>([]);
  const [categories, setCategories] = useState<AccountCategory[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [businessUnits, setBusinessUnits] = useState<BusinessUnit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [classesData, groupsData, categoriesData, accountsData, buData] = await Promise.all([
        coaAPI.listClasses(),
        coaAPI.listGroups(),
        coaAPI.listCategories(),
        coaAPI.listAccounts({ limit: 1000 }),
        coaAPI.listBusinessUnits(),
      ]);
      setClasses(classesData);
      setGroups(groupsData);
      setCategories(categoriesData);
      setAccounts(accountsData);
      setBusinessUnits(buData);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load COA data');
    } finally {
      setLoading(false);
    }
  };

  const handleSeedCOA = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await coaAPI.seed();
      setSuccess(`Seeded COA: ${result.classes} classes, ${result.groups} groups, ${result.categories} categories, ${result.accounts} accounts, ${result.business_units} business units`);
      await fetchData();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to seed COA data');
    } finally {
      setLoading(false);
    }
  };

  const toggleClass = (code: string) => {
    const newExpanded = new Set(expandedClasses);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedClasses(newExpanded);
  };

  const toggleGroup = (code: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedGroups(newExpanded);
  };

  const HierarchyView = () => (
    <div className="space-y-2">
      {classes.map((cls) => (
        <div key={cls.id} className="border border-gray-200 rounded-lg overflow-hidden">
          <button
            onClick={() => toggleClass(cls.code)}
            className="w-full flex items-center gap-3 p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            {expandedClasses.has(cls.code) ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
            <span className="font-mono text-lg font-bold text-primary-600">{cls.code}</span>
            <span className="font-semibold text-gray-900">{cls.name_en}</span>
            <span className="text-gray-500 text-sm">({cls.name_uz})</span>
            <span className={`ml-auto px-2 py-1 rounded text-xs font-medium ${
              cls.nature === 'debit' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
            }`}>
              {cls.nature}
            </span>
          </button>
          
          {expandedClasses.has(cls.code) && (
            <div className="border-t border-gray-200">
              {groups.filter(g => g.class_code === cls.code).map((group) => (
                <div key={group.id} className="border-b border-gray-100 last:border-b-0">
                  <button
                    onClick={() => toggleGroup(group.code)}
                    className="w-full flex items-center gap-3 p-3 pl-10 hover:bg-gray-50 transition-colors"
                  >
                    {expandedGroups.has(group.code) ? (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    )}
                    <span className="font-mono font-medium text-gray-700">{group.code}</span>
                    <span className="text-gray-800">{group.name_en}</span>
                    <span className="text-gray-500 text-sm">({group.name_uz})</span>
                  </button>
                  
                  {expandedGroups.has(group.code) && (
                    <div className="bg-gray-50 py-2">
                      {categories.filter(c => c.group_code === group.code).map((cat) => (
                        <div key={cat.id} className="flex items-center gap-3 py-2 pl-20 pr-4">
                          <span className="font-mono text-sm text-gray-600">{cat.code}</span>
                          <span className="text-gray-700">{cat.name_en}</span>
                          <span className="text-gray-500 text-sm">({cat.name_uz})</span>
                          <span className="ml-auto text-xs text-gray-400">
                            {accounts.filter(a => a.category_code === cat.code).length} accounts
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );

  const AccountsTable = () => (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left p-4 font-semibold text-gray-700">Code</th>
            <th className="text-left p-4 font-semibold text-gray-700">Name (EN)</th>
            <th className="text-left p-4 font-semibold text-gray-700">Name (UZ)</th>
            <th className="text-left p-4 font-semibold text-gray-700">Category</th>
            <th className="text-center p-4 font-semibold text-gray-700">Budgetable</th>
            <th className="text-center p-4 font-semibold text-gray-700">Status</th>
          </tr>
        </thead>
        <tbody>
          {accounts.slice(0, 100).map((account) => (
            <tr key={account.id} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="p-4 font-mono font-medium text-primary-600">{account.code}</td>
              <td className="p-4 text-gray-900">{account.name_en}</td>
              <td className="p-4 text-gray-600">{account.name_uz}</td>
              <td className="p-4 text-gray-600">{account.category_code}</td>
              <td className="p-4 text-center">
                {account.is_budgetable ? (
                  <Check className="w-5 h-5 text-green-600 mx-auto" />
                ) : (
                  <X className="w-5 h-5 text-gray-400 mx-auto" />
                )}
              </td>
              <td className="p-4 text-center">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  account.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  {account.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {accounts.length > 100 && (
        <p className="p-4 text-center text-gray-500">Showing first 100 of {accounts.length} accounts</p>
      )}
    </div>
  );

  const BusinessUnitsTable = () => (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left p-4 font-semibold text-gray-700">Code</th>
            <th className="text-left p-4 font-semibold text-gray-700">Name (EN)</th>
            <th className="text-left p-4 font-semibold text-gray-700">Name (UZ)</th>
            <th className="text-left p-4 font-semibold text-gray-700">Type</th>
            <th className="text-center p-4 font-semibold text-gray-700">Status</th>
          </tr>
        </thead>
        <tbody>
          {businessUnits.map((bu) => (
            <tr key={bu.id} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="p-4 font-mono font-medium text-primary-600">{bu.code}</td>
              <td className="p-4 text-gray-900">{bu.name_en}</td>
              <td className="p-4 text-gray-600">{bu.name_uz}</td>
              <td className="p-4">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  bu.unit_type === 'REVENUE_CENTER' ? 'bg-green-100 text-green-700' :
                  bu.unit_type === 'COST_CENTER' ? 'bg-red-100 text-red-700' :
                  bu.unit_type === 'PROFIT_CENTER' ? 'bg-blue-100 text-blue-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {bu.unit_type.replace('_', ' ')}
                </span>
              </td>
              <td className="p-4 text-center">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  bu.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  {bu.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (loading && classes.length === 0) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Chart of Accounts"
        subtitle="Manage account hierarchy and business units"
        actions={
          <div className="flex gap-2">
            <button
              onClick={handleSeedCOA}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              <Database className="w-4 h-4" />
              Seed COA Data
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

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}
      {success && <div className="mb-4"><SuccessMessage message={success} /></div>}

      <Card>
        <div className="p-4 border-b border-gray-200 flex gap-2">
          <TabButton active={activeTab === 'hierarchy'} onClick={() => setActiveTab('hierarchy')}>
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4" />
              Hierarchy
            </div>
          </TabButton>
          <TabButton active={activeTab === 'accounts'} onClick={() => setActiveTab('accounts')}>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Accounts ({accounts.length})
            </div>
          </TabButton>
          <TabButton active={activeTab === 'business-units'} onClick={() => setActiveTab('business-units')}>
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              Business Units ({businessUnits.length})
            </div>
          </TabButton>
        </div>

        <div className="p-4">
          {activeTab === 'hierarchy' && <HierarchyView />}
          {activeTab === 'accounts' && <AccountsTable />}
          {activeTab === 'business-units' && <BusinessUnitsTable />}
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
      const [templatesData, sectionsData, assignmentsData] = await Promise.all([
        templatesAPI.list(),
        templatesAPI.listSections(),
        templatesAPI.listAssignments(),
      ]);
      setTemplates(templatesData);
      setSections(sectionsData);
      setAssignments(assignmentsData);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load templates');
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
    <div className="overflow-x-auto">
      {assignments.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <ClipboardList className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>No template assignments yet</p>
          <p className="text-sm mt-2">Assign templates to business units to start budget planning</p>
        </div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-4 font-semibold text-gray-700">Template</th>
              <th className="text-left p-4 font-semibold text-gray-700">Business Unit</th>
              <th className="text-center p-4 font-semibold text-gray-700">Fiscal Year</th>
              <th className="text-left p-4 font-semibold text-gray-700">Deadline</th>
              <th className="text-center p-4 font-semibold text-gray-700">Status</th>
              <th className="text-center p-4 font-semibold text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((assignment) => (
              <tr key={assignment.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-medium text-gray-900">
                  {assignment.template?.name_en || `Template #${assignment.template_id}`}
                </td>
                <td className="p-4 text-gray-600">
                  {assignment.business_unit?.name_en || `BU #${assignment.business_unit_id}`}
                </td>
                <td className="p-4 text-center font-semibold">{assignment.fiscal_year}</td>
                <td className="p-4 text-gray-600">{assignment.deadline || '-'}</td>
                <td className="p-4 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(assignment.status)}`}>
                    {assignment.status}
                  </span>
                </td>
                <td className="p-4 text-center">
                  <button className="text-primary-600 hover:text-primary-700">
                    <Pencil className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
