import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Square,
  FastForward,
  Activity,
  Cpu,
  Layers,
  Sparkles,
  Sliders,
  Radio,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  RefreshCw,
  Zap,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { api } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import MiniConveyorScene from '../components/3d/MiniConveyorScene';

const SCENARIO_ICONS: Record<string, string> = {
  normal: 'N',
  visual_anomaly: 'V',
  thermal_anomaly: 'T',
  conductive_break: 'C',
  mechanical_anomaly: 'M',
  multi_sensor: 'MS',
  progressive_degradation: 'PD',
  critical: 'CR',
  high_risk: 'HR',
  intermittent: 'INT',
  resolved: 'RES',
  demo: 'DEMO',
};

export default function Simulation() {
  const [running, setRunning] = useState(false);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [splices, setSplices] = useState<any[]>([]);
  const [selectedSpliceId, setSelectedSpliceId] = useState<number>(1);
  const [anomalyProb, setAnomalyProb] = useState<number>(0.5);
  const [events, setEvents] = useState<any[]>([]);
  const [currentStep, setCurrentStep] = useState<any>(null);
  const [loadingScenarios, setLoadingScenarios] = useState(false);
  const [availableScenarios, setAvailableScenarios] = useState<Record<string, any>>({});

  const { subscribe } = useWebSocket();

  // Fetch initial status & splices
  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, splicesRes] = await Promise.all([
        api.getSimulationStatus(),
        api.getSplices(),
      ]);
      if (statusRes?.available_scenarios) {
        setAvailableScenarios(statusRes.available_scenarios);
      }
      if (statusRes?.running !== undefined) {
        setRunning(statusRes.running);
      }
      if (splicesRes?.splices?.length) {
        setSplices(splicesRes.splices);
        setSelectedSpliceId(splicesRes.splices[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch simulation status:', err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // WebSocket subscriptions for real-time live events
  useEffect(() => {
    const unsubs = [
      subscribe('inspection_completed', (p: any) => {
        const ev = {
          step: p.step || events.length + 1,
          total_steps: p.total_steps || 1,
          label: p.label || `Inspection #${p.inspection_id}`,
          risk: p.risk_level || p.result?.risk_result?.risk_level || 'LOW',
          overall: p.overall_score || 0,
          defect_type: p.defect_type,
          scores: p.scores || {
            vision: p.overall_score || 0,
            thermal: p.overall_score || 0,
            mechanical: p.overall_score || 0,
            conductive: 0,
            fused: p.overall_score || 0,
          },
          time: p.time || new Date().toLocaleTimeString(),
        };
        setCurrentStep(ev);
        setEvents(prev => [...prev, ev]);
      }),
      subscribe('system_status', (p: any) => {
        if (p.event === 'simulation_completed' || p.event === 'simulation_stopped') {
          setRunning(false);
          setActiveScenario(null);
        }
        if (p.event === 'simulation_started') {
          setRunning(true);
        }
      }),
    ];
    return () => unsubs.forEach(u => u());
  }, [subscribe, events.length]);

  // Run specific scenario
  const startScenario = async (key: string) => {
    setEvents([]);
    setCurrentStep(null);
    setActiveScenario(key);
    setRunning(true);
    setLoadingScenarios(true);

    try {
      const resp = await api.runScenario(key, selectedSpliceId);
      if (resp?.events?.length) {
        setEvents(resp.events);
        setCurrentStep(resp.events[resp.events.length - 1]);
      }
    } catch (err) {
      console.error('Scenario run error:', err);
    } finally {
      setRunning(false);
      setLoadingScenarios(false);
    }
  };

  // Trigger manual single step
  const handleSingleStep = async () => {
    try {
      const resp = await api.stepSimulation({
        splice_id: selectedSpliceId,
        anomaly_probability: anomalyProb,
      });
      if (resp?.result) {
        const ev = resp.result;
        setCurrentStep(ev);
        setEvents(prev => [...prev, ev]);
      }
    } catch (err) {
      console.error('Step execution error:', err);
    }
  };

  // Toggle continuous simulation
  const toggleContinuousSim = async () => {
    if (running) {
      try {
        await api.stopSimulation();
      } catch {}
      setRunning(false);
      setActiveScenario(null);
    } else {
      try {
        await api.startSimulation({
          splice_count: splices.length || 5,
          inspection_interval_seconds: 4.0,
          anomaly_probability: anomalyProb,
        });
        setRunning(true);
      } catch (err) {
        console.error('Start sim error:', err);
      }
    }
  };

  const scenariosList = Object.entries(
    Object.keys(availableScenarios).length > 0
      ? availableScenarios
      : {
          normal: { name: 'Normal Operation', description: 'Nominal belt speeds & baseline multi-sensor signals', duration_steps: 5 },
          visual_anomaly: { name: 'Visual Anomaly', description: 'Camera line-scan detects surface wear / crack', duration_steps: 5 },
          thermal_anomaly: { name: 'Thermal Anomaly', description: 'Infrared radiometric hotspot friction elevation', duration_steps: 5 },
          conductive_break: { name: 'Conductive Break', description: 'Inductive continuity circuit rupture detection', duration_steps: 4 },
          mechanical_anomaly: { name: 'Mechanical Anomaly', description: 'Tri-axial accelerometer harmonic vibration spike', duration_steps: 5 },
          multi_sensor: { name: 'Multi-Sensor Fusion', description: 'Co-located structural failure across all 4 modalities', duration_steps: 6 },
          progressive_degradation: { name: 'Progressive Degradation', description: 'Stepwise wear progression from 10% to 90% severity', duration_steps: 8 },
          critical: { name: 'Critical Failure', description: 'Emergency alarm state exceeding safety margin', duration_steps: 4 },
          intermittent: { name: 'Intermittent Fault', description: 'Transient spike pulses alternating with recovery', duration_steps: 6 },
          resolved: { name: 'Resolved Defect', description: 'Pre-intervention damage followed by repair restoration', duration_steps: 7 },
          demo: { name: 'Full Inspection Demo', description: 'Complete 10-step multi-stage operational demonstration', duration_steps: 10 },
        }
  );

  // Radar chart data from current step
  const radarData = [
    { modality: 'Vision', score: (currentStep?.scores?.vision || 0.1) * 100 },
    { modality: 'Thermal', score: (currentStep?.scores?.thermal || 0.1) * 100 },
    { modality: 'Mechanical', score: (currentStep?.scores?.mechanical || 0.1) * 100 },
    { modality: 'Conductive', score: (currentStep?.scores?.conductive || 0.0) * 100 },
    { modality: 'Fused Index', score: (currentStep?.scores?.fused || currentStep?.overall || 0.1) * 100 },
  ];

  // Timeline chart data
  const timelineData = events.map((e, i) => ({
    name: `Step ${e.step || i + 1}`,
    overall: Math.round((e.overall || e.overall_score || 0) * 100),
    vision: Math.round((e.scores?.vision || 0) * 100),
    thermal: Math.round((e.scores?.thermal || 0) * 100),
    mechanical: Math.round((e.scores?.mechanical || 0) * 100),
  }));

  const activeSpliceObj = splices.find(s => s.id === selectedSpliceId);

  // Active anomaly string for 3D conveyor
  let anomalyMode3D: string | null = null;
  if (activeScenario) {
    if (activeScenario.includes('visual')) anomalyMode3D = 'vision';
    else if (activeScenario.includes('thermal')) anomalyMode3D = 'thermal';
    else if (activeScenario.includes('mechanical')) anomalyMode3D = 'mechanical';
    else if (activeScenario.includes('critical') || activeScenario.includes('break')) anomalyMode3D = 'critical';
  } else if (currentStep?.overall > 0.6) {
    anomalyMode3D = 'critical';
  }

  return (
    <div className="space-y-4">
      {/* Top Header & Simulation Command Bar */}
      <div className="bg-slate-900 border border-slate-700/80 rounded-xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
            <h2 className="text-lg font-bold text-white font-mono tracking-wide">
              SYNTHETIC SIMULATION & FAULT INJECTION STATION
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Test and validate the Multi-Sensor Fusion, DIVE, and ATCE intelligence engines with real-time multi-modality synthetic vectors.
          </p>
        </div>

        {/* Global Control Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSingleStep}
            disabled={running}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 text-xs font-mono transition-all disabled:opacity-50"
            title="Inject a single inspection pass"
          >
            <FastForward className="w-3.5 h-3.5 text-cyan-400" />
            <span>Single Step</span>
          </button>

          <button
            onClick={toggleContinuousSim}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-mono font-bold transition-all shadow-md ${
              running
                ? 'bg-red-600 hover:bg-red-500 text-white'
                : 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white'
            }`}
          >
            {running ? (
              <>
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Stop Loop</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Continuous Sim</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Interactive Control & 3D Stage Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column: 3D Twin & Technical Signal Flow Schematic */}
        <div className="col-span-12 lg:col-span-7 space-y-4">
          {/* 3D Real-time Conveyor Simulation Stage */}
          <MiniConveyorScene
            height={320}
            interactive={true}
            activeAnomaly={anomalyMode3D}
            spliceName={activeSpliceObj?.name || 'Splice-001'}
            condition={currentStep?.condition || activeSpliceObj?.condition || 'GOOD'}
            speed={running ? 1.4 : 0.8}
          />

          {/* Real-time Multi-Sensor Waveform Timeline */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
                  Simulation Anomaly Waveform Timeline
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                {events.length} Inspection Steps Recorded
              </span>
            </div>

            {timelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={timelineData}>
                  <defs>
                    <linearGradient id="fusedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="thermalGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#64748b' }} unit="%" />
                  <Tooltip contentStyle={{ fontSize: 11, backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff' }} />
                  <Area type="monotone" dataKey="overall" name="Fused Anomaly" stroke="#3b82f6" strokeWidth={2} fill="url(#fusedGrad)" />
                  <Area type="monotone" dataKey="thermal" name="Thermal" stroke="#f59e0b" strokeWidth={1.5} fill="url(#thermalGrad)" />
                  <Area type="monotone" dataKey="vision" name="Vision" stroke="#06b6d4" strokeWidth={1.5} fill="none" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-32 flex flex-col items-center justify-center text-slate-400 text-xs font-mono">
                <span>Select a scenario card or click "Single Step" to generate waveforms.</span>
              </div>
            )}
          </div>

          {/* Custom SVG Industrial Schematic Illustration */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-white shadow-md">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-cyan-400 font-bold">EDGE DAQ & INFERENCE PIPELINE ARCHITECTURE</span>
              <span className="text-[10px] font-mono text-slate-500">IEEE 1451 Sensor Protocol</span>
            </div>

            <svg viewBox="0 0 720 130" className="w-full h-auto">
              <rect x="10" y="20" width="130" height="90" rx="8" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.5" />
              <text x="75" y="45" fill="#38bdf8" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">LINE-SCAN CAM</text>
              <text x="75" y="65" fill="#94a3b8" fontSize="9" textAnchor="middle" fontFamily="monospace">2048px CMOS</text>
              <text x="75" y="85" fill="#64748b" fontSize="8" textAnchor="middle" fontFamily="monospace">Optical Flow / ROI</text>

              <rect x="160" y="20" width="130" height="90" rx="8" fill="#1e293b" stroke="#f59e0b" strokeWidth="1.5" />
              <text x="225" y="45" fill="#f59e0b" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">LWIR THERMAL</text>
              <text x="225" y="65" fill="#94a3b8" fontSize="9" textAnchor="middle" fontFamily="monospace">640x512 Radiometric</text>
              <text x="225" y="85" fill="#64748b" fontSize="8" textAnchor="middle" fontFamily="monospace">ΔT & Hotspots</text>

              <rect x="310" y="20" width="130" height="90" rx="8" fill="#1e293b" stroke="#a855f7" strokeWidth="1.5" />
              <text x="375" y="45" fill="#a855f7" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">3-AXIS ACCEL</text>
              <text x="375" y="65" fill="#94a3b8" fontSize="9" textAnchor="middle" fontFamily="monospace">10 kHz Sample Rate</text>
              <text x="375" y="85" fill="#64748b" fontSize="8" textAnchor="middle" fontFamily="monospace">Harmonics & Kurtosis</text>

              <rect x="460" y="20" width="110" height="90" rx="8" fill="#1e293b" stroke="#10b981" strokeWidth="1.5" />
              <text x="515" y="45" fill="#10b981" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">LOOP ANTENNA</text>
              <text x="515" y="65" fill="#94a3b8" fontSize="9" textAnchor="middle" fontFamily="monospace">RF Continuity</text>
              <text x="515" y="85" fill="#64748b" fontSize="8" textAnchor="middle" fontFamily="monospace">Cord Integrity</text>

              {/* Arrow to Edge AI Box */}
              <line x1="575" y1="65" x2="605" y2="65" stroke="#38bdf8" strokeWidth="2" strokeDasharray="4 2" />
              <polygon points="605,60 615,65 605,70" fill="#38bdf8" />

              <rect x="615" y="15" width="95" height="100" rx="10" fill="#0f172a" stroke="#10b981" strokeWidth="2" />
              <text x="662" y="45" fill="#10b981" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">EDGE JETSON</text>
              <text x="662" y="65" fill="#38bdf8" fontSize="9" textAnchor="middle" fontFamily="monospace">DIVE FUSION</text>
              <text x="662" y="85" fill="#f59e0b" fontSize="9" textAnchor="middle" fontFamily="monospace">ATCE TWIN</text>
              <circle cx="662" cy="100" r="4" fill="#10b981" className="animate-pulse" />
            </svg>
          </div>
        </div>

        {/* Right Column: Scenario Launcher, Radar Chart, & Live Telemetry Inspector */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          {/* Target Splice & Anomaly Probability Selectors */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 font-mono">SIMULATION INJECTION TARGET</span>
              <span className="text-[10px] font-mono text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                Target Splice #{selectedSpliceId}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-500 font-medium block mb-1">Target Splice:</label>
                <select
                  value={selectedSpliceId}
                  onChange={e => setSelectedSpliceId(parseInt(e.target.value))}
                  disabled={running}
                  className="w-full text-xs font-mono bg-slate-50 border border-slate-200 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  {splices.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.belt_id} • {s.condition})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] text-slate-500 font-medium">Anomaly Probability:</label>
                  <span className="text-xs font-mono font-bold text-slate-700">{(anomalyProb * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={anomalyProb}
                  onChange={e => setAnomalyProb(parseFloat(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer mt-1.5"
                />
              </div>
            </div>
          </div>

          {/* Real-time Multi-Sensor Radar Chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <Radio className="w-4 h-4 text-purple-600" />
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
                  Live Multi-Modality Balance Radar
                </h3>
              </div>
              {currentStep?.risk && <StatusBadge value={currentStep.risk} size="xs" />}
            </div>

            <ResponsiveContainer width="100%" height={190}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="modality" tick={{ fontSize: 10, fill: '#475569' }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 8, fill: '#94a3b8' }} />
                <Radar name="Signal Magnitude" dataKey="score" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.35} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Scenario Quick Launcher Grid */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
                Fault Scenarios ({scenariosList.length})
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Click to execute scenario</span>
            </div>

            <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto pr-1">
              {scenariosList.map(([key, s]: [string, any]) => {
                const isActive = activeScenario === key;
                return (
                  <button
                    key={key}
                    onClick={() => startScenario(key)}
                    disabled={running}
                    className={`rounded-lg border p-2.5 text-left transition-all relative ${
                      isActive
                        ? 'border-blue-500 bg-blue-50/70 shadow-sm'
                        : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
                    } ${running && !isActive ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-5 h-5 rounded bg-blue-100 text-blue-700 text-[9px] font-bold font-mono flex items-center justify-center">
                        {SCENARIO_ICONS[key] || key.slice(0, 2).toUpperCase()}
                      </span>
                      <span className="text-xs font-bold text-slate-800 truncate">{s.name}</span>
                    </div>
                    <p className="text-[10px] text-slate-500 line-clamp-2">{s.description}</p>
                    <div className="flex justify-between items-center mt-1.5 text-[9px] font-mono text-slate-400">
                      <span>{s.duration_steps || 5} steps</span>
                      {isActive && <span className="text-blue-600 font-bold animate-pulse">RUNNING</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Live Step Progress & Telemetry Log */}
          {events.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-700 font-mono">TELEMETRY STEP LOG</span>
                <span className="text-[10px] font-mono text-slate-400">{events.length} iterations</span>
              </div>

              <div className="flex gap-1 mb-3">
                {events.map((e, idx) => (
                  <div
                    key={idx}
                    className={`h-2 flex-1 rounded-sm transition-all ${
                      e.risk === 'CRITICAL'
                        ? 'bg-red-500'
                        : e.risk === 'HIGH' || e.risk === 'POOR'
                        ? 'bg-amber-500'
                        : e.risk === 'MODERATE' || e.risk === 'FAIR'
                        ? 'bg-yellow-400'
                        : 'bg-emerald-400'
                    }`}
                    title={e.label}
                  />
                ))}
              </div>

              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1 text-xs">
                {events.slice(-15).reverse().map((e, idx) => (
                  <div key={idx} className="flex items-center justify-between p-1.5 rounded bg-slate-50 hover:bg-slate-100 border border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-slate-400 w-6">#{e.step || events.length - idx}</span>
                      <span className="font-mono text-[10px] text-slate-400 w-14">{e.time || 'now'}</span>
                      <span className="text-slate-700 font-medium truncate max-w-[170px]">{e.label}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {e.risk && <StatusBadge value={e.risk} size="xs" />}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
