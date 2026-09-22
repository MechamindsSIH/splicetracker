import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

export default function Settings() {
  const [config, setConfig] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.updateConfig(config);
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  };

  const fields = [
    { key: 'camera_index', label: 'Camera Index', type: 'number' },
    { key: 'camera_width', label: 'Camera Width', type: 'number' },
    { key: 'camera_height', label: 'Camera Height', type: 'number' },
    { key: 'camera_fps', label: 'Camera FPS', type: 'number' },
    { key: 'thermal_enabled', label: 'Thermal Enabled', type: 'checkbox' },
    { key: 'conductive_enabled', label: 'Conductive Enabled', type: 'checkbox' },
    { key: 'mechanical_enabled', label: 'Mechanical Enabled', type: 'checkbox' },
    { key: 'belt_speed', label: 'Belt Speed (m/s)', type: 'number' },
    { key: 'belt_length', label: 'Belt Length (m)', type: 'number' },
    { key: 'simulation_mode', label: 'Simulation Mode', type: 'checkbox' },
    { key: 'log_level', label: 'Log Level', type: 'text' },
  ];

  return (
    <div className="space-y-4 max-w-2xl">
      <h2 className="text-lg font-bold text-slate-800">Settings</h2>

      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-4">
        {fields.map(f => (
          <div key={f.key} className="flex items-center justify-between">
            <label className="text-sm text-slate-600">{f.label}</label>
            {f.type === 'checkbox' ? (
              <input
                type="checkbox"
                checked={!!config[f.key]}
                onChange={e => setConfig({ ...config, [f.key]: e.target.checked })}
                className="w-4 h-4"
              />
            ) : (
              <input
                type={f.type}
                value={config[f.key] ?? ''}
                onChange={e => setConfig({ ...config, [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                className="w-40 px-2 py-1 text-sm border border-slate-200 rounded font-mono"
              />
            )}
          </div>
        ))}

        <div className="flex items-center gap-3 pt-3 border-t border-slate-200">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          {saved && <span className="text-sm text-emerald-500">Saved!</span>}
        </div>
      </div>
    </div>
  );
}
