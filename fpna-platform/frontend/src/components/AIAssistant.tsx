import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot, Send, Loader2, AlertTriangle, CheckCircle, XCircle,
  TrendingUp, TrendingDown, BarChart2, Sparkles, RefreshCw,
  ChevronDown, ChevronUp, Zap, X, Plus, MessageSquare, Trash2, Clock
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface ChartDataset {
  label: string;
  data: number[];
  color?: string;
}

interface ChartData {
  type: 'bar' | 'line';
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

interface Alert {
  severity: 'warning' | 'critical';
  message: string;
  area: string;
}

interface HealthResult {
  fiscal_year: number;
  health_score: number;
  plan_total: number;
  baseline_total: number;
  variance_pct: number;
  verdict: 'ON TRACK' | 'AT RISK' | 'CRITICAL' | 'UNKNOWN';
  alerts: Alert[];
  total_plans: number;
  approved_count: number;
}

interface ProjectionRow {
  category: string;
  baseline: number;
  projected: number;
  change_pct: number;
}

interface ProjectionTable {
  scenario: string;
  fiscal_year: number;
  rows: ProjectionRow[];
  summary: {
    nii: { baseline: number; projected: number };
    net_income: { baseline: number; projected: number };
  };
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  chartData?: ChartData;
  projectionTable?: ProjectionTable;
  isStreaming?: boolean;
  toolCalls?: string[];
}

// ── Chat History ────────────────────────────────────────────────────────────

interface SavedConversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

const HISTORY_KEY = 'fpna_ai_chat_history';
const MAX_CONVERSATIONS = 20;

const loadConversations = (): SavedConversation[] => {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
};

const saveConversations = (convos: SavedConversation[]) => {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(convos.slice(0, MAX_CONVERSATIONS)));
};

const getConversationTitle = (messages: ChatMessage[]): string => {
  const firstUser = messages.find(m => m.role === 'user');
  if (!firstUser) return 'New conversation';
  const text = firstUser.content.slice(0, 50);
  return text.length < firstUser.content.length ? text + '…' : text;
};

interface ScenarioAdjustment {
  label: string;
  department: string;
  change_type: 'percentage' | 'absolute';
  value: number;
}

interface AIAssistantProps {
  theme: 'light' | 'dark';
  fiscalYear?: number;
}

// ── Mini bar chart (SVG, no deps) ──────────────────────────────────────────

const MiniBarChart: React.FC<{ data: ChartData; isDark: boolean }> = ({ data, isDark }) => {
  const W = 500;
  const H = 180;
  const PAD = { top: 30, right: 20, bottom: 50, left: 60 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;
  const allValues = data.datasets.flatMap(ds => ds.data);
  const maxVal = Math.max(...allValues, 1);
  const labels = data.labels;
  const barGroupW = chartW / labels.length;
  const barW = Math.min(24, (barGroupW / data.datasets.length) - 4);

  const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444'];
  const textColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? '#334155' : '#e2e8f0';

  const fmt = (v: number) => v >= 1e9 ? `${(v / 1e9).toFixed(1)}B`
    : v >= 1e6 ? `${(v / 1e6).toFixed(1)}M`
    : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K`
    : v.toFixed(0);

  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
      <p className="px-4 pt-3 pb-1 text-xs font-semibold text-slate-500 dark:text-slate-400">{data.title}</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(frac => {
          const y = PAD.top + chartH * (1 - frac);
          return (
            <g key={frac}>
              <line x1={PAD.left} y1={y} x2={PAD.left + chartW} y2={y} stroke={gridColor} strokeWidth="1" strokeDasharray="4,3" />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize="9" fill={textColor}>{fmt(maxVal * frac)}</text>
            </g>
          );
        })}

        {/* Bars */}
        {labels.map((label, gi) => {
          const groupX = PAD.left + gi * barGroupW;
          return (
            <g key={label}>
              {data.datasets.map((ds, di) => {
                const barH = Math.max(2, (ds.data[gi] / maxVal) * chartH);
                const x = groupX + (barGroupW - barW * data.datasets.length) / 2 + di * barW;
                const y = PAD.top + chartH - barH;
                const color = COLORS[di % COLORS.length];
                return (
                  <rect key={di} x={x} y={y} width={barW - 2} height={barH}
                    fill={color} rx="2" opacity="0.85" />
                );
              })}
              <text x={groupX + barGroupW / 2} y={PAD.top + chartH + 14}
                textAnchor="middle" fontSize="9" fill={textColor}>{label}</text>
            </g>
          );
        })}

        {/* Legend */}
        {data.datasets.map((ds, di) => (
          <g key={di}>
            <rect x={PAD.left + di * 100} y={H - 14} width={10} height={8} fill={COLORS[di % COLORS.length]} rx="1" />
            <text x={PAD.left + di * 100 + 14} y={H - 7} fontSize="9" fill={textColor}>{ds.label}</text>
          </g>
        ))}
      </svg>
    </div>
  );
};

// ── Health badge ───────────────────────────────────────────────────────────

const HealthBadge: React.FC<{ health: HealthResult }> = ({ health }) => {
  const cfg = {
    'ON TRACK': { color: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: CheckCircle, iconColor: 'text-emerald-600' },
    'AT RISK': { color: 'text-amber-700 bg-amber-50 border-amber-200', icon: AlertTriangle, iconColor: 'text-amber-500' },
    'CRITICAL': { color: 'text-red-700 bg-red-50 border-red-200', icon: XCircle, iconColor: 'text-red-500' },
    'UNKNOWN': { color: 'text-slate-600 bg-slate-50 border-slate-200', icon: RefreshCw, iconColor: 'text-slate-400' },
  }[health.verdict] ?? { color: 'text-slate-600 bg-slate-50 border-slate-200', icon: RefreshCw, iconColor: 'text-slate-400' };

  const Icon = cfg.icon;

  return (
    <div className={`rounded-xl border p-4 ${cfg.color}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${cfg.iconColor}`} />
        <span className="font-semibold text-sm">{health.verdict}</span>
        <span className="ml-auto text-xs font-mono">Score: {health.health_score}/100</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div><span className="opacity-60">Variance</span><br /><b>{health.variance_pct > 0 ? '+' : ''}{health.variance_pct?.toFixed(1)}%</b></div>
        <div><span className="opacity-60">Plans</span><br /><b>{health.total_plans}</b></div>
        <div><span className="opacity-60">Approved</span><br /><b>{health.approved_count}</b></div>
      </div>
      {health.alerts?.map((a, i) => (
        <div key={i} className="mt-2 text-xs flex items-start gap-1.5">
          <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
          <span>{a.message}</span>
        </div>
      ))}
    </div>
  );
};

// ── Projection table card ──────────────────────────────────────────────────

const ProjectionTableCard: React.FC<{ data: ProjectionTable; isDark: boolean }> = ({ data, isDark }) => {
  const fmt = (v: number) =>
    Math.abs(v) >= 1e12 ? `${(v / 1e12).toFixed(1)}T`
    : Math.abs(v) >= 1e9 ? `${(v / 1e9).toFixed(1)}B`
    : Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1)}M`
    : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(0)}K`
    : v.toFixed(0);

  const pctColor = (pct: number) =>
    pct > 0 ? 'text-emerald-600' : pct < 0 ? 'text-red-600' : 'text-slate-500';

  const border = isDark ? 'border-slate-700' : 'border-slate-200';
  const headerBg = isDark ? 'bg-slate-800' : 'bg-slate-100';
  const rowHover = isDark ? 'hover:bg-slate-800/50' : 'hover:bg-slate-50';
  const summaryBg = isDark ? 'bg-indigo-900/30' : 'bg-indigo-50';

  return (
    <div className={`mt-3 rounded-xl overflow-hidden border ${border}`}>
      <div className={`px-4 py-2.5 ${headerBg} flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-amber-500" />
          <span className="text-xs font-semibold uppercase tracking-wider">AI Projection: {data.scenario}</span>
        </div>
        <span className="text-[10px] text-slate-500">FY {data.fiscal_year}</span>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className={`${headerBg} border-b ${border}`}>
            <th className="text-left px-4 py-2 font-semibold">Category</th>
            <th className="text-right px-3 py-2 font-semibold">Baseline</th>
            <th className="text-right px-3 py-2 font-semibold">AI Projected</th>
            <th className="text-right px-3 py-2 font-semibold">Change</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className={`border-b ${border} ${rowHover}`}>
              <td className="px-4 py-2 font-medium">{row.category}</td>
              <td className="px-3 py-2 text-right font-mono text-slate-500">{fmt(row.baseline)}</td>
              <td className="px-3 py-2 text-right font-mono font-semibold">{fmt(row.projected)}</td>
              <td className={`px-3 py-2 text-right font-mono font-semibold ${pctColor(row.change_pct)}`}>
                {row.change_pct > 0 ? '+' : ''}{row.change_pct.toFixed(1)}%
              </td>
            </tr>
          ))}
          {/* NII summary */}
          {data.summary?.nii && (
            <tr className={`border-b-2 ${border} ${summaryBg} font-semibold`}>
              <td className="px-4 py-2 text-emerald-700 dark:text-emerald-400">Net Interest Income (NII)</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(data.summary.nii.baseline)}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(data.summary.nii.projected)}</td>
              <td className={`px-3 py-2 text-right font-mono ${pctColor(
                data.summary.nii.baseline ? ((data.summary.nii.projected - data.summary.nii.baseline) / Math.abs(data.summary.nii.baseline)) * 100 : 0
              )}`}>
                {data.summary.nii.baseline ? `${(((data.summary.nii.projected - data.summary.nii.baseline) / Math.abs(data.summary.nii.baseline)) * 100) > 0 ? '+' : ''}${(((data.summary.nii.projected - data.summary.nii.baseline) / Math.abs(data.summary.nii.baseline)) * 100).toFixed(1)}%` : '-'}
              </td>
            </tr>
          )}
          {/* Net Income summary */}
          {data.summary?.net_income && (
            <tr className={`${summaryBg} font-bold`}>
              <td className="px-4 py-2 text-indigo-700 dark:text-indigo-400">Net Income</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(data.summary.net_income.baseline)}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(data.summary.net_income.projected)}</td>
              <td className={`px-3 py-2 text-right font-mono ${pctColor(
                data.summary.net_income.baseline ? ((data.summary.net_income.projected - data.summary.net_income.baseline) / Math.abs(data.summary.net_income.baseline)) * 100 : 0
              )}`}>
                {data.summary.net_income.baseline ? `${(((data.summary.net_income.projected - data.summary.net_income.baseline) / Math.abs(data.summary.net_income.baseline)) * 100) > 0 ? '+' : ''}${(((data.summary.net_income.projected - data.summary.net_income.baseline) / Math.abs(data.summary.net_income.baseline)) * 100).toFixed(1)}%` : '-'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className={`px-4 py-2 ${headerBg} text-[10px] text-slate-500 flex items-center gap-1`}>
        <CheckCircle className="w-3 h-3 text-emerald-500" />
        Saved to database — visible in P&L Planning tab
      </div>
    </div>
  );
};

// ── Scenario panel ─────────────────────────────────────────────────────────

const PRESET_SCENARIOS: { label: string; adjustments: ScenarioAdjustment[] }[] = [
  {
    label: 'Headcount +10%',
    adjustments: [{ label: 'Salary cost +10%', department: 'ALL', change_type: 'percentage', value: 10 }]
  },
  {
    label: 'Revenue -15%',
    adjustments: [{ label: 'Revenue decline -15%', department: 'ALL', change_type: 'percentage', value: -15 }]
  },
  {
    label: 'Opex Freeze',
    adjustments: [
      { label: 'Admin cost -5%', department: 'Admin', change_type: 'percentage', value: -5 },
      { label: 'Ops cost -5%', department: 'Operations', change_type: 'percentage', value: -5 },
    ]
  },
  {
    label: 'Best Case',
    adjustments: [
      { label: 'Revenue +20%', department: 'Sales', change_type: 'percentage', value: 20 },
      { label: 'Cost -8%', department: 'ALL', change_type: 'percentage', value: -8 },
    ]
  },
];

// ── Main component ─────────────────────────────────────────────────────────

export const AIAssistant: React.FC<AIAssistantProps> = ({ theme, fiscalYear = 2026 }) => {
  const isDark = theme === 'dark';

  const makeWelcome = (): ChatMessage => ({
    id: 'welcome',
    role: 'assistant',
    content: `Hello! I'm your FP&A AI assistant powered by Claude Sonnet. I have live access to your FY ${fiscalYear} budget data.\n\nI can:\n• Answer budget questions and show variance analysis\n• Run what-if scenario calculations\n• **Generate P&L projections & stress tests** — anchored to **DWH BaselineData YoY** (per p_l_flag), with coherent stress/optimistic tilts\n• Check plan health and flag risks\n\nTry: "Run a DWH-anchored stress test for FY${fiscalYear} and save it as scenario bank_stress"`,
  });

  // ── Chat history state ─────────────────────────
  const [conversations, setConversations] = useState<SavedConversation[]>(() => loadConversations());
  const [activeConvoId, setActiveConvoId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([makeWelcome()]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [showScenario, setShowScenario] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [activeAdjustments, setActiveAdjustments] = useState<ScenarioAdjustment[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Save current conversation to history whenever messages change (after user interaction)
  useEffect(() => {
    const realMsgs = messages.filter(m => m.id !== 'welcome' && !m.isStreaming);
    if (realMsgs.length === 0) return; // don't save empty convos

    const now = new Date().toISOString();
    setConversations(prev => {
      let updated: SavedConversation[];
      if (activeConvoId) {
        updated = prev.map(c => c.id === activeConvoId
          ? { ...c, messages, title: getConversationTitle(messages), updatedAt: now }
          : c
        );
      } else {
        const newId = `conv_${Date.now()}`;
        setActiveConvoId(newId);
        updated = [{ id: newId, title: getConversationTitle(messages), messages, createdAt: now, updatedAt: now }, ...prev];
      }
      saveConversations(updated);
      return updated;
    });
  }, [messages.filter(m => !m.isStreaming).length]); // trigger only on finalized message count change

  const startNewChat = () => {
    setActiveConvoId(null);
    setMessages([makeWelcome()]);
    setInput('');
    setScenarioResult(null);
  };

  const loadConversation = (convo: SavedConversation) => {
    setActiveConvoId(convo.id);
    setMessages(convo.messages);
    setShowHistory(false);
    setInput('');
  };

  const deleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev => {
      const updated = prev.filter(c => c.id !== id);
      saveConversations(updated);
      return updated;
    });
    if (activeConvoId === id) startNewChat();
  };

  const bg = isDark ? 'bg-slate-900' : 'bg-white';
  const border = isDark ? 'border-slate-700' : 'border-slate-200';
  const textPrimary = isDark ? 'text-slate-100' : 'text-slate-900';
  const textSecondary = isDark ? 'text-slate-400' : 'text-slate-500';
  const inputBg = isDark ? 'bg-slate-800 border-slate-600 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400';
  const userBubble = 'bg-primary-600 text-white';
  const aiBubble = isDark ? 'bg-slate-800 border border-slate-700 text-slate-100' : 'bg-slate-50 border border-slate-200 text-slate-900';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load plan health on mount
  useEffect(() => {
    loadHealth();
  }, [fiscalYear]);

  const loadHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await fetch(`/api/v1/ai/health-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiscal_year: fiscalYear, alert_threshold_pct: 10 }),
      });
      if (res.ok) setHealth(await res.json());
    } catch { /* ignore */ }
    setHealthLoading(false);
  };

  // Extract a balanced JSON object starting at a given index
  const extractJsonObject = (str: string, startIdx: number): string | null => {
    if (str[startIdx] !== '{') return null;
    let depth = 0;
    let inString = false;
    let escape = false;
    for (let i = startIdx; i < str.length; i++) {
      const ch = str[i];
      if (escape) { escape = false; continue; }
      if (ch === '\\' && inString) { escape = true; continue; }
      if (ch === '"') { inString = !inString; continue; }
      if (inString) continue;
      if (ch === '{') depth++;
      else if (ch === '}') { depth--; if (depth === 0) return str.substring(startIdx, i + 1); }
    }
    return null;
  };

  // Parse chart_data and projection_table JSON from AI message text
  const extractStructuredData = (text: string): { text: string; chartData?: ChartData; projectionTable?: ProjectionTable } => {
    let cleaned = text;
    let chartData: ChartData | undefined;
    let projectionTable: ProjectionTable | undefined;

    // Sanitize JSON: fix +number (invalid JSON) → number
    const sanitizeJson = (s: string) => s.replace(/:\s*\+(\d)/g, ': $1');

    // Try extracting from ```json code blocks first, then fallback to raw search
    const codeBlockRegex = /```json\s*([\s\S]*?)```/g;
    let cbMatch;
    while ((cbMatch = codeBlockRegex.exec(cleaned)) !== null) {
      try {
        const obj = JSON.parse(sanitizeJson(cbMatch[1].trim()));
        if (obj.chart_data && !chartData) chartData = obj.chart_data;
        if (obj.projection_table && !projectionTable) projectionTable = obj.projection_table;
        cleaned = cleaned.replace(cbMatch[0], '').trim();
      } catch { /* ignore */ }
    }

    // Fallback: search for raw JSON objects with known keys
    if (!chartData) {
      const chartIdx = cleaned.indexOf('"chart_data"');
      if (chartIdx >= 0) {
        const braceIdx = cleaned.lastIndexOf('{', chartIdx);
        if (braceIdx >= 0) {
          const jsonStr = extractJsonObject(cleaned, braceIdx);
          if (jsonStr) {
            try {
              const obj = JSON.parse(sanitizeJson(jsonStr));
              chartData = obj.chart_data;
              cleaned = cleaned.replace(jsonStr, '').trim();
            } catch { /* ignore */ }
          }
        }
      }
    }

    if (!projectionTable) {
      const projIdx = cleaned.indexOf('"projection_table"');
      if (projIdx >= 0) {
        const braceIdx = cleaned.lastIndexOf('{', projIdx);
        if (braceIdx >= 0) {
          const jsonStr = extractJsonObject(cleaned, braceIdx);
          if (jsonStr) {
            try {
              const obj = JSON.parse(sanitizeJson(jsonStr));
              projectionTable = obj.projection_table;
              cleaned = cleaned.replace(jsonStr, '').trim();
            } catch { /* ignore */ }
          }
        }
      }
    }

    return { text: cleaned, chartData, projectionTable };
  };

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;
    const userText = input.trim();
    setInput('');
    setIsLoading(true);

    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', content: userText };
    const aiMsgId = (Date.now() + 1).toString();
    const aiMsg: ChatMessage = { id: aiMsgId, role: 'assistant', content: '', isStreaming: true };

    setMessages(prev => [...prev, userMsg, aiMsg]);

    try {
      const history = messages
        .filter(m => m.id !== 'welcome')
        .map(m => ({ role: m.role, content: m.content }));

      const res = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...history, { role: 'user', content: userText }],
          fiscal_year: fiscalYear,
        }),
      });

      if (!res.body) throw new Error('No stream body');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      const toolCallsFound: string[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const event = JSON.parse(data);
            if (event.type === 'text') {
              fullText += event.content;
            } else if (event.type === 'tool_call') {
              toolCallsFound.push(event.name);
            }
          } catch { /* ignore parse errors */ }
        }
        // Update message live
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId
            ? { ...m, content: fullText, toolCalls: toolCallsFound.length ? [...toolCallsFound] : undefined }
            : m
        ));
      }

      const { text: cleanText, chartData, projectionTable } = extractStructuredData(fullText);
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId
          ? { ...m, content: cleanText, isStreaming: false, chartData, projectionTable, toolCalls: toolCallsFound.length ? toolCallsFound : undefined }
          : m
      ));
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId
          ? { ...m, content: 'Sorry, I encountered an error. Please check your ANTHROPIC_API_KEY is set in the backend .env file.', isStreaming: false }
          : m
      ));
    }
    setIsLoading(false);
  }, [input, isLoading, messages, fiscalYear]);

  const runScenario = async (adjustments: ScenarioAdjustment[]) => {
    setScenarioLoading(true);
    setScenarioResult(null);
    setActiveAdjustments(adjustments);
    try {
      const res = await fetch('/api/v1/ai/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiscal_year: fiscalYear, adjustments }),
      });
      if (res.ok) setScenarioResult(await res.json());
    } catch { /* ignore */ }
    setScenarioLoading(false);
  };

  const SUGGESTED = [
    `How is our FY${fiscalYear} plan health?`,
    'Show variance by department',
    `FY${fiscalYear}: DWH-anchored optimistic P&L scenario — get_pl_driver_proposals, get_pl_baseline, generate_pl_projection scenario_profile optimistic, category_adjustments []`,
    `Generate a stress test scenario: interest income -10%, provisions +25%, OPEX +12%`,
  ];

  const fmtNum = (n: number) =>
    Math.abs(n) >= 1e9 ? `$${(n / 1e9).toFixed(2)}B`
    : Math.abs(n) >= 1e6 ? `$${(n / 1e6).toFixed(2)}M`
    : `$${n.toLocaleString()}`;

  return (
    <div className="flex flex-col h-full gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`text-2xl font-bold ${textPrimary}`}>AI Assistant</h1>
          <p className={`text-sm mt-0.5 ${textSecondary}`}>Claude Sonnet · FY {fiscalYear} budget intelligence</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={startNewChat} className="btn-ghost text-xs flex items-center gap-1.5" title="New conversation">
            <Plus className="w-4 h-4" /> New Chat
          </button>
          <div className="relative">
            <button
              onClick={() => setShowHistory(prev => !prev)}
              className={`btn-ghost text-xs flex items-center gap-1.5 ${showHistory ? 'ring-2 ring-primary-400' : ''}`}
              title="Chat history"
            >
              <Clock className="w-4 h-4" />
              History
              {conversations.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-primary-100 text-primary-700 text-[10px] font-bold dark:bg-primary-900 dark:text-primary-300">
                  {conversations.length}
                </span>
              )}
            </button>
            {showHistory && (
              <div className={`absolute right-0 top-full mt-1 w-80 max-h-96 overflow-y-auto rounded-xl border shadow-xl z-50 ${bg} ${border}`}>
                <div className={`px-3 py-2 border-b ${border} flex items-center justify-between sticky top-0 ${bg}`}>
                  <span className={`text-xs font-semibold uppercase tracking-wider ${textSecondary}`}>Chat History</span>
                  <button onClick={() => setShowHistory(false)} className="p-0.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                {conversations.length === 0 ? (
                  <div className={`p-4 text-center text-xs ${textSecondary}`}>No saved conversations</div>
                ) : (
                  conversations.map(c => (
                    <button
                      key={c.id}
                      onClick={() => loadConversation(c)}
                      className={`w-full text-left px-3 py-2.5 border-b last:border-b-0 ${border} hover:bg-primary-50 dark:hover:bg-slate-800 transition-colors flex items-start gap-2 group ${activeConvoId === c.id ? 'bg-primary-50 dark:bg-slate-800' : ''}`}
                    >
                      <MessageSquare className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${activeConvoId === c.id ? 'text-primary-500' : textSecondary}`} />
                      <div className="flex-1 min-w-0">
                        <div className={`text-xs font-medium truncate ${textPrimary}`}>{c.title}</div>
                        <div className={`text-[10px] mt-0.5 ${textSecondary}`}>
                          {new Date(c.updatedAt).toLocaleDateString()} · {c.messages.filter(m => m.role === 'user').length} messages
                        </div>
                      </div>
                      <button
                        onClick={(e) => deleteConversation(c.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-opacity"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3 text-red-500" />
                      </button>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <div className={`w-px h-5 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />
          <button
            onClick={() => setShowScenario(s => !s)}
            className={`btn-secondary flex items-center gap-2 text-sm ${showScenario ? 'ring-2 ring-primary-500' : ''}`}
          >
            <Zap className="w-4 h-4 text-amber-500" />
            What-if Scenarios
            {showScenario ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          <button onClick={loadHealth} disabled={healthLoading} className="btn-ghost p-2">
            <RefreshCw className={`w-4 h-4 ${healthLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left — Chat */}
        <div className={`flex flex-col flex-1 rounded-xl border ${border} ${bg} overflow-hidden`}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Suggested prompts (only at start) */}
            {messages.length === 1 && (
              <div className="grid grid-cols-2 gap-2 mt-2">
                {SUGGESTED.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(s); inputRef.current?.focus(); }}
                    className={`text-left text-xs px-3 py-2.5 rounded-lg border ${border} ${textSecondary} hover:border-primary-400 hover:text-primary-600 transition-colors`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] ${msg.role === 'user' ? 'order-2' : 'order-1'}`}>
                  {msg.role === 'assistant' && (
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <Bot className="w-3.5 h-3.5 text-primary-500" />
                      <span className="text-[11px] font-medium text-primary-500">Claude Sonnet</span>
                      {msg.toolCalls?.map(t => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-full">{t}</span>
                      ))}
                    </div>
                  )}
                  <div className={`px-4 py-3 rounded-xl text-sm leading-relaxed ${msg.role === 'user' ? `whitespace-pre-wrap ${userBubble}` : `prose-chat ${aiBubble}`}`}>
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    ) : (
                      msg.content
                    )}
                    {msg.isStreaming && (
                      <span className="inline-block w-1 h-4 bg-primary-400 ml-1 animate-pulse rounded" />
                    )}
                  </div>
                  {msg.chartData && <MiniBarChart data={msg.chartData} isDark={isDark} />}
                  {msg.projectionTable && <ProjectionTableCard data={msg.projectionTable} isDark={isDark} />}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className={`border-t ${border} p-3 flex gap-2 items-end`}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Ask about your budget, run scenarios, check variance…"
              rows={1}
              className={`flex-1 resize-none rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${inputBg}`}
              style={{ maxHeight: '100px' }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              className="btn-primary h-9 w-9 p-0 flex items-center justify-center disabled:opacity-50"
            >
              {isLoading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Send className="w-4 h-4" />
              }
            </button>
          </div>
        </div>

        {/* Right panel — health + scenarios */}
        <div className="w-72 shrink-0 flex flex-col gap-4">
          {/* Plan health */}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${textSecondary}`}>Plan Health · FY{fiscalYear}</p>
            {healthLoading
              ? <div className="skeleton h-24 rounded-xl" />
              : health
                ? <HealthBadge health={health} />
                : <div className={`rounded-xl border ${border} p-4 text-xs ${textSecondary} text-center`}>No data yet</div>
            }
          </div>

          {/* What-if scenarios */}
          {showScenario && (
            <div className={`rounded-xl border ${border} ${bg} overflow-hidden`}>
              <div className={`px-4 py-3 border-b ${border}`}>
                <p className={`text-xs font-semibold uppercase tracking-wider ${textSecondary}`}>Quick Scenarios</p>
              </div>
              <div className="p-3 space-y-2">
                {PRESET_SCENARIOS.map((ps, i) => (
                  <button
                    key={i}
                    onClick={() => runScenario(ps.adjustments)}
                    disabled={scenarioLoading}
                    className={`w-full text-left px-3 py-2 rounded-lg border ${border} text-sm ${textPrimary} hover:border-primary-400 transition-colors`}
                  >
                    <span className="font-medium">{ps.label}</span>
                    <span className={`block text-xs mt-0.5 ${textSecondary}`}>
                      {ps.adjustments.map(a => a.label).join(', ')}
                    </span>
                  </button>
                ))}

                {scenarioLoading && (
                  <div className="flex items-center gap-2 text-xs text-primary-500 p-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Calculating…
                  </div>
                )}

                {scenarioResult && !scenarioLoading && (
                  <div className={`mt-2 rounded-lg border p-3 text-xs ${border} ${bg}`}>
                    <div className="flex items-center gap-2 mb-2">
                      {scenarioResult.calculation?.better_or_worse === 'BETTER'
                        ? <TrendingDown className="w-4 h-4 text-emerald-500" />
                        : <TrendingUp className="w-4 h-4 text-red-500" />
                      }
                      <span className={`font-bold ${scenarioResult.calculation?.better_or_worse === 'BETTER' ? 'text-emerald-600' : 'text-red-600'}`}>
                        {scenarioResult.calculation?.better_or_worse}
                      </span>
                      <span className={textSecondary}>vs baseline</span>
                      <button onClick={() => setScenarioResult(null)} className="ml-auto">
                        <X className={`w-3 h-3 ${textSecondary}`} />
                      </button>
                    </div>
                    <div className={`space-y-1 ${textSecondary}`}>
                      <div className="flex justify-between">
                        <span>Baseline</span><span className="font-mono">{fmtNum(scenarioResult.calculation?.baseline_total || 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Adjusted</span><span className="font-mono font-bold">{fmtNum(scenarioResult.calculation?.adjusted_total || 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Delta</span>
                        <span className={`font-mono font-bold ${(scenarioResult.calculation?.delta || 0) < 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {(scenarioResult.calculation?.delta || 0) > 0 ? '+' : ''}{fmtNum(scenarioResult.calculation?.delta || 0)}
                          {' '}({scenarioResult.calculation?.delta_pct > 0 ? '+' : ''}{scenarioResult.calculation?.delta_pct?.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                    {scenarioResult.narrative && (
                      <div className={`mt-2 pt-2 border-t ${border} text-[11px] ${textSecondary} leading-relaxed`}>
                        {scenarioResult.narrative}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Quick actions */}
          <div className={`rounded-xl border ${border} ${bg} p-3`}>
            <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${textSecondary}`}>Quick Queries</p>
            <div className="space-y-1">
              {[
                [`DWH base + save`, `FY${fiscalYear}: Call get_pl_driver_proposals and get_pl_baseline, then generate_pl_projection with scenario_name "dwh_base", scenario_profile "base", category_adjustments [], assumptions citing DWH source years and historic YoY by category.`],
                [`Stress (anchored)`, `FY${fiscalYear}: get_pl_driver_proposals, get_pl_baseline, then generate_pl_projection scenario_name "bank_stress", scenario_profile "stress", category_adjustments [] — summarize anchor_notes and scenario_tilt_notes.`],
                [`Driver impact`, `What drivers are impacting the FY${fiscalYear} plan most?`],
                [`Plan health`, `How is our FY${fiscalYear} plan looking?`],
              ].map(([label, prompt]) => (
                <button
                  key={label}
                  onClick={() => { setInput(prompt); inputRef.current?.focus(); }}
                  className={`w-full text-left text-xs px-2.5 py-2 rounded-lg hover:bg-primary-50 hover:text-primary-700 dark:hover:bg-slate-800 transition-colors ${textSecondary}`}
                >
                  <Sparkles className="w-3 h-3 inline mr-1.5 opacity-50" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIAssistant;
