import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Layers, Grid, Cpu, ArrowUpRight } from 'lucide-react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import StatusBadge from '../components/StatusBadge';
import SpliceTracker3DScene from '../components/3d/SpliceTracker3DScene';
import { demoSplices } from '../data/demoData';

export default function TemporalTwin() {
  const { data } = usePolling(useCallback(() => api.getSplices(), []), 5000);
  const splices = data?.splices?.length ? data.splices : demoSplices;

  const [viewMode, setViewMode] = useState<'3d' | 'grid'>('3d');
  const [selectedBelt, setSelectedBelt] = useState<string>('ALL');
  const [activeSpliceId, setActiveSpliceId] = useState<number | null>(null);

  const filteredSplices = selectedBelt === 'ALL' ? splices : splices.filter((s: any) => s.belt_id === selectedBelt);
  const activeSplice = splices.find((s: any) => s.id === activeSpliceId) || filteredSplices[0] || splices[0];

  const belts = Array.from(new Set(splices.map((s: any) => s.belt_id))).sort();

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Cpu size={20} className="text-blue-600" />
            Temporal Digital Twin
          </h2>
          <p className="text-xs text-slate-500">
            Real-time physical asset replication with per-splice condition state machine
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Belt Asset Filter */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 border border-slate-200 text-xs">
            <button
              onClick={() => setSelectedBelt('ALL')}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                selectedBelt === 'ALL' ? 'bg-white text-blue-700 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Belts ({splices.length})
            </button>
            {belts.map((b: any) => (
              <button
                key={b}
                onClick={() => setSelectedBelt(b)}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  selectedBelt === b ? 'bg-white text-blue-700 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {b}
              </button>
            ))}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 border border-slate-200 text-xs">
            <button
              onClick={() => setViewMode('3d')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                viewMode === '3d' ? 'bg-blue-600 text-white shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Layers size={14} />
              3D Twin
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                viewMode === 'grid' ? 'bg-blue-600 text-white shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Grid size={14} />
              State Grid
            </button>
          </div>
        </div>
      </div>

      {splices.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-400">
          No splices available — database seeding in progress
        </div>
      ) : viewMode === '3d' ? (
        /* 3D Digital Twin View */
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12 lg:col-span-8 h-[540px] rounded-xl overflow-hidden shadow-sm">
            <SpliceTracker3DScene
              activeSpliceName={activeSplice?.name || 'Splice-001'}
              activeStatus={
                activeSplice?.condition === 'CRITICAL'
                  ? 'CRITICAL'
                  : activeSplice?.condition === 'POOR' || activeSplice?.condition === 'DEGRADED'
                  ? 'WARNING'
                  : 'NORMAL'
              }
              cameraPreset="overview"
            />
          </div>

          {/* Splice Selector Sidebar */}
          <div className="col-span-12 lg:col-span-4 flex flex-col h-[540px] bg-white rounded-xl border border-slate-200 p-3 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 mb-2">
              <span className="text-xs font-bold text-slate-700">Digital Twin Splices</span>
              <Link to="/architecture" className="text-xs text-blue-600 hover:underline flex items-center gap-0.5">
                Full 3D Architecture <ArrowUpRight size={12} />
              </Link>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {filteredSplices.map((s: any) => {
                const isSelected = activeSplice?.id === s.id;
                return (
                  <div
                    key={s.id}
                    onClick={() => setActiveSpliceId(s.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50/50 shadow-sm ring-1 ring-blue-400'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-800">{s.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">({s.belt_id})</span>
                      </div>
                      <StatusBadge value={s.condition || 'NORMAL'} size="xs" />
                    </div>

                    <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-500">
                      <div>Position: <span className="font-mono text-slate-700">{s.position.toFixed(1)}m</span></div>
                      <div>Severity: <span className="font-mono text-slate-700">{(s.severity * 100).toFixed(1)}%</span></div>
                    </div>

                    {/* Condition state bar */}
                    <div className="mt-2 flex items-center gap-1">
                      {['NORMAL', 'MINOR_ANOMALY', 'WARNING', 'DEGRADING', 'HIGH_RISK', 'CRITICAL'].map((level, i) => {
                        const active = level === (s.condition || 'NORMAL');
                        const colors = ['bg-emerald-400', 'bg-yellow-400', 'bg-amber-400', 'bg-orange-400', 'bg-red-400', 'bg-red-600'];
                        return (
                          <div
                            key={level}
                            className={`h-1.5 flex-1 rounded-sm ${active ? colors[i] : 'bg-slate-100'}`}
                            title={level}
                          />
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        /* State Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {filteredSplices.map((s: any) => (
            <Link
              key={s.id}
              to={`/splice/${s.id}`}
              className="bg-white rounded-lg border border-slate-200 p-4 hover:border-blue-300 transition-colors shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-bold text-slate-800">{s.name}</span>
                  <div className="text-[10px] text-slate-400 font-mono">{s.belt_id}</div>
                </div>
                <StatusBadge value={s.condition || 'NORMAL'} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div>Severity: <StatusBadge value={s.severity || 'NONE'} size="xs" /></div>
                <div>Risk: <StatusBadge value={s.risk_level || 'LOW'} size="xs" /></div>
                <div>Confidence: <span className="font-mono">{((s.confidence || 0) * 100).toFixed(0)}%</span></div>
                <div>Position: <span className="font-mono">{s.position?.toFixed(1)}m</span></div>
              </div>
              <div className="mt-3 pt-2 border-t border-slate-100">
                <div className="flex items-center gap-1">
                  {['NORMAL', 'MINOR_ANOMALY', 'WARNING', 'DEGRADING', 'HIGH_RISK', 'CRITICAL'].map((level, i) => {
                    const active = level === (s.condition || 'NORMAL');
                    const colors = ['bg-emerald-400', 'bg-yellow-400', 'bg-amber-400', 'bg-orange-400', 'bg-red-400', 'bg-red-600'];
                    return (
                      <div key={level} className={`h-2 flex-1 rounded-sm ${active ? colors[i] : 'bg-slate-100'}`} title={level} />
                    );
                  })}
                </div>
                <div className="flex justify-between text-[8px] text-slate-400 mt-0.5">
                  <span>NOR</span>
                  <span>CRT</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
