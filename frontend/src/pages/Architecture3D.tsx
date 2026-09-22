import { useState, useEffect, useCallback } from 'react';
import {
  Layers,
  Camera,
  Play,
  Pause,
  Maximize2,
  Activity,
  Cpu,
  Eye,
  Radio,
  Wifi,
  ChevronRight,
  Database,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Gauge,
  Sliders,
} from 'lucide-react';
import SpliceTracker3DScene, { ComponentDetail } from '../components/3d/SpliceTracker3DScene';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';

export default function Architecture3D() {
  const { data: splicesData } = usePolling(useCallback(() => api.getSplices(), []), 5000);
  const { data: systemStatus } = usePolling(useCallback(() => api.getSystemStatus(), []), 5000);

  const [selectedBelt, setSelectedBelt] = useState('BELT-01');
  const [selectedSpliceId, setSelectedSpliceId] = useState<number | null>(null);
  const [cameraPreset, setCameraPreset] = useState<'overview' | 'inspection' | 'splice' | 'edge' | 'topdown'>('overview');
  const [beltRunning, setBeltRunning] = useState(true);
  const [showDataFlow, setShowDataFlow] = useState(true);
  const [showAiOverlay, setShowAiOverlay] = useState(true);
  const [selectedComponent, setSelectedComponent] = useState<ComponentDetail | null>(null);
  const [simulatedStatus, setSimulatedStatus] = useState<'AUTO' | 'NORMAL' | 'WARNING' | 'CRITICAL'>('AUTO');

  const splices = splicesData?.splices || [];
  const beltSplices = splices.filter((s: any) => s.belt_id === selectedBelt);
  const activeSplice = beltSplices.find((s: any) => s.id === selectedSpliceId) || beltSplices[0] || splices[0];

  // Derive active 3D status from activeSplice or manual simulation override
  let effectiveStatus: 'NORMAL' | 'WARNING' | 'CRITICAL' = 'NORMAL';
  if (simulatedStatus !== 'AUTO') {
    effectiveStatus = simulatedStatus;
  } else if (activeSplice) {
    if (activeSplice.condition === 'CRITICAL' || activeSplice.severity > 0.8) {
      effectiveStatus = 'CRITICAL';
    } else if (activeSplice.condition === 'POOR' || activeSplice.condition === 'DEGRADED' || activeSplice.severity > 0.4) {
      effectiveStatus = 'WARNING';
    } else {
      effectiveStatus = 'NORMAL';
    }
  }

  // Set initial selected splice when splices load
  useEffect(() => {
    if (beltSplices.length > 0 && !selectedSpliceId) {
      setSelectedSpliceId(beltSplices[0].id);
    }
  }, [beltSplices, selectedSpliceId]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] space-y-3">
      {/* Top Header & Control Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center shadow-sm">
            <Layers size={20} />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              SpliceTracker 3D System Architecture & Digital Twin
            </h1>
            <p className="text-xs text-slate-500">
              Interactive physical-to-cloud engineering model // Sensors, Edge Compute, AI Pipeline, and Real-Time Telemetry
            </p>
          </div>
        </div>

        {/* Asset & Splice Selector */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-slate-100 rounded-md p-1 border border-slate-200">
            <span className="text-xs font-semibold text-slate-600 px-2">Asset:</span>
            {['BELT-01', 'BELT-02', 'BELT-03', 'BELT-04'].map((bId) => (
              <button
                key={bId}
                onClick={() => {
                  setSelectedBelt(bId);
                  const firstInBelt = splices.find((s: any) => s.belt_id === bId);
                  if (firstInBelt) setSelectedSpliceId(firstInBelt.id);
                }}
                className={`text-xs px-2.5 py-1 rounded font-medium transition-all ${
                  selectedBelt === bId ? 'bg-white text-blue-700 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {bId}
              </button>
            ))}
          </div>

          {beltSplices.length > 0 && (
            <select
              value={activeSplice?.id || ''}
              onChange={(e) => setSelectedSpliceId(Number(e.target.value))}
              className="text-xs bg-white border border-slate-300 rounded-md px-2.5 py-1.5 font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {beltSplices.map((s: any) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.condition} // {s.position.toFixed(1)}m)
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Main 3D Workspace */}
      <div className="flex-1 grid grid-cols-12 gap-3 min-h-0">
        {/* Left 3D Viewport Column */}
        <div className="col-span-12 lg:col-span-9 flex flex-col h-full rounded-xl overflow-hidden border border-slate-800 bg-slate-950 relative shadow-inner">
          {/* Viewport Overlay Controls */}
          <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 bg-slate-900/85 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/80 shadow-lg">
            {/* Camera Presets */}
            <div className="flex items-center gap-1 pr-2 border-r border-slate-700">
              <span className="text-[10px] text-slate-400 font-mono uppercase px-1">Cam:</span>
              <button
                onClick={() => setCameraPreset('overview')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  cameraPreset === 'overview' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setCameraPreset('inspection')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  cameraPreset === 'inspection' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                Gantry
              </button>
              <button
                onClick={() => setCameraPreset('splice')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  cameraPreset === 'splice' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                Splice
              </button>
              <button
                onClick={() => setCameraPreset('edge')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  cameraPreset === 'edge' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                Edge Box
              </button>
              <button
                onClick={() => setCameraPreset('topdown')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  cameraPreset === 'topdown' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                Top-Down
              </button>
            </div>

            {/* Animation & Layer Toggles */}
            <button
              onClick={() => setBeltRunning(!beltRunning)}
              title={beltRunning ? 'Pause conveyor motion' : 'Start conveyor motion'}
              className={`p-1.5 rounded transition-colors ${beltRunning ? 'bg-emerald-600/80 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
            >
              {beltRunning ? <Pause size={14} /> : <Play size={14} />}
            </button>

            <button
              onClick={() => setShowDataFlow(!showDataFlow)}
              title="Toggle Particle Data Flow"
              className={`px-2 py-0.5 text-xs rounded font-mono transition-colors ${
                showDataFlow ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'
              }`}
            >
              Data Flow
            </button>

            <button
              onClick={() => setShowAiOverlay(!showAiOverlay)}
              title="Toggle Holographic AI Overlay"
              className={`px-2 py-0.5 text-xs rounded font-mono transition-colors ${
                showAiOverlay ? 'bg-purple-600 text-white' : 'text-slate-400 hover:bg-slate-800'
              }`}
            >
              AI HUD
            </button>
          </div>

          {/* Bottom Left Quick Status Badge */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 bg-slate-900/85 backdrop-blur-md px-3 py-2 rounded-lg border border-slate-800 text-xs font-mono text-slate-300">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Asset:</span>
              <span className="font-bold text-white">{selectedBelt}</span>
            </div>
            <div className="h-3 w-px bg-slate-700" />
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Active Splice:</span>
              <span className="font-bold text-white">{activeSplice?.name || 'Splice-001'}</span>
            </div>
            <div className="h-3 w-px bg-slate-700" />
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Condition:</span>
              <span
                className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
                  effectiveStatus === 'CRITICAL'
                    ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                    : effectiveStatus === 'WARNING'
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                }`}
              >
                {effectiveStatus}
              </span>
            </div>
          </div>

          {/* 3D Canvas */}
          <div className="flex-1 w-full h-full">
            <SpliceTracker3DScene
              onSelectComponent={(comp) => setSelectedComponent(comp)}
              selectedComponentId={selectedComponent?.id}
              activeStatus={effectiveStatus}
              beltRunning={beltRunning}
              showDataFlow={showDataFlow}
              showAiOverlay={showAiOverlay}
              cameraPreset={cameraPreset}
              activeSpliceName={activeSplice?.name || 'Splice-001'}
            />
          </div>
        </div>

        {/* Right Inspection & Telemetry Column */}
        <div className="col-span-12 lg:col-span-3 flex flex-col h-full gap-3 overflow-y-auto">
          {/* Active Component Telemetry Panel */}
          {selectedComponent ? (
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col space-y-3">
              <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                <div>
                  <span className="text-[10px] uppercase tracking-wider font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                    {selectedComponent.category}
                  </span>
                  <h2 className="text-sm font-bold text-slate-800 mt-1">{selectedComponent.name}</h2>
                  <p className="text-xs text-slate-400 font-mono">{selectedComponent.model}</p>
                </div>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    selectedComponent.status === 'CRITICAL'
                      ? 'bg-red-100 text-red-700'
                      : selectedComponent.status === 'WARNING'
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-emerald-100 text-emerald-700'
                  }`}
                >
                  {selectedComponent.status}
                </span>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed">{selectedComponent.description}</p>

              {/* Real-time Telemetry Metrics */}
              <div>
                <h3 className="text-xs font-bold text-slate-700 mb-1.5 flex items-center gap-1">
                  <Activity size={12} className="text-blue-600" />
                  Live Operational Telemetry
                </h3>
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-100 space-y-1.5">
                  {Object.entries(selectedComponent.telemetry).map(([k, v]) => (
                    <div key={k} className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">{k}:</span>
                      <span className="font-mono font-semibold text-slate-800">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Technical Specifications */}
              <div>
                <h3 className="text-xs font-bold text-slate-700 mb-1.5 flex items-center gap-1">
                  <Sliders size={12} className="text-slate-600" />
                  Hardware Specifications
                </h3>
                <div className="space-y-1 text-xs">
                  {Object.entries(selectedComponent.specs).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-slate-600 border-b border-slate-50 py-0.5">
                      <span className="text-slate-400">{k}</span>
                      <span className="font-medium text-slate-700 text-right">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm text-center flex flex-col items-center justify-center text-slate-400 space-y-2">
              <Eye size={28} className="text-slate-300" />
              <p className="text-xs font-medium text-slate-600">Interactive 3D Inspector</p>
              <p className="text-[11px] text-slate-400 leading-normal">
                Click any sensor on the gantry, the splice joint, the drive motor, or the SpliceTracker Edge box in the 3D model to inspect real-time telemetry and hardware specs.
              </p>
            </div>
          )}

          {/* Splice Health State Machine Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <Cpu size={14} className="text-purple-600" />
                Active Splice Digital Twin
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Position: {activeSplice?.position?.toFixed(1)}m</span>
            </div>

            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-slate-800">{activeSplice?.name || 'Splice-001'}</div>
                <div className="text-[11px] text-slate-500">Belt ID: {activeSplice?.belt_id}</div>
              </div>
              <div className="text-right">
                <div className="text-xs font-mono font-bold text-slate-900">
                  Severity: {activeSplice?.severity !== undefined ? (activeSplice.severity * 100).toFixed(1) + '%' : '4.2%'}
                </div>
                <div className="text-[10px] text-slate-500">Confidence: 94%</div>
              </div>
            </div>

            {/* Simulation State Override */}
            <div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-1.5">
                Inspect Condition State:
              </span>
              <div className="grid grid-cols-4 gap-1">
                {(['AUTO', 'NORMAL', 'WARNING', 'CRITICAL'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setSimulatedStatus(mode)}
                    className={`text-[10px] py-1 rounded font-bold transition-all ${
                      simulatedStatus === mode
                        ? mode === 'CRITICAL'
                          ? 'bg-red-600 text-white shadow-sm'
                          : mode === 'WARNING'
                          ? 'bg-amber-500 text-white shadow-sm'
                          : mode === 'NORMAL'
                          ? 'bg-emerald-600 text-white shadow-sm'
                          : 'bg-blue-600 text-white shadow-sm'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Pipeline Data Path Summary */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-2">
            <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
              <Database size={14} className="text-blue-600" />
              Data Pipeline & Synchronous Ingestion
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Vision Line-Rate</span>
                <span className="font-mono font-bold text-slate-800">48 kHz (GigE)</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Thermal Stream</span>
                <span className="font-mono font-bold text-slate-800">60 Hz LWIR</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Ultrasonic Pulser</span>
                <span className="font-mono font-bold text-slate-800">5.0 MHz Echo</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Edge Inference Latency</span>
                <span className="font-mono font-bold text-emerald-600">14.2 ms</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500">Database Record Count</span>
                <span className="font-mono font-bold text-blue-600">1,452 Telemetry Rows</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
