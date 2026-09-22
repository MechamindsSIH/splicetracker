import { useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorDisplay from '../components/ErrorDisplay';

export default function SpliceDetail() {
  const { id } = useParams<{ id: string }>();
  const spliceId = parseInt(id || '1');
  const { data, loading, error, refetch } = usePolling(useCallback(() => api.getSplice(spliceId), [spliceId]), 5000);
  const { data: historyData } = usePolling(useCallback(() => api.getSpliceHistory(spliceId), [spliceId]), 5000);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorDisplay message={error} onRetry={refetch} />;

  const splice = data?.splice || data;
  const twin = data?.twin_state;
  const history = historyData?.history || [];
  const condLevels = ['NORMAL', 'MINOR_ANOMALY', 'WARNING', 'DEGRADING', 'HIGH_RISK', 'CRITICAL'];
  const chartData = history.map((h: any) => ({
    name: new Date(h.timestamp).toLocaleTimeString(),
    value: condLevels.indexOf(h.condition),
  }));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-blue-500 hover:underline">&larr; Back</Link>
        <h2 className="text-lg font-bold text-slate-800">{splice?.name || `Splice ${spliceId}`}</h2>
        {splice?.condition && <StatusBadge value={splice.condition} />}
        {splice?.risk_level && <StatusBadge value={splice.risk_level} />}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Splice Information</h3>
          <dl className="space-y-2 text-sm">
            {[
              ['ID', splice?.id],
              ['Name', splice?.name],
              ['Belt', splice?.belt_id],
              ['Position', `${splice?.position?.toFixed(1) || 0}m`],
              ['Condition', splice?.condition],
              ['Severity', splice?.severity],
              ['Confidence', `${((splice?.confidence || 0) * 100).toFixed(0)}%`],
              ['Risk Level', splice?.risk_level],
            ].map(([label, val]) => (
              <div key={String(label)} className="flex justify-between">
                <dt className="text-slate-500">{label}</dt>
                <dd className="font-mono text-slate-700">{String(val || 'N/A')}</dd>
              </div>
            ))}
          </dl>
        </div>

        {twin && (
          <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
            <h3 className="text-xs text-slate-500 mb-3">Digital Twin State</h3>
            <dl className="space-y-2 text-sm">
              {[
                ['Condition', twin.condition],
                ['Severity', twin.severity],
                ['Trend', twin.trend],
                ['Confidence', `${((twin.confidence || 0) * 100).toFixed(0)}%`],
                ['Risk', twin.risk_level],
                ['Events', twin.event_count || 0],
              ].map(([label, val]) => (
                <div key={String(label)} className="flex justify-between">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="font-mono text-slate-700">{typeof val === 'string' ? <StatusBadge value={val} size="xs" /> : String(val)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Condition History</h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} ticks={[0,1,2,3,4,5]} tickFormatter={(v) => ['NOR','MIN','WRN','DEG','HI','CRT'][v] || ''} />
                <Tooltip />
                <Line type="stepAfter" dataKey="value" stroke="#3b82f6" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No history data</p>
          )}
        </div>
      </div>

      {history.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Timeline</h3>
          <div className="space-y-1">
            {history.slice(-20).reverse().map((h: any, i: number) => (
              <div key={i} className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-slate-50 text-xs">
                <span className="font-mono text-slate-400 w-20">{new Date(h.timestamp).toLocaleTimeString()}</span>
                <StatusBadge value={h.condition} size="xs" />
                {h.previous && <span className="text-slate-400">&larr; {h.previous}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
