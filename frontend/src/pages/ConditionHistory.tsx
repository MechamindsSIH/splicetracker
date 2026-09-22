import { useCallback } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import StatusBadge from '../components/StatusBadge';
import { demoAnalytics } from '../data/demoData';

export default function ConditionHistory() {
  const { data } = usePolling(useCallback(() => api.getAnalytics(), []), 10000);
  const trends = data?.condition_trends?.length ? data.condition_trends : demoAnalytics.condition_trends;
  const condLevels = ['NORMAL', 'MINOR_ANOMALY', 'WARNING', 'DEGRADING', 'HIGH_RISK', 'CRITICAL'];
  const chartData = trends.map((t: any) => ({
    name: new Date(t.timestamp).toLocaleTimeString(),
    value: condLevels.indexOf(t.condition),
    condition: t.condition,
    splice: t.splice_id,
  }));

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">Condition History</h2>

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs text-slate-500 mb-3">Condition Over Time</h3>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} ticks={[0,1,2,3,4,5]} tickFormatter={(v) => condLevels[v]?.substring(0, 3) || ''} />
              <Tooltip formatter={(value: any) => condLevels[value as number] || value} />
              <Area type="stepAfter" dataKey="value" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-400 text-center py-12">No condition history — start a simulation</p>
        )}
      </div>

      {chartData.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Recent Changes</h3>
          <div className="space-y-1">
            {chartData.slice(-20).reverse().map((d: any, i: number) => (
              <div key={i} className="flex items-center gap-3 py-1 px-2 rounded hover:bg-slate-50 text-xs">
                <span className="font-mono text-slate-400 w-20">{d.name}</span>
                <StatusBadge value={d.condition} size="xs" />
                <span className="text-slate-400">Splice {d.splice}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
