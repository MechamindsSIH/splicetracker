import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { useWebSocket } from '../hooks/useWebSocket';
import SensorCard from '../components/SensorCard';
import StatusBadge from '../components/StatusBadge';
import { demoStatus } from '../data/demoData';

const baselineInspection = {
  splice_id: 'Splice-202',
  fusion_result: { vision_score: 0.91, thermal_score: 0.78, mechanical_score: 0.66, conductive_score: 0.84, fusion_status: 'CORROBORATED', overall_confidence: 0.94, supporting_sensors: ['Vision', 'Thermal', 'Mechanical', 'Conductive'] },
  dive_event: { event_id: 'EVT-240918-073', event_type: 'SPLICE_SEPARATION', persistence_count: 14, status: 'ACTIVE' },
  atce_result: { trend: 'RAPID_DEGRADATION', persistence: 14, classification: 'MULTI-SENSOR CONFIRMED' },
  twin_state: { condition: 'CRITICAL' },
  risk_result: { risk_score: 91, risk_level: 'CRITICAL', recommended_action: 'Hold the next planned load increase and schedule an expedited inspection.' },
};

export default function LiveInspection() {
  const { data: status } = usePolling(useCallback(() => api.getSystemStatus(), []), 5000);
  const { subscribe } = useWebSocket();
  const [latestResult, setLatestResult] = useState<any>(null);
  const [frameCount, setFrameCount] = useState(0);

  useEffect(() => {
    const unsub = subscribe('inspection_completed', (p: any) => {
      setLatestResult(p.result || p);
      setFrameCount(c => c + 1);
    });
    return unsub;
  }, [subscribe]);

  const components = status?.components || demoStatus.components;
  const inspection = latestResult || baselineInspection;
  const vision = inspection.fusion_result || {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        {/* Camera Area */}
        <div className="col-span-12 xl:col-span-7 bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-medium text-slate-700">Live Camera Feed</h3>
            <span className="text-[10px] font-mono text-slate-400">Frames: {(frameCount || 18421).toLocaleString()}</span>
          </div>
          <div className="relative aspect-video overflow-hidden rounded-lg bg-[#07131f] font-mono">
            <div className="absolute inset-0 opacity-30" style={{ backgroundImage: 'linear-gradient(90deg, transparent 49.7%, #38bdf8 50%, transparent 50.3%), linear-gradient(0deg, transparent 49.7%, #38bdf8 50%, transparent 50.3%), repeating-linear-gradient(0deg, transparent 0 5px, rgba(56,189,248,.18) 6px)' }} />
            <div className="absolute left-[8%] right-[5%] top-[38%] h-[28%] -skew-y-6 rounded-sm border-y-8 border-slate-400 bg-gradient-to-r from-slate-700 via-slate-500 to-slate-700 shadow-[0_14px_20px_rgba(0,0,0,.5)]" />
            <div className="absolute left-[49%] top-[34%] h-[35%] w-[16%] -skew-y-6 border-2 border-rose-400 bg-rose-500/20 shadow-[0_0_20px_rgba(251,113,133,.55)]" />
            <div className="absolute left-[52%] top-[33%] h-[39%] w-px bg-cyan-300 shadow-[0_0_14px_3px_rgba(103,232,249,.8)] animate-pulse" />
            <div className="absolute left-3 top-3 rounded bg-slate-950/80 px-2 py-1 text-[10px] text-cyan-300 border border-cyan-800">OPTI-SCAN 8K · CAM-204</div>
            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded bg-rose-950/70 px-2 py-1 text-[10px] text-rose-200 border border-rose-700"><span className="h-1.5 w-1.5 rounded-full bg-rose-400 animate-pulse" />ANOMALY ROI LOCKED</div>
            <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between text-[10px] text-slate-300"><div className="rounded bg-slate-950/80 p-2 leading-5 border border-slate-700">SPLICE {inspection.splice_id}<br/><span className="text-cyan-300">POSITION 180.0 m</span></div><div className="rounded bg-slate-950/80 p-2 text-right leading-5 border border-slate-700">DEFECT: SPLICE SEPARATION<br/><span className="text-rose-300">CONFIDENCE 94%</span></div></div>
          </div>
        </div>

        {/* Sensor Status */}
        <div className="col-span-12 xl:col-span-5 space-y-3">
          <h3 className="text-sm font-medium text-slate-700">Sensor Readings</h3>
          <div className="grid grid-cols-2 gap-3">
            {['vision', 'thermal', 'mechanical', 'conductive'].map(s => (
              <SensorCard
                key={s}
                name={s.charAt(0).toUpperCase() + s.slice(1)}
                anomalyScore={vision[`${s}_score`] || 0}
                confidence={0.85}
                status={components[s] || 'offline'}
              />
            ))}
          </div>
          {inspection.dive_event && (
            <div className="bg-gradient-to-br from-violet-50 to-white rounded-lg border border-violet-200 p-3">
              <h4 className="text-xs text-slate-500 mb-1">DIVE Event</h4>
              <div className="text-xs space-y-1 text-slate-600">
                <div>ID: <span className="font-mono">{inspection.dive_event.event_id}</span></div>
                <div>Type: {inspection.dive_event.event_type}</div>
                <div>Persistence: {inspection.dive_event.persistence_count} correlated observations</div>
                <div>Status: <StatusBadge value={inspection.dive_event.status || 'ACTIVE'} size="xs" /></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detection Results */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-3">
            <h4 className="text-xs text-slate-500 mb-2">Fusion</h4>
            <div className="text-xs space-y-1 text-slate-600">
              <div>Status: <StatusBadge value={inspection.fusion_result?.fusion_status || 'N/A'} size="xs" /></div>
              <div>Confidence: <span className="font-mono">{((inspection.fusion_result?.overall_confidence || 0) * 100).toFixed(0)}%</span></div>
              <div>Supporting: {inspection.fusion_result?.supporting_sensors?.join(', ') || 'none'}</div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-3">
            <h4 className="text-xs text-slate-500 mb-2">ATCE Temporal</h4>
            <div className="text-xs space-y-1 text-slate-600">
              <div>Trend: <StatusBadge value={inspection.atce_result?.trend || 'STABLE'} size="xs" /></div>
              <div>Persistence: {inspection.atce_result?.persistence || 0}</div>
              <div>Classification: {inspection.atce_result?.classification || 'N/A'}</div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-3">
            <h4 className="text-xs text-slate-500 mb-2">Risk</h4>
            <div className="text-xs space-y-1 text-slate-600">
              <div>Score: <span className="font-mono text-lg font-bold">{inspection.risk_result?.risk_score?.toFixed(0) || 0}</span>/100</div>
              <div>Level: <StatusBadge value={inspection.risk_result?.risk_level || 'LOW'} /></div>
              <div className="text-[10px] italic">{inspection.risk_result?.recommended_action || ''}</div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-3">
            <h4 className="text-xs text-slate-500 mb-2">TDOS Operating State</h4>
            <div className="text-xs space-y-1 text-slate-600"><div>State: <StatusBadge value={inspection.twin_state?.condition || 'NORMAL'} size="xs" /></div><div>Asset: BELT-03 / STAGING</div><div>Transition: HIGH RISK → CRITICAL</div><div className="text-[10px] text-violet-600 font-medium">Temporal decision layer synchronized</div></div>
          </div>
        </div>
    </div>
  );
}
