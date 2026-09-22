export default function RiskGauge({ score, level }: { score: number; level: string }) {
  const color = level === 'CRITICAL' ? 'text-red-600' : level === 'HIGH' ? 'text-red-500' : level === 'MEDIUM' ? 'text-amber-500' : 'text-emerald-500';
  const bgColor = level === 'CRITICAL' ? 'bg-red-500' : level === 'HIGH' ? 'bg-red-400' : level === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400';

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="text-xs text-slate-500 mb-2">Risk Score</div>
      <div className="flex items-end gap-3">
        <span className={`text-3xl font-bold font-mono ${color}`}>{score.toFixed(0)}</span>
        <span className="text-sm text-slate-400 mb-1">/100</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full mt-2 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${bgColor}`} style={{ width: `${score}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-slate-400 mt-1">
        <span>LOW</span><span>MEDIUM</span><span>HIGH</span><span>CRITICAL</span>
      </div>
    </div>
  );
}
