import React, { useEffect, useState } from 'react';
import { Check, FlaskConical, RefreshCw, Rocket, Save } from 'lucide-react';
import { driversAPI } from '../../services/api';

type Driver = { id: number; code: string; name_en: string };
type MetadataLogic = {
  id: number;
  driver_id: number;
  code: string;
  name: string;
  formula_expr: string;
  version: number;
  is_active: boolean;
  is_published: boolean;
  published_at?: string | null;
};

const MetadataLogicV2Page = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [rows, setRows] = useState<MetadataLogic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [form, setForm] = useState({
    driver_id: null as number | null,
    code: '',
    name: '',
    formula_expr: 'baseline * (1 + rate / 100)',
  });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [driverData, metadataData] = await Promise.all([
        driversAPI.list({ is_active: true }),
        driversAPI.listMetadataLogic(),
      ]);
      setDrivers(driverData || []);
      setRows(metadataData || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load metadata logic');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await driversAPI.createMetadataLogic(form);
      setMessage('Metadata logic created. Validate and publish it.');
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Create failed');
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async (row: MetadataLogic) => {
    setError(null);
    setMessage(null);
    try {
      const res = await driversAPI.validateMetadataLogic(row.id, {
        formula_expr: row.formula_expr,
        sample_context: { baseline: 1000, rate: 10, month: 1 },
      });
      if (res?.is_valid) {
        setMessage(`Formula valid for ${row.code}. Sample result: ${res.sample_result}`);
      } else {
        setError(res?.message || 'Validation failed');
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Validation failed');
    }
  };

  const handlePublish = async (row: MetadataLogic) => {
    setError(null);
    setMessage(null);
    try {
      await driversAPI.publishMetadataLogic(row.id);
      setMessage(`Published ${row.code} (v${row.version})`);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Publish failed');
    }
  };

  const handleSeedDefaults = async () => {
    setError(null);
    setMessage(null);
    try {
      const res = await driversAPI.seedMetadataLogic();
      setMessage(`Seed complete. Created: ${res?.created ?? 0}, Skipped: ${res?.skipped ?? 0}`);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Seed failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Metadata Logic V2 (Test)</h1>
          <p className="text-gray-600 mt-1">Create, validate, and publish formula logic for drivers.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="px-3 py-2 border rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className="w-4 h-4 inline mr-1" /> Refresh
          </button>
          <button onClick={handleSeedDefaults} className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700">
            <FlaskConical className="w-4 h-4 inline mr-1" /> Seed Defaults
          </button>
        </div>
      </div>

      {error && <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700">{error}</div>}
      {message && <div className="p-3 rounded-lg border border-green-200 bg-green-50 text-green-700">{message}</div>}

      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="font-semibold text-gray-900">Create Metadata Logic</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-700 mb-1">Driver</label>
            <select
              value={form.driver_id ?? ''}
              onChange={(e) => {
                const id = e.target.value ? Number(e.target.value) : null;
                const d = drivers.find((x) => x.id === id);
                setForm((f) => ({
                  ...f,
                  driver_id: id,
                  code: d?.code || f.code,
                  name: d?.name_en || f.name,
                }));
              }}
              className="w-full border rounded-lg px-3 py-2"
            >
              <option value="">No linked driver (manual test)</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>{d.code} - {d.name_en}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Code</label>
            <input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} className="w-full border rounded-lg px-3 py-2" />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Name</label>
            <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="w-full border rounded-lg px-3 py-2" />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Formula</label>
            <input value={form.formula_expr} onChange={(e) => setForm((f) => ({ ...f, formula_expr: e.target.value }))} className="w-full border rounded-lg px-3 py-2 font-mono" />
          </div>
        </div>
        <button
          disabled={saving || !form.code || !form.formula_expr}
          onClick={handleCreate}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-60"
        >
          <Save className="w-4 h-4 inline mr-1" /> Create
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 font-semibold text-gray-900">Existing Metadata Logic</div>
        {loading ? (
          <div className="p-6 text-gray-500">Loading...</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-gray-500">No metadata logic rows yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3">Code</th>
                  <th className="text-left px-4 py-3">Version</th>
                  <th className="text-left px-4 py-3">Formula</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-3 font-medium">{r.code}</td>
                    <td className="px-4 py-3">v{r.version}</td>
                    <td className="px-4 py-3 font-mono text-xs">{r.formula_expr}</td>
                    <td className="px-4 py-3">
                      {r.is_published ? (
                        <span className="inline-flex items-center gap-1 text-green-700"><Check className="w-4 h-4" /> Published</span>
                      ) : (
                        <span className="text-amber-700">Draft</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => handleValidate(r)} className="px-2 py-1 border rounded hover:bg-gray-50">
                          <FlaskConical className="w-4 h-4 inline mr-1" /> Validate
                        </button>
                        <button onClick={() => handlePublish(r)} className="px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700">
                          <Rocket className="w-4 h-4 inline mr-1" /> Publish
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetadataLogicV2Page;
