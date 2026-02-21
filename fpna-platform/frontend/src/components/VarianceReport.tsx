import React, { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle, RefreshCw,
  Download, Filter, BarChart2, PieChart, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { dwhIntegrationAPI } from '../services/api';

interface VarianceItem {
  account_code: string;
  account_name: string;
  month: number;
  planned: number;
  actual: number;
  variance: number;
  variance_percent: number;
}

interface VarianceReportData {
  fiscal_year: number;
  month: number | null;
  department: string | null;
  summary: {
    total_planned: number;
    total_actual: number;
    total_variance: number;
    favorable_count: number;
    unfavorable_count: number;
    on_target_count: number;
  };
  top_variances: VarianceItem[];
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPercent = (value: number) => {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
};

export const VarianceReportPage = () => {
  const [report, setReport] = useState<VarianceReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fiscalYear, setFiscalYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number | undefined>();
  const [department, setDepartment] = useState<string>('');

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await dwhIntegrationAPI.getVarianceReport(
        fiscalYear,
        selectedMonth,
        department || undefined
      );
      setReport(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load variance report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, []);

  const getVarianceColor = (percent: number) => {
    if (Math.abs(percent) <= 5) return 'text-green-600';
    if (Math.abs(percent) <= 10) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getVarianceBg = (percent: number) => {
    if (Math.abs(percent) <= 5) return 'bg-green-50';
    if (Math.abs(percent) <= 10) return 'bg-yellow-50';
    return 'bg-red-50';
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plan vs Fact Analysis</h1>
          <p className="text-gray-500 mt-1">Compare budgeted amounts against actual results</p>
        </div>
        <button
          onClick={loadReport}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fiscal Year</label>
            <input
              type="number"
              value={fiscalYear}
              onChange={(e) => setFiscalYear(parseInt(e.target.value))}
              className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
            <select
              value={selectedMonth || ''}
              onChange={(e) => setSelectedMonth(e.target.value ? parseInt(e.target.value) : undefined)}
              className="w-40 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Months</option>
              {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
                <option key={m} value={m}>
                  {new Date(2000, m-1).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="All departments"
              className="w-48 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={loadReport}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2"
          >
            <Filter className="w-4 h-4" /> Apply Filters
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : report ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">Total Planned</span>
                <BarChart2 className="w-5 h-5 text-blue-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(report.summary.total_planned)}
              </p>
            </div>

            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">Total Actual</span>
                <PieChart className="w-5 h-5 text-green-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(report.summary.total_actual)}
              </p>
            </div>

            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">Total Variance</span>
                {report.summary.total_variance >= 0 ? (
                  <TrendingUp className="w-5 h-5 text-red-500" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-green-500" />
                )}
              </div>
              <p className={`text-2xl font-bold ${report.summary.total_variance >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                {report.summary.total_variance >= 0 ? '+' : ''}{formatCurrency(report.summary.total_variance)}
              </p>
            </div>

            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500">Performance</span>
                <CheckCircle className="w-5 h-5 text-purple-500" />
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded">
                  {report.summary.favorable_count} Favorable
                </span>
                <span className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded">
                  {report.summary.unfavorable_count} Over
                </span>
              </div>
            </div>
          </div>

          {/* Top Variances Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">Top Variances</h2>
              <button className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2">
                <Download className="w-4 h-4" /> Export
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Account
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Month
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Planned
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actual
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Variance
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Variance %
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {report.top_variances.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                        <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                        <p>No significant variances found</p>
                      </td>
                    </tr>
                  ) : (
                    report.top_variances.map((item, idx) => (
                      <tr key={idx} className={`hover:bg-gray-50 ${getVarianceBg(item.variance_percent)}`}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{item.account_code}</div>
                            <div className="text-sm text-gray-500">{item.account_name}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {item.month ? new Date(2000, item.month - 1).toLocaleString('default', { month: 'short' }) : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                          {formatCurrency(item.planned)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                          {formatCurrency(item.actual)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${getVarianceColor(item.variance_percent)}`}>
                          {item.variance >= 0 ? '+' : ''}{formatCurrency(item.variance)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-bold ${getVarianceColor(item.variance_percent)}`}>
                          <div className="flex items-center justify-end gap-1">
                            {item.variance_percent >= 0 ? (
                              <ArrowUpRight className="w-4 h-4" />
                            ) : (
                              <ArrowDownRight className="w-4 h-4" />
                            )}
                            {formatPercent(item.variance_percent)}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          {Math.abs(item.variance_percent) <= 5 ? (
                            <span className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded-full">On Target</span>
                          ) : Math.abs(item.variance_percent) <= 10 ? (
                            <span className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded-full">Warning</span>
                          ) : (
                            <span className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded-full">Critical</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-500">
          <BarChart2 className="w-16 h-16 mx-auto mb-4 text-gray-300" />
          <p className="text-lg font-medium">No variance data available</p>
          <p className="text-sm mt-2">Import actuals data to see Plan vs Fact analysis</p>
        </div>
      )}
    </div>
  );
};

export default VarianceReportPage;
