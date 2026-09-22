interface Props {
  name: string;
  anomalyScore: number;
  confidence: number;
  status: string;
  details?: Record<string, any>;
}

export default function SensorCard({ name, anomalyScore, confidence, status, details }: Props) {
  const barColor = anomalyScore > 0.7 ? 'bg-red-500' : anomalyScore > 0.4 ? 'bg-amber-500' : 'bg-emerald-500';
  const statusColor = status === 'online' ? 'bg-emerald-500' : 'bg-red-500';

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-700">{name}</span>
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
          <span className="text-[10px] text-slate-500 uppercase">{status}</span>
        </div>
      </div>
      <div className="space-y-1.5">
        <div>
          <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
            <span>Anomaly</span>
            <span className="font-mono">{(anomalyScore * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${anomalyScore * 100}%` }} />
          </div>
        </div>
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>Confidence</span>
          <span className="font-mono">{(confidence * 100).toFixed(0)}%</span>
        </div>
        {details && Object.entries(details).slice(0, 2).map(([k, v]) => (
          <div key={k} className="flex justify-between text-[10px] text-slate-500">
            <span>{k.replace(/_/g, ' ')}</span>
            <span className="font-mono">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
