import { useCallback } from 'react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { demoPipelineStages } from '../data/demoData';

const STAGE_ORDER = ['Camera', 'Preprocessing', 'Vision Processing', 'Sensor Fusion', 'DIVE', 'ATCE', 'Temporal Twin', 'Risk Engine', 'Localization', 'Alert', 'Pipeline'];
const STAGE_METRICS: Record<string, [string, string]> = {
  Camera: ['188 fps', '12 ms'], Preprocessing: ['188 frames/min', '18 ms'], 'Vision Processing': ['94 ROIs/min', '36 ms'], 'Sensor Fusion': ['84 jobs/min', '41 ms'], DIVE: ['31 events/min', '45 ms'], ATCE: ['31 correlations/min', '52 ms'], 'Temporal Twin': ['16 asset states', '19 ms'], 'Risk Engine': ['36 evaluations/min', '57 ms'], Localization: ['14 locates/min', '22 ms'], Alert: ['3 active routes', '9 ms'], Pipeline: ['99.98% delivery', '18 ms'],
};

export default function PipelineView() {
  const { data } = usePolling(useCallback(() => api.getPipelineStatus(), []), 3000);
  const stages = data?.stages?.length ? data.stages : demoPipelineStages;

  const orderedStages = STAGE_ORDER.map(name => {
    const found = stages.find((s: any) => s.name === name);
    return found || { name, status: 'idle', last_event: '', processing_result: '', error_state: null };
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">Data Pipeline</h2>
      <p className="text-sm text-slate-500">Processing chain visualization</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[["INGRESS", "249 fps", "Vision + thermal acquisition"], ["EVENTS", "31/min", "DIVE correlation queue"], ["DECISIONS", "36/min", "ATCE + TDOS evaluation"], ["DELIVERY", "99.98%", "Edge-to-console completion"]].map(([label, value, detail]) => <div key={label} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"><div className="text-[10px] font-mono tracking-wider text-slate-400">{label}</div><div className="mt-1 text-xl font-bold text-slate-800">{value}</div><div className="mt-1 text-[10px] text-slate-500">{detail}</div></div>)}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-7 space-y-0">
        {orderedStages.map((stage: any, i: number) => {
          const statusColor = stage.status === 'completed' ? 'bg-emerald-500' : stage.status === 'processing' ? 'bg-blue-500 animate-pulse' : stage.status === 'error' ? 'bg-red-500' : 'bg-slate-300';
          const borderColor = stage.status === 'completed' ? 'border-emerald-200' : stage.status === 'processing' ? 'border-blue-200' : stage.status === 'error' ? 'border-red-200' : 'border-slate-200';
          return (
            <div key={stage.name}>
              <div className={`bg-white rounded-lg border ${borderColor} p-3 relative`}>
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-700">{stage.name}</div>
                    <div className="text-[10px] text-slate-500 flex gap-3">
                      {stage.processing_result || stage.status}
                      <span className="font-mono text-cyan-600">{STAGE_METRICS[stage.name]?.[0]}</span><span className="font-mono text-slate-400">{STAGE_METRICS[stage.name]?.[1]}</span>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    {stage.last_event ? new Date(stage.last_event).toLocaleTimeString() : '—'}
                  </div>
                </div>
                {stage.error_state && (
                  <div className="text-[10px] text-red-500 mt-1">{stage.error_state}</div>
                )}
              </div>
              {i < orderedStages.length - 1 && (
                <div className="flex justify-center py-0.5">
                  <div className="w-0.5 h-4 bg-slate-200" />
                </div>
              )}
            </div>
          );
        })}
        </div>
        <aside className="col-span-12 lg:col-span-5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between"><div><h3 className="text-sm font-bold text-slate-800">Decision Graph</h3><p className="text-[11px] text-slate-500">Correlated path for EVT-240918-073</p></div><span className="text-[10px] font-mono text-emerald-600">SYNCHRONIZED</span></div>
          <div className="mt-5 space-y-0">{[['Vision + thermal', 'Sensor Fusion', '2 modalities confirm'], ['DIVE event grouping', 'ATCE correlation', '14 observations persist'], ['Temporal Twin', 'Risk Engine', 'Critical state transition'], ['Decision route', 'Alert Console', 'Supervisor response required']].map(([from, to, note], index) => <div key={from}><div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><div className="flex items-center justify-between text-xs"><span className="font-semibold text-slate-700">{from}</span><span className="text-cyan-600">→</span><span className="font-semibold text-slate-700">{to}</span></div><div className="mt-1 text-[10px] font-mono text-slate-500">{note}</div></div>{index < 3 && <div className="ml-6 h-5 border-l-2 border-dashed border-cyan-300"/>}</div>)}</div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center"><div className="rounded bg-cyan-50 p-2"><div className="text-[10px] text-slate-500">Queue</div><div className="font-mono text-sm font-bold text-cyan-700">03</div></div><div className="rounded bg-violet-50 p-2"><div className="text-[10px] text-slate-500">Latency</div><div className="font-mono text-sm font-bold text-violet-700">57ms</div></div><div className="rounded bg-emerald-50 p-2"><div className="text-[10px] text-slate-500">Uptime</div><div className="font-mono text-sm font-bold text-emerald-700">99.98%</div></div></div>
        </aside>
      </div>
    </div>
  );
}
