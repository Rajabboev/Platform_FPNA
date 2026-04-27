import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Check, ExternalLink, Loader2, RefreshCw } from 'lucide-react';
import { reportingAPI } from '../services/api';

const PBI_URL_KEY = 'analytics_powerbi_embed_url';

const looksLikeUrl = (value: string): boolean => {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
};

export const AnalysisDashboard = () => {
  const [embedUrlInput, setEmbedUrlInput] = useState('');
  const [activeEmbedUrl, setActiveEmbedUrl] = useState('');
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const hasValidInput = useMemo(() => looksLikeUrl(embedUrlInput.trim()), [embedUrlInput]);
  const hasActiveEmbed = useMemo(() => looksLikeUrl(activeEmbedUrl.trim()), [activeEmbedUrl]);

  useEffect(() => {
    const loadConfig = async () => {
      setLoadingConfig(true);
      setError(null);
      try {
        const cfg = await reportingAPI.getPowerBIConfig().catch(() => ({}));
        const backendUrl = (cfg?.workspace_url || '').trim();
        const localUrl = (window.localStorage.getItem(PBI_URL_KEY) || '').trim();
        const initialUrl = backendUrl || localUrl;
        setEmbedUrlInput(initialUrl);
        setActiveEmbedUrl(initialUrl);
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Failed to load Power BI configuration');
      } finally {
        setLoadingConfig(false);
      }
    };
    loadConfig();
  }, []);

  const handleSaveAndLoad = async () => {
    const nextUrl = embedUrlInput.trim();
    if (!looksLikeUrl(nextUrl)) {
      setError('Enter a valid http(s) embed URL.');
      setSuccess(null);
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await reportingAPI.savePowerBIConfig({ workspace_url: nextUrl }).catch(() => null);
      window.localStorage.setItem(PBI_URL_KEY, nextUrl);
      setActiveEmbedUrl(nextUrl);
      setSuccess('Power BI embed URL updated.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save embed URL');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500 mt-0.5">Embedded Power BI report</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
          title="Reload page"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <Check className="w-4 h-4 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Power BI embed link</label>
        <div className="flex items-center gap-2">
          <input
            value={embedUrlInput}
            onChange={(e) => setEmbedUrlInput(e.target.value)}
            placeholder="https://app.powerbi.com/reportEmbed?..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          <button
            onClick={handleSaveAndLoad}
            disabled={saving || !hasValidInput}
            className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Load'}
          </button>
          {hasActiveEmbed && (
            <a
              href={activeEmbedUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
            >
              <ExternalLink className="w-4 h-4" /> Open
            </a>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loadingConfig ? (
          <div className="h-[70vh] flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
          </div>
        ) : hasActiveEmbed ? (
          <iframe
            title="Power BI Analytics"
            src={activeEmbedUrl}
            className="w-full h-[76vh]"
            allowFullScreen
          />
        ) : (
          <div className="h-[70vh] flex items-center justify-center text-center px-6">
            <div>
              <p className="text-gray-900 font-medium">No Power BI embed URL set.</p>
              <p className="text-gray-500 text-sm mt-1">
                Paste your report embed link above and click Load.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisDashboard;
