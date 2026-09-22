import type { FusionResult } from '../types';

export default function FusionDisplay({ fusion }: { fusion: FusionResult | null }) {
  if (!fusion) return <div className="text-sm text-slate-400">No fusion data</div>;

  const sensors = [
    { name: 'Vision', score: fusion.vision_score },
    { name: 'Thermal', score: fusion.thermal_score },
    { name: 'Mechanical', score: fusion.mechanical_score },
    { name: 'Conductive', score: fusion.conductive_score },
  ];

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="text-xs text-slate-500 mb-2">Sensor Fusion</div>
      <div className="space-y-1.5">
        {sensors.map((s) => {
          const isSupporting = fusion.supporting_sensors?.includes(s.name.toLowerCase());
          return (
            <div key={s.name} className="flex items-center gap-2">
              <span className={`text-sm ${isSupporting ? 'text-red-500' : 'text-emerald-500'}`}>
                {isSupporting ? '!' : '✓'}
              </span>
              <span className="text-xs text-slate-600 w-20">{s.name}</span>
              <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${s.score > 0.5 ? 'bg-red-400' : 'bg-emerald-400'}`}
                  style={{ width: `${s.score * 100}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-slate-500 w-8 text-right">
                {(s.score * 100).toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 pt-2 border-t border-slate-100 flex justify-between text-[10px]">
        <span className="text-slate-500">
          Supporting: {fusion.supporting_sensors?.length || 0}/4
        </span>
        <span className="text-slate-500">
          Confidence: {(fusion.overall_confidence * 100).toFixed(0)}%
        </span>
        <span className={`font-medium ${fusion.fusion_status?.includes('HIGH') ? 'text-red-600' : 'text-slate-600'}`}>
          {fusion.fusion_status?.replace(/_/g, ' ')}
        </span>
      </div>
    </div>
  );
}
