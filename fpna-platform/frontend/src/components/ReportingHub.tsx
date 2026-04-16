// ReportingHub.tsx - Professional FP&A Reporting Hub
// Power BI Workspace Embed | Excel Ad-hoc | Paginated Reports | Report Library
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { excelExportAPI } from '../services/api';
import {
  BarChart2,
  FileSpreadsheet,
  FileText,
  BookOpen,
  ExternalLink,
  Link2,
  Download,
  RefreshCw,
  Plus,
  Trash2,
  Eye,
  Settings,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  ChevronRight,
  Monitor,
  Table,
  PieChart,
  TrendingUp,
  X,
} from 'lucide-react';

interface ReportingHubProps {
  theme: 'light' | 'dark';
}

interface PowerBIReport {
  id: string;
  name: string;
  url: string;
  workspace: string;
  lastViewed?: string;
}

interface ExcelReport {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  params?: Record<string, string>;
}

interface PaginatedReport {
  id: string;
  name: string;
  type: 'budget-summary' | 'variance' | 'department' | 'custom';
  description: string;
  status: 'ready' | 'generating' | 'error';
  lastGenerated?: string;
}

const REPORT_TABS = [
  { id: 'powerbi', label: 'Power BI', icon: Monitor },
  { id: 'excel', label: 'Excel Reports', icon: FileSpreadsheet },
  { id: 'paginated', label: 'Paginated Reports', icon: FileText },
  { id: 'library', label: 'Report Library', icon: BookOpen },
] as const;

type ReportTab = typeof REPORT_TABS[number]['id'];

const DEFAULT_EXCEL_REPORTS: ExcelReport[] = [
  { id: 'budget-plan', name: 'Budget Plan Export', description: 'Full budget plan with monthly breakdown by department', endpoint: '/api/v1/reports/budget-plan/export', params: {} },
  { id: 'variance', name: 'Variance Analysis', description: 'Plan vs Actual variance with % deviation by account', endpoint: '/api/v1/reports/variance/export', params: {} },
  { id: 'baseline', name: 'Baseline Comparison', description: 'Baseline vs planned amounts by account', endpoint: '/api/v1/reports/baseline/export', params: {} },
  { id: 'coa-summary', name: 'COA Summary', description: 'Chart of accounts with budget amounts by category', endpoint: '/api/v1/reports/budget-plan/export', params: {} },
];

const DEFAULT_PAGINATED: PaginatedReport[] = [
  { id: 'exec-summary', name: 'Executive Summary', type: 'budget-summary', description: 'High-level budget overview for C-suite distribution', status: 'ready', lastGenerated: '2026-03-14' },
  { id: 'dept-budget', name: 'Department Budget Pack', type: 'department', description: 'Per-department budget breakdown with YoY comparison', status: 'ready', lastGenerated: '2026-03-13' },
  { id: 'variance-report', name: 'Variance Report', type: 'variance', description: 'Monthly plan vs actual variance with commentary', status: 'ready', lastGenerated: '2026-03-10' },
  { id: 'board-report', name: 'Board Report', type: 'budget-summary', description: 'Formatted board-ready budget presentation', status: 'ready', lastGenerated: '2026-03-01' },
];

// ── Ad-hoc export sub-form ─────────────────────────────────────────────────
const AdhocExportForm: React.FC<{
  fiscalYear: string; isDark: boolean; btnPrimary: string; textSecondary: string;
}> = ({ fiscalYear, isDark, btnPrimary, textSecondary }) => {
  const [dataset, setDataset] = useState('Planned Budgets');
  const [groupBy, setGroupBy] = useState('Department');
  const [period, setPeriod] = useState('Full Year');
  const [loading, setLoading] = useState(false);
  const selectCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${isDark ? 'bg-slate-800 border-slate-700 text-slate-100' : 'bg-white border-slate-300 text-slate-900'}`;

  const run = async () => {
    setLoading(true);
    try {
      await excelExportAPI.adhoc({ fiscal_year: parseInt(fiscalYear, 10), dataset, group_by: groupBy, period });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Export failed');
    }
    setLoading(false);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      {[
        { label: 'Dataset', value: dataset, set: setDataset, options: ['Planned Budgets', 'Actuals', 'Baselines', 'Variance'] },
        { label: 'Group By', value: groupBy, set: setGroupBy, options: ['Department', 'Account', 'Business Unit', 'Month'] },
        { label: 'Period', value: period, set: setPeriod, options: ['Full Year', 'Q1', 'Q2', 'Q3', 'Q4', 'YTD'] },
      ].map(({ label, value, set, options }) => (
        <div key={label}>
          <label className={`block text-xs font-medium mb-1.5 ${textSecondary}`}>{label}</label>
          <select className={selectCls} value={value} onChange={e => set(e.target.value)}>
            {options.map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
      ))}
      <div className="md:col-span-3">
        <button onClick={run} disabled={loading} className={`${btnPrimary} disabled:opacity-60`}>
          {loading ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin inline-block" /> Generating…</> : <><Download className="w-4 h-4" /> Generate Export</>}
        </button>
      </div>
    </div>
  );
};

export const ReportingHub: React.FC<ReportingHubProps> = ({ theme }) => {
  const isDark = theme === 'dark';
  const [activeTab, setActiveTab] = useState<ReportTab>('powerbi');

  // Power BI state
  const [pbiReports, setPbiReports] = useState<PowerBIReport[]>(() => {
    try {
      const saved = localStorage.getItem('fpna_pbi_reports');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [selectedReport, setSelectedReport] = useState<PowerBIReport | null>(null);
  const [showAddReport, setShowAddReport] = useState(false);
  const [newReportName, setNewReportName] = useState('');
  const [newReportUrl, setNewReportUrl] = useState('');
  const [newReportWorkspace, setNewReportWorkspace] = useState('');
  const [iframeLoading, setIframeLoading] = useState(false);
  const [iframeError, setIframeError] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Excel state
  const [downloadingReport, setDownloadingReport] = useState<string | null>(null);
  const [fiscalYear, setFiscalYear] = useState('2026');

  // Paginated state
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);
  const [paginatedReports] = useState<PaginatedReport[]>(DEFAULT_PAGINATED);

  // Workspace connection state
  const [workspaceUrl, setWorkspaceUrl] = useState(() => localStorage.getItem('fpna_pbi_workspace') || '');
  const [showWorkspaceForm, setShowWorkspaceForm] = useState(false);
  const [workspaceDraft, setWorkspaceDraft] = useState('');

  const cardBg = isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200';
  const textPrimary = isDark ? 'text-slate-50' : 'text-slate-900';
  const textSecondary = isDark ? 'text-slate-400' : 'text-slate-500';
  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm ${
    isDark ? 'bg-slate-800 border-slate-700 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
  } focus:outline-none focus:ring-2 focus:ring-primary-500`;
  const btnPrimary = 'bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2';
  const btnSecondary = `px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center gap-2 ${
    isDark ? 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
  }`;

  const savePbiReports = (reports: PowerBIReport[]) => {
    setPbiReports(reports);
    localStorage.setItem('fpna_pbi_reports', JSON.stringify(reports));
  };

  const handleAddReport = () => {
    if (!newReportName.trim() || !newReportUrl.trim()) return;
    const report: PowerBIReport = {
      id: Date.now().toString(),
      name: newReportName.trim(),
      url: newReportUrl.trim(),
      workspace: newReportWorkspace.trim() || 'My Workspace',
      lastViewed: new Date().toISOString(),
    };
    savePbiReports([...pbiReports, report]);
    setNewReportName('');
    setNewReportUrl('');
    setNewReportWorkspace('');
    setShowAddReport(false);
    setSelectedReport(report);
  };

  const handleRemoveReport = (id: string) => {
    savePbiReports(pbiReports.filter((r) => r.id !== id));
    if (selectedReport?.id === id) setSelectedReport(null);
  };

  const handleSaveWorkspace = () => {
    localStorage.setItem('fpna_pbi_workspace', workspaceDraft);
    setWorkspaceUrl(workspaceDraft);
    setShowWorkspaceForm(false);
  };

  const handleExcelDownload = useCallback(async (report: ExcelReport) => {
    setDownloadingReport(report.id);
    try {
      const fy = parseInt(fiscalYear, 10);
      if (report.id === 'budget-plan') await excelExportAPI.budgetPlan(fy);
      else if (report.id === 'variance') await excelExportAPI.variance(fy);
      else if (report.id === 'baseline') await excelExportAPI.baselineComparison(fy);
      else if (report.id === 'driver-impact') await excelExportAPI.budgetPlan(fy); // fallback
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      alert(`Export error: ${msg}`);
    } finally {
      setDownloadingReport(null);
    }
  }, [fiscalYear]);

  const handleGenerateReport = async (report: PaginatedReport) => {
    setGeneratingReport(report.id);
    await new Promise((r) => setTimeout(r, 1500));
    alert(`"${report.name}" generation requires backend PDF service integration.\n\nEndpoint: POST /api/v1/reports/generate\nFormat: PDF / XLSX`);
    setGeneratingReport(null);
  };

  // Tab content renderers
  const renderPowerBI = () => (
    <div className="space-y-4">
      {/* Workspace connection bar */}
      <div className={`rounded-xl border p-4 flex items-center justify-between gap-4 ${cardBg}`}>
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${workspaceUrl ? 'bg-emerald-100' : isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
            <Link2 className={`w-4 h-4 ${workspaceUrl ? 'text-emerald-600' : textSecondary}`} />
          </div>
          <div className="min-w-0">
            <p className={`text-sm font-medium ${textPrimary}`}>Power BI Workspace</p>
            {workspaceUrl ? (
              <p className={`text-xs truncate max-w-xs ${textSecondary}`}>{workspaceUrl}</p>
            ) : (
              <p className={`text-xs ${textSecondary}`}>Not connected — add workspace URL to embed reports</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {workspaceUrl && (
            <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
              <CheckCircle className="w-3.5 h-3.5" /> Connected
            </span>
          )}
          <button onClick={() => { setWorkspaceDraft(workspaceUrl); setShowWorkspaceForm(true); }} className={btnSecondary}>
            <Settings className="w-3.5 h-3.5" />
            {workspaceUrl ? 'Change' : 'Connect'}
          </button>
        </div>
      </div>

      {/* Workspace connection form */}
      {showWorkspaceForm && (
        <div className={`rounded-xl border p-5 space-y-4 ${cardBg}`}>
          <h3 className={`font-semibold ${textPrimary}`}>Connect Power BI Workspace</h3>
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className={`block text-xs font-medium mb-1.5 ${textSecondary}`}>Workspace URL or Embed URL</label>
              <input
                value={workspaceDraft}
                onChange={(e) => setWorkspaceDraft(e.target.value)}
                placeholder="https://app.powerbi.com/groups/..."
                className={inputCls}
              />
              <p className={`text-xs mt-1 ${textSecondary}`}>Enter your Power BI workspace URL, report URL, or publish-to-web embed URL.</p>
            </div>
          </div>
          <div className={`rounded-lg p-3 text-xs space-y-1 ${isDark ? 'bg-slate-800/60' : 'bg-slate-50'}`}>
            <p className={`font-semibold ${textPrimary}`}>Supported URL formats:</p>
            <p className={textSecondary}>• Publish to web: <code>https://app.powerbi.com/reportEmbed?reportId=...</code></p>
            <p className={textSecondary}>• Workspace: <code>https://app.powerbi.com/groups/[workspace-id]/...</code></p>
            <p className={textSecondary}>• Embed token: Configure backend at <code>Settings → Power BI API</code></p>
          </div>
          <div className="flex gap-2">
            <button onClick={handleSaveWorkspace} className={btnPrimary}>Save Connection</button>
            <button onClick={() => setShowWorkspaceForm(false)} className={btnSecondary}>Cancel</button>
          </div>
        </div>
      )}

      {/* Report tiles + viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Report list */}
        <div className={`rounded-xl border ${cardBg} overflow-hidden`}>
          <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            <p className={`text-sm font-semibold ${textPrimary}`}>Reports</p>
            <button onClick={() => setShowAddReport(true)} className="p-1.5 rounded-lg hover:bg-primary-50 text-primary-600 transition-colors" title="Add report">
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="p-2 space-y-1 min-h-[200px]">
            {pbiReports.length === 0 ? (
              <div className={`p-6 text-center text-xs ${textSecondary}`}>
                <Monitor className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p>No reports added yet</p>
                <button onClick={() => setShowAddReport(true)} className="mt-2 text-primary-600 hover:underline font-medium">Add report</button>
              </div>
            ) : (
              pbiReports.map((r) => (
                <div
                  key={r.id}
                  onClick={() => { setSelectedReport(r); setIframeLoading(true); setIframeError(false); }}
                  className={`group flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    selectedReport?.id === r.id
                      ? isDark ? 'bg-primary-900/40 border border-primary-800' : 'bg-primary-50 border border-primary-200'
                      : isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="min-w-0">
                    <p className={`text-xs font-medium truncate ${selectedReport?.id === r.id ? 'text-primary-600' : textPrimary}`}>{r.name}</p>
                    <p className={`text-[11px] truncate ${textSecondary}`}>{r.workspace}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleRemoveReport(r.id); }}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-red-500 transition-all"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Embed area */}
        <div className={`lg:col-span-3 rounded-xl border overflow-hidden ${cardBg}`} style={{ minHeight: 520 }}>
          {!selectedReport ? (
            <div className={`flex flex-col items-center justify-center h-full min-h-[520px] ${textSecondary}`}>
              <Monitor className="w-16 h-16 mb-4 opacity-20" />
              <p className={`text-lg font-medium ${textPrimary}`}>Select a report to view</p>
              <p className="text-sm mt-1">Choose from the list or add a new Power BI report</p>
              <button onClick={() => setShowAddReport(true)} className={`mt-6 ${btnPrimary}`}>
                <Plus className="w-4 h-4" /> Add Report
              </button>
            </div>
          ) : (
            <>
              <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
                <div>
                  <p className={`font-semibold text-sm ${textPrimary}`}>{selectedReport.name}</p>
                  <p className={`text-xs ${textSecondary}`}>{selectedReport.workspace}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { setIframeLoading(true); setIframeError(false); if (iframeRef.current) iframeRef.current.src = selectedReport.url; }}
                    className={btnSecondary}
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Refresh
                  </button>
                  <a href={selectedReport.url} target="_blank" rel="noopener noreferrer" className={btnSecondary}>
                    <ExternalLink className="w-3.5 h-3.5" /> Open in Power BI
                  </a>
                </div>
              </div>
              <div className="relative" style={{ height: 480 }}>
                {iframeLoading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-slate-900/80 z-10">
                    <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
                  </div>
                )}
                {iframeError ? (
                  <div className="flex flex-col items-center justify-center h-full text-center px-8">
                    <AlertCircle className="w-12 h-12 text-amber-500 mb-4" />
                    <p className={`font-medium ${textPrimary}`}>Could not load report</p>
                    <p className={`text-sm mt-1 ${textSecondary}`}>The URL may require Power BI authentication or may block embedding.</p>
                    <a href={selectedReport.url} target="_blank" rel="noopener noreferrer" className={`mt-4 ${btnPrimary}`}>
                      <ExternalLink className="w-4 h-4" /> Open in Power BI
                    </a>
                  </div>
                ) : (
                  <iframe
                    ref={iframeRef}
                    src={selectedReport.url}
                    className="w-full h-full border-0"
                    title={selectedReport.name}
                    onLoad={() => setIframeLoading(false)}
                    onError={() => { setIframeLoading(false); setIframeError(true); }}
                    allowFullScreen
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Add report modal */}
      {showAddReport && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4 ${isDark ? 'bg-slate-900' : 'bg-white'}`}>
            <div className="flex items-center justify-between">
              <h3 className={`text-lg font-bold ${textPrimary}`}>Add Power BI Report</h3>
              <button onClick={() => setShowAddReport(false)} className={`p-2 rounded-lg ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'}`}>
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className={`block text-xs font-medium mb-1.5 ${textSecondary}`}>Report Name *</label>
                <input value={newReportName} onChange={(e) => setNewReportName(e.target.value)} placeholder="e.g. Budget Dashboard 2026" className={inputCls} />
              </div>
              <div>
                <label className={`block text-xs font-medium mb-1.5 ${textSecondary}`}>Embed URL *</label>
                <input value={newReportUrl} onChange={(e) => setNewReportUrl(e.target.value)} placeholder="https://app.powerbi.com/reportEmbed?..." className={inputCls} />
              </div>
              <div>
                <label className={`block text-xs font-medium mb-1.5 ${textSecondary}`}>Workspace / Group</label>
                <input value={newReportWorkspace} onChange={(e) => setNewReportWorkspace(e.target.value)} placeholder="e.g. FP&A Reports" className={inputCls} />
              </div>
            </div>
            <div className={`rounded-lg p-3 text-xs ${isDark ? 'bg-slate-800' : 'bg-slate-50'}`}>
              <p className={`font-medium mb-1 ${textPrimary}`}>How to get the embed URL:</p>
              <ol className={`list-decimal list-inside space-y-0.5 ${textSecondary}`}>
                <li>Open your report in Power BI Service</li>
                <li>File → Publish to web → Create embed code</li>
                <li>Copy the iframe <code>src</code> URL</li>
              </ol>
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={handleAddReport} disabled={!newReportName.trim() || !newReportUrl.trim()} className={`${btnPrimary} flex-1 justify-center disabled:opacity-50`}>
                Add Report
              </button>
              <button onClick={() => setShowAddReport(false)} className={btnSecondary}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderExcel = () => (
    <div className="space-y-4">
      {/* Fiscal year filter */}
      <div className={`rounded-xl border p-4 flex items-center gap-4 ${cardBg}`}>
        <label className={`text-sm font-medium ${textPrimary}`}>Fiscal Year:</label>
        <select
          value={fiscalYear}
          onChange={(e) => setFiscalYear(e.target.value)}
          className={`px-3 py-1.5 rounded-lg border text-sm ${isDark ? 'bg-slate-800 border-slate-700 text-slate-100' : 'bg-white border-slate-300 text-slate-900'} focus:outline-none focus:ring-2 focus:ring-primary-500`}
        >
          {[2025, 2026, 2027].map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <p className={`text-xs ${textSecondary}`}>All exports will use FY{fiscalYear} data</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {DEFAULT_EXCEL_REPORTS.map((report) => (
          <div key={report.id} className={`rounded-xl border p-5 flex flex-col gap-3 ${cardBg}`}>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-semibold text-sm ${textPrimary}`}>{report.name}</p>
                <p className={`text-xs mt-0.5 ${textSecondary}`}>{report.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-auto">
              <button
                onClick={() => handleExcelDownload(report)}
                disabled={downloadingReport === report.id}
                className={`${btnPrimary} flex-1 justify-center disabled:opacity-60`}
              >
                {downloadingReport === report.id ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                ) : (
                  <><Download className="w-4 h-4" /> Download .xlsx</>
                )}
              </button>
            </div>
            <p className={`text-[11px] font-mono ${textSecondary}`}>{report.endpoint}</p>
          </div>
        ))}
      </div>

      {/* Ad-hoc section */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Table className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className={`font-semibold text-sm ${textPrimary}`}>Ad-hoc Query Export</p>
            <p className={`text-xs ${textSecondary}`}>Build a custom export with field selection and filters</p>
          </div>
        </div>
        <AdhocExportForm fiscalYear={fiscalYear} isDark={isDark} btnPrimary={btnPrimary} textSecondary={textSecondary} />
      </div>
    </div>
  );

  const renderPaginated = () => (
    <div className="space-y-4">
      <div className={`rounded-xl border p-4 flex items-center gap-3 ${isDark ? 'bg-blue-950/30 border-blue-900/40' : 'bg-blue-50 border-blue-100'}`}>
        <FileText className="w-5 h-5 text-blue-500 shrink-0" />
        <p className={`text-sm ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
          Paginated reports generate formatted PDF or Excel outputs suitable for board distribution and audit trails.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {paginatedReports.map((report) => (
          <div key={report.id} className={`rounded-xl border p-5 ${cardBg}`}>
            <div className="flex items-start gap-3 mb-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                report.type === 'budget-summary' ? 'bg-indigo-100' :
                report.type === 'variance' ? 'bg-amber-100' :
                report.type === 'department' ? 'bg-teal-100' : 'bg-slate-100'
              }`}>
                {report.type === 'budget-summary' ? <PieChart className="w-5 h-5 text-indigo-600" /> :
                 report.type === 'variance' ? <TrendingUp className="w-5 h-5 text-amber-600" /> :
                 report.type === 'department' ? <BarChart2 className="w-5 h-5 text-teal-600" /> :
                 <FileText className="w-5 h-5 text-slate-600" />}
              </div>
              <div className="flex-1">
                <p className={`font-semibold text-sm ${textPrimary}`}>{report.name}</p>
                <p className={`text-xs mt-0.5 ${textSecondary}`}>{report.description}</p>
              </div>
              <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                report.status === 'ready' ? 'bg-emerald-100 text-emerald-700' :
                report.status === 'generating' ? 'bg-amber-100 text-amber-700' :
                'bg-red-100 text-red-700'
              }`}>
                {report.status}
              </span>
            </div>
            {report.lastGenerated && (
              <div className={`flex items-center gap-1.5 text-xs mb-4 ${textSecondary}`}>
                <Clock className="w-3.5 h-3.5" />
                Last generated: {new Date(report.lastGenerated).toLocaleDateString()}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerateReport(report)}
                disabled={generatingReport === report.id}
                className={`${btnPrimary} flex-1 justify-center disabled:opacity-60`}
              >
                {generatingReport === report.id ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                ) : (
                  <><RefreshCw className="w-4 h-4" /> Generate</>
                )}
              </button>
              <button
                onClick={() => alert('Download last generated report requires backend PDF service.')}
                className={btnSecondary}
              >
                <Download className="w-4 h-4" /> PDF
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderLibrary = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { icon: Monitor, label: 'Power BI Reports', count: pbiReports.length, color: 'yellow', desc: 'Connected Power BI reports' },
          { icon: FileSpreadsheet, label: 'Excel Exports', count: DEFAULT_EXCEL_REPORTS.length, color: 'emerald', desc: 'Available Excel exports' },
          { icon: FileText, label: 'Paginated Reports', count: paginatedReports.length, color: 'indigo', desc: 'Board-ready formatted reports' },
        ].map(({ icon: Icon, label, count, color, desc }) => (
          <div key={label} className={`rounded-xl border p-5 ${cardBg}`}>
            <div className={`w-10 h-10 rounded-lg bg-${color}-100 flex items-center justify-center mb-3`}>
              <Icon className={`w-5 h-5 text-${color}-600`} />
            </div>
            <p className={`text-2xl font-bold ${textPrimary}`}>{count}</p>
            <p className={`font-semibold text-sm mt-0.5 ${textPrimary}`}>{label}</p>
            <p className={`text-xs mt-1 ${textSecondary}`}>{desc}</p>
          </div>
        ))}
      </div>

      <div className={`rounded-xl border ${cardBg}`}>
        <div className={`px-5 py-4 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          <p className={`font-semibold ${textPrimary}`}>All Reports</p>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {[
            ...pbiReports.map((r) => ({ name: r.name, type: 'Power BI', icon: Monitor, action: () => { setActiveTab('powerbi'); setSelectedReport(r); } })),
            ...DEFAULT_EXCEL_REPORTS.map((r) => ({ name: r.name, type: 'Excel', icon: FileSpreadsheet, action: () => setActiveTab('excel') })),
            ...paginatedReports.map((r) => ({ name: r.name, type: 'Paginated', icon: FileText, action: () => setActiveTab('paginated') })),
          ].map((item, i) => (
            <div key={i} className={`px-5 py-3.5 flex items-center justify-between ${isDark ? 'hover:bg-slate-800/50' : 'hover:bg-slate-50'} transition-colors cursor-pointer`} onClick={item.action}>
              <div className="flex items-center gap-3">
                <item.icon className={`w-4 h-4 ${textSecondary}`} />
                <p className={`text-sm font-medium ${textPrimary}`}>{item.name}</p>
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>{item.type}</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${textSecondary}`} />
            </div>
          ))}
        </div>
      </div>

      {/* Integration info */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-primary-100 flex items-center justify-center">
            <Eye className="w-4 h-4 text-primary-600" />
          </div>
          <div>
            <p className={`font-semibold text-sm ${textPrimary}`}>Reporting Integration Options</p>
            <p className={`text-xs ${textSecondary}`}>Available output channels</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { title: 'Power BI Embed Token', desc: 'Secure embedding via Azure AD service principal. Configure in Settings → Power BI API.', tag: 'Enterprise' },
            { title: 'Publish to Web', desc: 'Public or organization-scoped embed URLs from Power BI Service.', tag: 'Standard' },
            { title: 'SSRS / Paginated', desc: 'SQL Server Reporting Services integration for pixel-perfect reports.', tag: 'On-premise' },
            { title: 'Scheduled Email', desc: 'Auto-distribute PDF reports to stakeholders on a schedule.', tag: 'Planned' },
          ].map(({ title, desc, tag }) => (
            <div key={title} className={`rounded-lg p-3.5 ${isDark ? 'bg-slate-800/60' : 'bg-slate-50'}`}>
              <div className="flex items-center justify-between mb-1">
                <p className={`text-sm font-medium ${textPrimary}`}>{title}</p>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'}`}>{tag}</span>
              </div>
              <p className={`text-xs ${textSecondary}`}>{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className={`text-2xl font-bold ${textPrimary}`}>Reporting</h1>
        <p className={`mt-1 text-sm ${textSecondary}`}>Power BI dashboards, ad-hoc Excel exports, and paginated reports</p>
      </div>

      {/* Tabs */}
      <div className={`rounded-xl border ${cardBg} overflow-hidden`}>
        <div className={`flex border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
          {REPORT_TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-primary-600 text-primary-600'
                  : `border-transparent ${textSecondary} ${isDark ? 'hover:text-slate-200 hover:bg-slate-800/60' : 'hover:text-slate-700 hover:bg-slate-50'}`
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
        <div className="p-5">
          {activeTab === 'powerbi' && renderPowerBI()}
          {activeTab === 'excel' && renderExcel()}
          {activeTab === 'paginated' && renderPaginated()}
          {activeTab === 'library' && renderLibrary()}
        </div>
      </div>
    </div>
  );
};

export default ReportingHub;
