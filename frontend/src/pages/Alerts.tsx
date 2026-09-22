import { useState, useCallback } from 'react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import StatusBadge from '../components/StatusBadge';
import { demoAlerts } from '../data/demoData';

export default function Alerts() {
  const [filter, setFilter] = useState<string>('');
  const { data, refetch } = usePolling(useCallback(() => api.getAlerts({ status: filter || undefined }), [filter]), 5000);

  const alerts = data?.alerts?.length ? data.alerts : demoAlerts.filter(alert => !filter || alert.status === filter);

  const handleAcknowledge = async (id: number) => {
    try {
      await api.acknowledgeAlert(id);
      refetch();
    } catch {}
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold text-slate-800">Alerts</h2>
        <div className="flex gap-1">
          {['', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'].map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`text-xs px-2.5 py-1 rounded ${filter === s ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      {alerts.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-400">No alerts found</div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">ID</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Severity</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Splice</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Reason</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Risk</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Status</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Time</th>
                <th className="text-left px-3 py-2 text-xs text-slate-500 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a: any) => (
                <tr key={a.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">#{a.id}</td>
                  <td className="px-3 py-2"><StatusBadge value={a.severity} size="xs" /></td>
                  <td className="px-3 py-2 text-xs">{a.splice_id}</td>
                  <td className="px-3 py-2 text-xs text-slate-600 max-w-xs truncate">{a.reason}</td>
                  <td className="px-3 py-2 font-mono text-xs">{a.risk_score}</td>
                  <td className="px-3 py-2"><StatusBadge value={a.status} size="xs" /></td>
                  <td className="px-3 py-2 font-mono text-[10px] text-slate-400">{new Date(a.timestamp).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    {a.status === 'ACTIVE' && (
                      <button onClick={() => handleAcknowledge(a.id)} className="text-[10px] px-2 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
                        Ack
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
