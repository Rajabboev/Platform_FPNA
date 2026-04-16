import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Loader2, AlertCircle, Check, X, RefreshCw, ArrowRightLeft,
  Banknote, Target, Database, Download, TrendingUp, TrendingDown,
  Calendar, Globe, Search, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { currenciesAPI } from '../../services/api';

// ── Types ──────────────────────────────────────────────────────────────────
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

interface BudgetRate {
  id: number;
  fiscal_year: number;
  month: number;
  from_currency: string;
  to_currency: string;
  planned_rate: number;
  assumption_type: string;
  is_approved: boolean;
  notes: string | null;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ── Currencies Page ────────────────────────────────────────────────────────
const CurrenciesPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'rates' | 'currencies' | 'budget-rates'>('rates');
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchCurrencies = useCallback(async () => {
    setLoading(true);
    try {
      const currData = await currenciesAPI.list();
      setCurrencies(currData);
      setInitialLoaded(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load');
      setInitialLoaded(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCurrencies(); }, [fetchCurrencies]);

  // Auto-dismiss success after 4s
  useEffect(() => {
    if (success) { const t = setTimeout(() => setSuccess(null), 4000); return () => clearTimeout(t); }
  }, [success]);

  // Build currency name map for quick lookup
  const currencyMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of currencies) m[c.code] = c.name_en;
    return m;
  }, [currencies]);

  if (loading && !initialLoaded) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-primary-600 animate-spin" /></div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Currencies & FX Rates</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Official CBU exchange rates, currency management, and budget FX planning
          </p>
        </div>
        <button onClick={fetchCurrencies} className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-800 dark:text-gray-300 dark:border-slate-600">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
          <span className="text-red-800 dark:text-red-300 flex-1 text-sm">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4 text-red-400" /></button>
        </div>
      )}
      {success && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 flex items-center gap-3">
          <Check className="w-5 h-5 text-green-600 shrink-0" />
          <span className="text-green-800 dark:text-green-300 flex-1 text-sm">{success}</span>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4 text-green-400" /></button>
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700">
        <div className="p-4 border-b border-gray-200 dark:border-slate-700 flex gap-2">
          {([
            { key: 'rates' as const, icon: Globe, label: 'CBU Exchange Rates' },
            { key: 'currencies' as const, icon: Banknote, label: `Currencies (${currencies.length})` },
            { key: 'budget-rates' as const, icon: Target, label: 'Budget Rates' },
          ]).map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2 ${
                activeTab === key
                  ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400'
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {activeTab === 'rates' && (
            <FXRatesTab
              currencies={currencies}
              currencyMap={currencyMap}
              onRefreshCurrencies={fetchCurrencies}
              onError={setError}
              onSuccess={setSuccess}
            />
          )}
          {activeTab === 'currencies' && (
            <CurrenciesTab currencies={currencies} onRefresh={fetchCurrencies} onError={setError} onSuccess={setSuccess} />
          )}
          {activeTab === 'budget-rates' && (
            <BudgetRatesTab currencies={currencies} onError={setError} onSuccess={setSuccess} />
          )}
        </div>
      </div>
    </div>
  );
};

// ── Tab 1: FX Rates (professional, table-driven) ─────────────────────────
const FXRatesTab: React.FC<{
  currencies: Currency[];
  currencyMap: Record<string, string>;
  onRefreshCurrencies: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ currencies, currencyMap, onRefreshCurrencies, onError, onSuccess }) => {
  const today = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(today);
  const [rates, setRates] = useState<FXRate[]>([]);
  const [loadingRates, setLoadingRates] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [search, setSearch] = useState('');
  const [lastFetchInfo, setLastFetchInfo] = useState<{ count: number; newCurrencies: number } | null>(null);

  // Converter
  const [convertAmount, setConvertAmount] = useState('1000');
  const [convertFrom, setConvertFrom] = useState('USD');
  const [convertTo, setConvertTo] = useState('UZS');
  const [convertResult, setConvertResult] = useState<{ converted_amount: number; rate_used: number } | null>(null);

  const loadRates = useCallback(async () => {
    setLoadingRates(true);
    try {
      const data = await currenciesAPI.listRates({
        start_date: selectedDate,
        end_date: selectedDate,
        limit: 500,
      });
      setRates(data || []);
    } catch {
      setRates([]);
    } finally {
      setLoadingRates(false);
    }
  }, [selectedDate]);

  useEffect(() => { loadRates(); }, [loadRates]);

  const handleFetchCBU = async () => {
    try {
      setFetching(true);
      setLastFetchInfo(null);
      const result = await currenciesAPI.fetchCBURates(selectedDate);
      setLastFetchInfo({ count: result.fetched, newCurrencies: result.currencies_created || 0 });
      onSuccess(`Imported ${result.fetched} official rates from CBU for ${result.date}`);
      onRefreshCurrencies();
      await loadRates();
    } catch (err: any) {
      onError(err.response?.data?.detail || 'CBU fetch failed');
    } finally {
      setFetching(false);
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
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Conversion failed');
    }
  };

  // Navigate date
  const shiftDate = (days: number) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + days);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  // Filter + sort rates
  const filteredRates = useMemo(() => {
    let filtered = rates;
    if (search) {
      const q = search.toLowerCase();
      filtered = rates.filter(r =>
        r.from_currency.toLowerCase().includes(q) ||
        (currencyMap[r.from_currency] || '').toLowerCase().includes(q)
      );
    }
    return filtered.sort((a, b) => a.from_currency.localeCompare(b.from_currency));
  }, [rates, search, currencyMap]);

  // Key currencies to highlight
  const keyCurrencies = ['USD', 'EUR', 'GBP', 'RUB', 'CNY', 'JPY', 'CHF', 'KZT'];
  const keyRates = useMemo(() =>
    keyCurrencies
      .map(code => rates.find(r => r.from_currency === code))
      .filter(Boolean) as FXRate[],
    [rates]
  );

  const formatDate = (d: string) => {
    const dt = new Date(d + 'T00:00:00');
    return dt.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
  };

  return (
    <div className="space-y-4">
      {/* ── Header: date nav + fetch ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button onClick={() => shiftDate(-1)} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800">
            <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
          </button>
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-slate-800 rounded-lg">
            <Calendar className="w-4 h-4 text-primary-600" />
            <input
              type="date"
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              className="bg-transparent font-medium text-gray-900 dark:text-white border-none outline-none"
            />
          </div>
          <button onClick={() => shiftDate(1)} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800">
            <ChevronRight className="w-4 h-4 text-gray-600 dark:text-gray-400" />
          </button>
          <button onClick={() => setSelectedDate(today)}
            className="px-3 py-2 text-xs font-medium text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-lg">
            Today
          </button>
        </div>

        <div className="flex items-center gap-3">
          {lastFetchInfo && (
            <span className="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-3 py-1.5 rounded-lg">
              {lastFetchInfo.count} rates imported
              {lastFetchInfo.newCurrencies > 0 && `, ${lastFetchInfo.newCurrencies} new currencies`}
            </span>
          )}
          <button
            onClick={handleFetchCBU}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm"
          >
            {fetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Fetch from CBU
          </button>
        </div>
      </div>

      {/* ── Key currencies cards ── */}
      {keyRates.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {keyRates.slice(0, 8).map(r => (
            <div key={r.from_currency} className="bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono font-bold text-primary-600 text-sm">{r.from_currency}</span>
                <span className="text-xs text-gray-400">{currencyMap[r.from_currency] || ''}</span>
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                {parseFloat(String(r.rate)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              <div className="text-xs text-gray-400">UZS / 1 {r.from_currency}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Converter ── */}
      <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-gray-50 to-slate-50 dark:from-slate-800 dark:to-slate-800/80 rounded-lg border border-gray-200 dark:border-slate-700">
        <span className="text-xs font-semibold text-gray-500 uppercase mr-1">Convert</span>
        <input type="number" value={convertAmount} onChange={e => setConvertAmount(e.target.value)}
          className="w-28 px-3 py-1.5 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm font-mono" />
        <select value={convertFrom} onChange={e => { setConvertFrom(e.target.value); setConvertResult(null); }}
          className="px-2 py-1.5 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm">
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="GBP">GBP</option>
          <option value="RUB">RUB</option>
          {currencies.filter(c => !['USD','EUR','GBP','RUB','UZS'].includes(c.code)).map(c =>
            <option key={c.code} value={c.code}>{c.code}</option>
          )}
        </select>
        <ArrowRightLeft className="w-4 h-4 text-gray-400 shrink-0" />
        <select value={convertTo} onChange={e => { setConvertTo(e.target.value); setConvertResult(null); }}
          className="px-2 py-1.5 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm">
          <option value="UZS">UZS</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          {currencies.filter(c => !['USD','EUR','UZS'].includes(c.code)).map(c =>
            <option key={c.code} value={c.code}>{c.code}</option>
          )}
        </select>
        <button onClick={handleConvert} className="px-4 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm font-medium">
          =
        </button>
        {convertResult && (
          <div className="text-sm font-semibold text-green-600 dark:text-green-400 ml-1">
            {convertResult.converted_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {convertTo}
            <span className="text-xs text-gray-400 ml-1 font-normal">(@ {convertResult.rate_used})</span>
          </div>
        )}
      </div>

      {/* ── Search + stats bar ── */}
      <div className="flex items-center justify-between">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search currency..."
            className="pl-9 pr-3 py-2 w-64 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-white text-sm"
          />
        </div>
        <div className="text-xs text-gray-400">
          {loadingRates ? (
            <span className="flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Loading...</span>
          ) : (
            <span>
              <strong className="text-gray-600 dark:text-gray-300">{filteredRates.length}</strong> rates for {formatDate(selectedDate)}
              {rates.length > 0 && <span className="ml-2 px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded font-medium">CBU Official</span>}
            </span>
          )}
        </div>
      </div>

      {/* ── Rates Table ── */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300 w-20">Code</th>
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300">Currency</th>
              <th className="text-right p-3 font-semibold text-gray-600 dark:text-gray-300">Rate (UZS)</th>
              <th className="text-center p-3 font-semibold text-gray-600 dark:text-gray-300 w-20">Source</th>
            </tr>
          </thead>
          <tbody>
            {filteredRates.map(r => {
              const isKey = keyCurrencies.includes(r.from_currency);
              return (
                <tr key={r.id}
                  className={`border-b border-gray-100 dark:border-slate-700/50 hover:bg-blue-50/50 dark:hover:bg-slate-800/50 ${
                    isKey ? 'bg-blue-50/30 dark:bg-blue-900/10' : ''
                  }`}>
                  <td className="p-3">
                    <span className={`font-mono font-bold ${isKey ? 'text-primary-600' : 'text-gray-700 dark:text-gray-300'}`}>
                      {r.from_currency}
                    </span>
                  </td>
                  <td className="p-3 text-gray-700 dark:text-gray-300">
                    {currencyMap[r.from_currency] || r.from_currency}
                  </td>
                  <td className="p-3 text-right">
                    <span className="font-mono font-semibold text-gray-900 dark:text-white">
                      {parseFloat(String(r.rate)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      r.rate_source === 'CBU'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {r.rate_source}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loadingRates && filteredRates.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Globe className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No rates for {formatDate(selectedDate)}</p>
            <p className="text-sm mt-1">Click <strong>"Fetch from CBU"</strong> to import official exchange rates</p>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Tab 2: Currencies List ────────────────────────────────────────────────
const CurrenciesTab: React.FC<{
  currencies: Currency[];
  onRefresh: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ currencies, onRefresh, onError, onSuccess }) => {
  const handleSeed = async () => {
    try {
      await currenciesAPI.seed();
      onSuccess('Default currencies seeded');
      onRefresh();
    } catch (err: any) { onError(err.response?.data?.detail || 'Seed failed'); }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-gray-500">
          {currencies.length} currencies registered. Currencies are auto-created when fetching CBU rates.
        </p>
        <button onClick={handleSeed} className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-800 dark:text-gray-300 dark:border-slate-600 text-sm">
          <Database className="w-4 h-4" /> Seed Defaults
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-slate-800 border-b dark:border-slate-700">
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300">Code</th>
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300">Symbol</th>
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300">Name (EN)</th>
              <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300">Name (UZ)</th>
              <th className="text-center p-3 font-semibold text-gray-600 dark:text-gray-300">Base</th>
              <th className="text-center p-3 font-semibold text-gray-600 dark:text-gray-300">Status</th>
            </tr>
          </thead>
          <tbody>
            {currencies.map(c => (
              <tr key={c.id} className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-800/50">
                <td className="p-3 font-mono font-bold text-primary-600">{c.code}</td>
                <td className="p-3 text-lg">{c.symbol}</td>
                <td className="p-3 text-gray-900 dark:text-white">{c.name_en}</td>
                <td className="p-3 text-gray-500 dark:text-gray-400">{c.name_uz}</td>
                <td className="p-3 text-center">
                  {c.is_base_currency && <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-medium">BASE</span>}
                </td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                    {c.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {currencies.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <Banknote className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No currencies. Fetch CBU rates to auto-create, or click "Seed Defaults".</p>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Tab 3: Budget FX Rates ────────────────────────────────────────────────
const BudgetRatesTab: React.FC<{
  currencies: Currency[];
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}> = ({ currencies, onError, onSuccess }) => {
  const currentYear = new Date().getFullYear();
  const [fiscalYear, setFiscalYear] = useState(currentYear + 1);
  const [selectedCurrency, setSelectedCurrency] = useState('USD');
  const [budgetRates, setBudgetRates] = useState<BudgetRate[]>([]);
  const [actualRates, setActualRates] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);

  // Generate form
  const [baseRate, setBaseRate] = useState('');
  const [growthRate, setGrowthRate] = useState('');
  const [assumption, setAssumption] = useState('flat');

  // Edit state
  const [editRates, setEditRates] = useState<Record<number, string>>({});

  const loadBudgetRates = useCallback(async () => {
    if (!selectedCurrency) return;
    setLoading(true);
    try {
      const data = await currenciesAPI.listBudgetRates({ fiscal_year: fiscalYear, from_currency: selectedCurrency });
      setBudgetRates(data || []);
      const edits: Record<number, string> = {};
      for (const r of (data || [])) edits[r.month] = r.planned_rate?.toString() || '';
      setEditRates(edits);

      // Load actual CBU monthly averages
      try {
        const history = await currenciesAPI.getRateHistory(selectedCurrency, {
          start_date: `${fiscalYear}-01-01`,
          end_date: `${fiscalYear}-12-31`,
        });
        const monthRates: Record<number, number[]> = {};
        for (const pt of (history.data_points || [])) {
          const month = new Date(pt.rate_date).getMonth() + 1;
          if (!monthRates[month]) monthRates[month] = [];
          monthRates[month].push(pt.rate);
        }
        const avgRates: Record<number, number> = {};
        for (const [m, vals] of Object.entries(monthRates)) {
          avgRates[parseInt(m)] = vals.reduce((a: number, b: number) => a + b, 0) / vals.length;
        }
        setActualRates(avgRates);
      } catch { setActualRates({}); }
    } catch (err: any) {
      if (err.response?.status !== 404) onError(err.response?.data?.detail || 'Failed to load budget rates');
      setBudgetRates([]);
    } finally { setLoading(false); }
  }, [fiscalYear, selectedCurrency, onError]);

  useEffect(() => { loadBudgetRates(); }, [loadBudgetRates]);

  const handleGenerate = async () => {
    if (!baseRate) { onError('Base rate is required'); return; }
    try {
      setGenerating(true);
      await currenciesAPI.generateBudgetRates({
        fiscal_year: fiscalYear, from_currency: selectedCurrency, to_currency: 'UZS',
        assumption_type: assumption, base_rate: parseFloat(baseRate),
        growth_rate: growthRate ? parseFloat(growthRate) : undefined,
      });
      onSuccess(`Generated ${assumption} budget rates for ${selectedCurrency}/${fiscalYear}`);
      await loadBudgetRates();
    } catch (err: any) { onError(err.response?.data?.detail || 'Failed to generate'); }
    finally { setGenerating(false); }
  };

  const handleSaveRate = async (month: number) => {
    const val = editRates[month];
    if (!val) return;
    try {
      await currenciesAPI.createBudgetRate({
        fiscal_year: fiscalYear, month, from_currency: selectedCurrency, to_currency: 'UZS',
        planned_rate: parseFloat(val), assumption_type: 'manual',
      });
      onSuccess(`Saved ${MONTHS[month - 1]} rate`);
      await loadBudgetRates();
    } catch (err: any) { onError(err.response?.data?.detail || 'Save failed'); }
  };

  const handleApprove = async () => {
    try {
      setApproving(true);
      await currenciesAPI.approveBudgetRates(fiscalYear, selectedCurrency, 1);
      onSuccess(`Approved budget rates for ${selectedCurrency}/${fiscalYear}`);
      await loadBudgetRates();
    } catch (err: any) { onError(err.response?.data?.detail || 'Approve failed'); }
    finally { setApproving(false); }
  };

  const isFullyApproved = budgetRates.length === 12 && budgetRates.every(r => r.is_approved);
  const activeCurrencies = currencies.filter(c => c.is_active && !c.is_base_currency);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Currency</label>
          <select value={selectedCurrency} onChange={e => setSelectedCurrency(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm">
            {activeCurrencies.length > 0
              ? activeCurrencies.map(c => <option key={c.code} value={c.code}>{c.code} — {c.name_en}</option>)
              : <option value="USD">USD</option>
            }
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Fiscal Year</label>
          <select value={fiscalYear} onChange={e => setFiscalYear(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm">
            {[currentYear - 1, currentYear, currentYear + 1, currentYear + 2].map(y =>
              <option key={y} value={y}>{y}</option>
            )}
          </select>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {isFullyApproved ? (
            <span className="px-3 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium flex items-center gap-1">
              <Check className="w-4 h-4" /> Approved
            </span>
          ) : budgetRates.length > 0 && (
            <button onClick={handleApprove} disabled={approving}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">
              {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Approve All
            </button>
          )}
        </div>
      </div>

      {/* Generate form */}
      <div className="bg-white dark:bg-slate-800 border dark:border-slate-700 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Generate Budget Rates</h4>
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Assumption</label>
            <select value={assumption} onChange={e => setAssumption(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm">
              <option value="flat">Flat (same rate)</option>
              <option value="linear_growth">Linear Growth</option>
              <option value="seasonal">Seasonal</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Base Rate (per 1 {selectedCurrency})</label>
            <input type="number" step="0.01" value={baseRate} onChange={e => setBaseRate(e.target.value)}
              placeholder="e.g. 12850" className="w-40 px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm" />
          </div>
          {assumption !== 'flat' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Growth Rate (%)</label>
              <input type="number" step="0.1" value={growthRate} onChange={e => setGrowthRate(e.target.value)}
                placeholder="e.g. 2.5" className="w-32 px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-900 dark:text-white text-sm" />
            </div>
          )}
          <button onClick={handleGenerate} disabled={generating || !baseRate}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm">
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />} Generate
          </button>
        </div>
      </div>

      {/* Budget Rates Matrix */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 animate-spin text-primary-600" /></div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-slate-800 border-b dark:border-slate-700">
                <th className="text-left p-3 font-semibold text-gray-600 dark:text-gray-300 w-36">Row</th>
                {MONTHS.map(m => (
                  <th key={m} className="text-center p-2 font-semibold text-gray-600 dark:text-gray-300">{m}</th>
                ))}
                <th className="text-center p-2 font-semibold text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-slate-700">Avg</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-200 dark:border-slate-700">
                <td className="p-3 font-medium text-gray-900 dark:text-white">Budget Rate</td>
                {MONTHS.map((_, i) => {
                  const m = i + 1;
                  const rate = budgetRates.find(r => r.month === m);
                  return (
                    <td key={m} className="p-1">
                      <input type="number" step="0.01" value={editRates[m] || ''} placeholder="—"
                        onChange={e => setEditRates(prev => ({ ...prev, [m]: e.target.value }))}
                        onBlur={() => { if (editRates[m] && editRates[m] !== rate?.planned_rate?.toString()) handleSaveRate(m); }}
                        className={`w-full px-1.5 py-1.5 border rounded text-center text-xs font-mono focus:ring-2 focus:ring-primary-500 ${
                          rate?.is_approved ? 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20' : 'border-gray-300 dark:border-slate-600 dark:bg-slate-800'
                        } dark:text-white`}
                      />
                    </td>
                  );
                })}
                <td className="p-2 text-center font-mono text-xs font-semibold bg-gray-50 dark:bg-slate-700">
                  {budgetRates.length > 0 ? (budgetRates.reduce((s, r) => s + (r.planned_rate || 0), 0) / budgetRates.length).toFixed(2) : '—'}
                </td>
              </tr>
              <tr className="border-b border-gray-100 dark:border-slate-700/50 bg-gray-50/50 dark:bg-slate-800/30">
                <td className="p-3 text-gray-500 text-xs">Actual (CBU avg)</td>
                {MONTHS.map((_, i) => (
                  <td key={i} className="p-2 text-center font-mono text-xs text-gray-500">
                    {actualRates[i + 1] ? actualRates[i + 1].toFixed(2) : '—'}
                  </td>
                ))}
                <td className="p-2 text-center font-mono text-xs text-gray-500 bg-gray-50 dark:bg-slate-700">
                  {Object.keys(actualRates).length > 0
                    ? (Object.values(actualRates).reduce((a, b) => a + b, 0) / Object.keys(actualRates).length).toFixed(2) : '—'}
                </td>
              </tr>
              <tr className="border-b border-gray-200 dark:border-slate-700">
                <td className="p-3 text-gray-500 text-xs">Variance</td>
                {MONTHS.map((_, i) => {
                  const m = i + 1;
                  const budget = editRates[m] ? parseFloat(editRates[m]) : null;
                  const actual = actualRates[m] || null;
                  const diff = budget !== null && actual !== null ? budget - actual : null;
                  return (
                    <td key={m} className="p-2 text-center">
                      {diff !== null ? (
                        <span className={`font-mono text-xs font-medium ${diff > 0 ? 'text-red-600' : diff < 0 ? 'text-green-600' : 'text-gray-400'}`}>
                          {diff > 0 ? '+' : ''}{diff.toFixed(1)}
                        </span>
                      ) : <span className="text-gray-300 text-xs">—</span>}
                    </td>
                  );
                })}
                <td className="p-2 bg-gray-50 dark:bg-slate-700"></td>
              </tr>
            </tbody>
          </table>
          {budgetRates.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Target className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No budget rates for {selectedCurrency}/{fiscalYear}</p>
              <p className="text-sm mt-1">Use "Generate" above to create planned FX rates</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CurrenciesPage;
