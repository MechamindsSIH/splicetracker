import { useCallback } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { demoAnalytics } from '../data/demoData';
import { demoAnomalies } from '../data/demoData';

const COLORS = ['#10b981', '#f59e0b', '#ef4444', '#dc2626'];

export default function Analytics() {
  const { data } = usePolling(useCallback(() => api.getAnalytics(), []), 10000);
  const analytics = data || demoAnalytics;
  const riskDist = analytics.risk_distribution || {};
  const riskData = Object.entries(riskDist).map(([name, value]) => ({ name, value: value as number }));
  const defectFreq = analytics.defect_frequency || {};
  const defectData = Object.entries(defectFreq).map(([name, value]) => ({ name, value: value as number }));
  const trends = analytics.condition_trends || [];
  const trendData = trends.slice(-30).map((t: any, i: number) => ({
    name: new Date(t.timestamp).toLocaleTimeString(),
    condition: ['NORMAL','MINOR_ANOMALY','WARNING','DEGRADING','HIGH_RISK','CRITICAL'].indexOf(t.condition),
  }));

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">Analytics</h2>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Inspections', value: analytics.inspection_count || analytics.total_inspections || 0, color: 'text-blue-600' },
          { label: 'Total Anomalies', value: analytics.anomaly_count || analytics.total_anomalies || 0, color: 'text-amber-600' },
          { label: 'Total Alerts', value: analytics.alert_count || analytics.total_alerts || 0, color: 'text-red-600' },
          { label: 'Avg Risk', value: riskData.length > 0 ? Math.round(riskData.reduce((a, b) => a + b.value, 0) / riskData.length) : 0, color: 'text-slate-600' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="text-xs text-slate-500">{s.label}</div>
            <div className={`text-3xl font-bold font-mono mt-1 ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Risk Distribution</h3>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={riskData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                  {riskData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-slate-400 text-center py-8">No data</p>}
        </div>

        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Defect Frequency</h3>
          {defectData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={defectData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-slate-400 text-center py-8">No data</p>}
        </div>

        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Condition Trend</h3>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} domain={[0, 5]} />
                <Tooltip />
                <Line type="monotone" dataKey="condition" stroke="#ef4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-slate-400 text-center py-8">No data</p>}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3"><div><h3 className="text-sm font-bold text-slate-800">Anomaly Evidence Ledger</h3><p className="text-[11px] text-slate-500">Corroborated detections ranked by confidence and operational impact</p></div><span className="rounded-full bg-rose-50 px-2.5 py-1 text-[10px] font-mono font-bold text-rose-700">6 ACTIVE SIGNALS</span></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Event','Source','Detection','Location','Confidence','Priority'].map(item => <th key={item} className="px-4 py-2.5 text-left font-semibold">{item}</th>)}</tr></thead><tbody>{demoAnomalies.map(([id, source, detection, location, confidence, priority]) => <tr key={id} className="border-t border-slate-100 hover:bg-slate-50"><td className="px-4 py-3 font-mono text-slate-500">{id}</td><td className="px-4 py-3 font-semibold text-slate-700">{source}</td><td className="px-4 py-3 text-slate-600">{detection}</td><td className="px-4 py-3 font-mono text-slate-500">{location}</td><td className="px-4 py-3 font-mono text-cyan-700">{confidence}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${priority === 'CRITICAL' ? 'bg-rose-100 text-rose-700' : priority === 'HIGH' ? 'bg-orange-100 text-orange-700' : 'bg-amber-100 text-amber-700'}`}>{priority}</span></td></tr>)}</tbody></table></div>
      </div>
    </div>
  );
}
