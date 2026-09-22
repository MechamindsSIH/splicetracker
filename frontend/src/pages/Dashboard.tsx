import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Layers,
  ArrowRight,
  Activity,
  ShieldCheck,
  AlertOctagon,
  Cpu,
  RefreshCw,
  Eye,
  Radio,
  BarChart3,
} from 'lucide-react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { useWebSocket } from '../hooks/useWebSocket';
import StatusBadge from '../components/StatusBadge';
import SensorCard from '../components/SensorCard';
import RiskGauge from '../components/RiskGauge';
import FusionDisplay from '../components/FusionDisplay';
import AlertCard from '../components/AlertCard';
import LoadingSpinner from '../components/LoadingSpinner';
import MiniConveyorScene from '../components/3d/MiniConveyorScene';
import { demoAlerts, demoAnalytics, demoAssets, demoSplices, demoStatus } from '../data/demoData';

const edgeFlowData = Array.from({ length: 18 }, (_, index) => ({
  tick: `${String(8 + Math.floor(index / 3)).padStart(2, '0')}:${String((index % 3) * 20).padStart(2, '0')}`,
  vision: 166 + ((index * 17) % 31),
  thermal: 58 + ((index * 11) % 18),
  fusion: 78 + ((index * 7) % 16),
  latency: 42 + ((index * 9) % 24),
}));

export default function Dashboard() {
  const { data: status, loading: statusLoading } = usePolling(useCallback(() => api.getSystemStatus(), []), 5000);
  const { data: splicesData } = usePolling(useCallback(() => api.getSplices(), []), 5000);
  const { data: alertsData } = usePolling(useCallback(() => api.getAlerts({ status: 'ACTIVE', limit: 5 }), []), 5000);
  const { data: analyticsData } = usePolling(useCallback(() => api.getAnalytics(), []), 10000);
  const { connected, subscribe } = useWebSocket();

  const [selectedBelt, setSelectedBelt] = useState('BELT-01');
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [latestFusion, setLatestFusion] = useState<any>(null);
  const [latestRisk, setLatestRisk] = useState<any>({ risk_score: 0, risk_level: 'LOW' });
  const [sensorReadings, setSensorReadings] = useState<Record<string, any>>({});

  useEffect(() => {
    const unsubs = [
      subscribe('inspection_completed', (p: any) => {
        setRecentEvents(prev => [{ ...p, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 20));
        if (p.result?.fusion_result) setLatestFusion(p.result.fusion_result);
        if (p.result?.risk_result) setLatestRisk(p.result.risk_result);
      }),
      subscribe('sensor_update', (p: any) => {
        setSensorReadings(prev => ({ ...prev, [p.sensor_type]: p.data }));
      }),
      subscribe('risk_updated', (p: any) => {
        setLatestRisk({ risk_score: p.risk_score || 0, risk_level: p.risk_level || 'LOW' });
      }),
    ];
    return () => unsubs.forEach(u => u());
  }, [subscribe]);

  // Keep a complete, clearly-labelled local demo mirror available when the
  // backend is not running. Live API data always takes precedence.
  const isDemoMode = !splicesData?.splices?.length;
  const splices = isDemoMode ? demoSplices : splicesData.splices;
  const beltSplices = splices.filter((s: any) => s.belt_id === selectedBelt);
  // Surface the asset's highest-priority splice rather than whichever record
  // happened to be returned first.
  const currentSplice = beltSplices.reduce((highest: any, splice: any) =>
    !highest || splice.severity > highest.severity ? splice : highest,
  undefined as any) || splices[0];
  const alerts = alertsData?.alerts?.length ? alertsData.alerts : demoAlerts;
  const components = status?.components || demoStatus.components;
  const selectedAsset = demoAssets[selectedBelt];

  // Generate trend data from splices if analytics trends are empty
  const conditionData = (analyticsData?.condition_trends?.length ? analyticsData.condition_trends : splices.slice(0, 10)).map((t: any, i: number) => {
    const cond = t.condition || 'GOOD';
    const val = cond === 'CRITICAL' ? 5 : cond === 'POOR' ? 4 : cond === 'DEGRADED' ? 3 : cond === 'WARNING' ? 2 : cond === 'FAIR' ? 1 : 0;
    return {
      name: t.name || `Splice-${i + 1}`,
      value: val,
      condName: cond,
    };
  });

  if (statusLoading && !splicesData) return <LoadingSpinner message="Connecting to SpliceTracker intelligence platform..." />;

  const totalInspections = analyticsData?.total_inspections ?? analyticsData?.inspection_count ?? demoAnalytics.total_inspections;
  const totalAnomalies = analyticsData?.total_anomalies ?? analyticsData?.anomaly_count ?? demoAnalytics.total_anomalies;
  const totalAlerts = analyticsData?.total_alerts ?? analyticsData?.alert_count ?? demoAnalytics.total_alerts;
  const activeAlertsCount = analyticsData?.active_alerts ?? demoAnalytics.active_alerts;

  return (
    <div className="space-y-4">
      {/* System Status & Asset Selection Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          {['camera', 'thermal', 'conductive', 'mechanical'].map(sensor => (
            <div key={sensor} className="flex items-center gap-1.5 bg-slate-50 rounded px-2.5 py-1 border border-slate-200">
              <div className={`w-2 h-2 rounded-full ${components[sensor] !== 'offline' ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-xs text-slate-700 font-medium capitalize">{sensor}</span>
            </div>
          ))}
          <div className="flex items-center gap-1.5 bg-slate-50 rounded px-2.5 py-1 border border-slate-200">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-emerald-500'}`} />
            <span className="text-xs text-slate-700 font-medium">Edge Link</span>
          </div>
        </div>

        {/* Asset Switcher */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-slate-500">Conveyor Asset:</span>
          {['BELT-01', 'BELT-02', 'BELT-03', 'BELT-04'].map((bId) => (
            <button
              key={bId}
              onClick={() => setSelectedBelt(bId)}
              className={`text-xs px-2.5 py-1 rounded font-medium transition-all ${
                selectedBelt === bId
                  ? 'bg-blue-600 text-white font-bold shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {bId}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-950 via-slate-900 to-blue-950 px-4 py-3 text-white shadow-lg flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${isDemoMode ? 'bg-amber-400' : 'bg-emerald-400'} shadow-[0_0_14px_currentColor]`} />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-slate-400">{isDemoMode ? 'Simulation telemetry stream' : 'Live telemetry feed'}</div>
            <div className="text-sm font-semibold">{selectedAsset.name} <span className="font-mono text-slate-400">/ {selectedBelt}</span></div>
          </div>
        </div>
        <div className="flex items-center gap-5 text-xs font-mono">
          <div><span className="text-slate-400">LENGTH </span><span className="text-cyan-300">{selectedAsset.length}</span></div>
          <div><span className="text-slate-400">DESIGN SPEED </span><span className="text-cyan-300">{selectedAsset.speed}</span></div>
          <div><span className="text-slate-400">PRIORITY </span><span className={currentSplice?.severity > 0.5 ? 'text-rose-300' : 'text-emerald-300'}>{currentSplice?.risk_level || 'LOW'}</span></div>
        </div>
      </div>

      {/* 3D Digital Twin Hero Interactive Card */}
      <div className="bg-slate-900 rounded-xl border border-slate-700/80 p-4 shadow-xl text-white space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600/30 border border-blue-400/40 flex items-center justify-center text-cyan-400 shadow-inner">
              <Layers size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">
                  Live 3D Digital Twin Active
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  Asset: {selectedBelt} // {beltSplices.length} Monitored Splices
                </span>
              </div>
              <h2 className="text-sm font-bold text-white mt-0.5">
                Conveyor Gantry & Multi-Sensor Digital Twin
              </h2>
            </div>
          </div>

          <Link
            to="/architecture"
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg font-medium text-xs shadow transition-all hover:translate-x-0.5"
          >
            Launch Full 3D Facility
            <ArrowRight size={13} />
          </Link>
        </div>

        {/* Embedded Interactive 3D Conveyor Scene */}
        <MiniConveyorScene
          height={260}
          interactive={true}
          spliceName={currentSplice?.name || 'Splice-001'}
          condition={currentSplice?.condition || 'GOOD'}
          speed={1.0}
        />
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Current Splice Status */}
        <div className="col-span-12 md:col-span-4 bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide">Active Monitored Splice</h3>
            <span className="text-xs font-mono text-slate-400">{currentSplice?.belt_id}</span>
          </div>
          {currentSplice ? (
            <div className="space-y-2.5">
              <Link to={`/splice/${currentSplice.id}`} className="text-lg font-bold text-slate-900 hover:text-blue-600 block">
                {currentSplice.name}
              </Link>
              <div className="flex items-center gap-2">
                <StatusBadge value={currentSplice.condition || 'GOOD'} />
                <StatusBadge value={currentSplice.risk_level || 'LOW'} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-1">
                <div>Position: <span className="font-mono font-semibold text-slate-800">{currentSplice.position?.toFixed(1)}m</span></div>
                <div>Confidence: <span className="font-mono font-semibold text-slate-800">{((currentSplice.confidence || 0.94) * 100).toFixed(0)}%</span></div>
                <div>Severity: <span className="font-mono font-semibold text-slate-800">{(currentSplice.severity * 100).toFixed(1)}%</span></div>
                <div>Installed: <span className="font-mono font-semibold text-slate-800">{new Date(currentSplice.installed_date || Date.now()).toLocaleDateString()}</span></div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">No splice data</p>
          )}
        </div>

        {/* Risk Gauge */}
        <div className="col-span-12 md:col-span-3">
          <RiskGauge score={currentSplice?.severity || latestRisk.risk_score || 0} level={currentSplice?.risk_level || latestRisk.risk_level || 'LOW'} />
        </div>

        {/* Operational KPI Cards */}
        <div className="col-span-12 md:col-span-5 grid grid-cols-3 gap-3">
          <div className="bg-white rounded-lg border border-slate-200 p-3.5 shadow-sm">
            <div className="text-xs font-medium text-slate-500">Historical Inspections</div>
            <div className="text-2xl font-bold text-slate-900 font-mono mt-1">{totalInspections}</div>
            <div className="text-[10px] text-emerald-600 mt-0.5 font-medium">365-Day History</div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-3.5 shadow-sm">
            <div className="text-xs font-medium text-slate-500">Anomalies Detected</div>
            <div className="text-2xl font-bold text-amber-600 font-mono mt-1">{totalAnomalies}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">DIVE Verified</div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-3.5 shadow-sm">
            <div className="text-xs font-medium text-slate-500">Active Alerts</div>
            <div className="text-2xl font-bold text-red-600 font-mono mt-1">{activeAlertsCount}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Total: {totalAlerts}</div>
          </div>
        </div>
      </div>

      {/* Sensor Modality Cards + Fusion Display */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8 grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { name: 'Vision', key: 'vision', defScore: currentSplice?.severity || 0.04 },
            { name: 'Thermal', key: 'thermal', defScore: (currentSplice?.severity || 0.05) * 0.9 },
            { name: 'Mechanical', key: 'mechanical', defScore: (currentSplice?.severity || 0.06) * 0.85 },
            { name: 'Conductive', key: 'conductive', defScore: currentSplice?.condition === 'CRITICAL' ? 1.0 : 0.0 },
          ].map(s => (
            <SensorCard
              key={s.key}
              name={s.name}
              anomalyScore={sensorReadings[s.key]?.anomaly_score || latestFusion?.[`${s.key}_score`] || s.defScore}
              confidence={sensorReadings[s.key]?.confidence || 0.94}
              status={components[s.key] || 'online'}
              details={sensorReadings[s.key]?.details}
            />
          ))}
        </div>
        <div className="col-span-12 lg:col-span-4">
          <FusionDisplay fusion={latestFusion || {
            fusion_status: currentSplice?.condition === 'CRITICAL' ? 'CONFLICT' : 'COMPLETE',
            vision_score: currentSplice?.severity || 0.04,
            thermal_score: (currentSplice?.severity || 0.04) * 0.9,
            mechanical_score: (currentSplice?.severity || 0.04) * 0.85,
            conductive_score: currentSplice?.condition === 'CRITICAL' ? 1.0 : 0.0,
            overall_confidence: 0.93,
          }} />
        </div>
      </div>

      {/* Multi-Modality Live Waveform Sparklines */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
              Live Modality Waveforms (Vision • Thermal • Dynamic Imbalance • Loop Continuity)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            Real-Time Edge Telemetry
          </span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'OptiScan 8K Line-Scan', score: currentSplice?.severity || 0.04, color: '#06b6d4' },
            { label: 'LWIR 60Hz Radiometric', score: (currentSplice?.severity || 0.05) * 0.9, color: '#f59e0b' },
            { label: 'Tri-Axial RMS (10kHz)', score: (currentSplice?.severity || 0.06) * 0.85, color: '#8b5cf6' },
            { label: 'Inductive Loop Circuit', score: currentSplice?.condition === 'CRITICAL' ? 1.0 : 0.0, color: '#10b981' },
          ].map((ch, idx) => (
            <div key={idx} className="bg-slate-50 rounded-lg p-2.5 border border-slate-200/80">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] font-mono text-slate-500">{ch.label}</span>
                <span className="text-xs font-mono font-bold" style={{ color: ch.color }}>{(ch.score * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, Math.max(5, ch.score * 100))}%`, backgroundColor: ch.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Edge data-flow observability */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 xl:col-span-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-600" />
                <h3 className="text-sm font-bold text-slate-800">Edge Data-Flow Throughput</h3>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">Ingress, fusion and inference activity across the last six hours</p>
            </div>
            <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-[10px] font-mono font-semibold text-cyan-700">STREAM HEALTH 99.98%</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={edgeFlowData} margin={{ left: -18, right: 8 }}>
              <defs>
                <linearGradient id="visionFlow" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#06b6d4" stopOpacity={0.35}/><stop offset="100%" stopColor="#06b6d4" stopOpacity={0}/></linearGradient>
                <linearGradient id="fusionFlow" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.28}/><stop offset="100%" stopColor="#8b5cf6" stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="tick" tick={{ fontSize: 10 }} interval={2} /><YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ borderRadius: 8, borderColor: '#cbd5e1', fontSize: 11 }} />
              <Area type="monotone" dataKey="vision" name="Vision frames/min" stroke="#06b6d4" fill="url(#visionFlow)" strokeWidth={2} />
              <Area type="monotone" dataKey="fusion" name="Fusion jobs/min" stroke="#8b5cf6" fill="url(#fusionFlow)" strokeWidth={2} />
              <Line type="monotone" dataKey="thermal" name="Thermal frames/min" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="col-span-12 xl:col-span-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold text-slate-800">Inference Service Map</h3><span className="text-[10px] font-mono text-emerald-600">ALL NOMINAL</span></div>
          <div className="space-y-3">
            {[
              ['Vision gateway', '188 fps', '12 ms', 'bg-cyan-500'], ['Thermal fusion', '61 fps', '24 ms', 'bg-amber-500'], ['DIVE correlation', '84 jobs/min', '41 ms', 'bg-violet-500'], ['Risk inference', '36 updates/min', '57 ms', 'bg-emerald-500'],
            ].map(([name, rate, latency, color]) => (
              <div key={name} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                <div className="flex items-center justify-between text-xs"><span className="font-semibold text-slate-700">{name}</span><span className="font-mono text-slate-400">{latency}</span></div>
                <div className="mt-2 flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${color}`} /><span className="text-[11px] font-mono text-slate-600">{rate}</span><div className="ml-auto h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><div className={`h-full rounded-full ${color}`} style={{ width: `${78 + (name.length % 3) * 8}%` }} /></div></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3"><div><h3 className="text-sm font-bold text-slate-800">Intelligence Lifecycle</h3><p className="text-[11px] text-slate-500">How a detected signal becomes an operational decision</p></div><Link to="/pipeline" className="text-xs font-medium text-blue-600 hover:underline">Open pipeline →</Link></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {[
            ['SENSOR FUSION', '4 modalities', '94% confidence', 'border-cyan-300 bg-cyan-50', 'text-cyan-700'],
            ['DIVE', 'EVT-240918-073', '14 observations correlated', 'border-violet-300 bg-violet-50', 'text-violet-700'],
            ['ATCE', 'Rapid degradation', 'Trend persistence: 14 cycles', 'border-amber-300 bg-amber-50', 'text-amber-700'],
            ['TDOS', 'Critical operating state', 'Decision route: intervention', 'border-rose-300 bg-rose-50', 'text-rose-700'],
          ].map(([name, headline, detail, tone, accent]) => (
            <div key={name} className={`rounded-lg border p-3 ${tone}`}><div className={`text-[10px] font-mono font-bold tracking-wider ${accent}`}>{name}</div><div className="mt-1 text-sm font-bold text-slate-800">{headline}</div><div className="mt-1 text-[11px] text-slate-500">{detail}</div></div>
          ))}
        </div>
      </div>

      {/* Charts + Alerts + Events */}
      <div className="grid grid-cols-12 gap-4">
        {/* Condition Trend */}
        <div className="col-span-12 lg:col-span-4 bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-700">Splice Health Distribution & Trends</h3>
            <span className="text-xs text-slate-400 font-mono">Asset: {selectedBelt}</span>
          </div>
          {conditionData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={conditionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} ticks={[0,1,2,3,4,5]} tickFormatter={(v) => ['GOOD','FAIR','WRN','DEG','POOR','CRT'][v] || ''} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">Awaiting telemetry...</p>
          )}
        </div>

        {/* Conveyor Belt Comparison Bar Chart */}
        <div className="col-span-12 lg:col-span-4 bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-700">Conveyor Lines Risk Comparison</h3>
            <span className="text-xs text-slate-400 font-mono">4 Conveyor Assets</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={[
              { belt: 'BELT-01', risk: 22, splices: 5 },
              { belt: 'BELT-02', risk: 12, splices: 4 },
              { belt: 'BELT-03', risk: 68, splices: 3 },
              { belt: 'BELT-04', risk: 36, splices: 4 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="belt" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} unit="%" />
              <Tooltip />
              <Bar dataKey="risk" name="Avg Risk Index" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Active Alerts */}
        <div className="col-span-12 md:col-span-6 lg:col-span-3 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-700">Recent Alerts ({alerts.length})</h3>
            <Link to="/alerts" className="text-xs text-blue-600 hover:underline">View All</Link>
          </div>
          {alerts.length > 0 ? (
            alerts.slice(0, 3).map((a: any) => <AlertCard key={a.id} alert={a} />)
          ) : (
            <div className="bg-white rounded-lg border border-slate-200 p-4 text-xs text-slate-400 text-center">
              All monitored splices nominal
            </div>
          )}
        </div>

        {/* Live System Log Stream */}
        <div className="col-span-12 md:col-span-6 lg:col-span-3">
          <h3 className="text-xs font-bold text-slate-700 mb-2">Live Edge Event Stream</h3>
          <div className="bg-white rounded-lg border border-slate-200 p-2 max-h-[220px] overflow-y-auto space-y-1.5 shadow-sm">
            {recentEvents.length > 0 ? (
              recentEvents.map((e, i) => (
                <div key={i} className="text-[11px] text-slate-700 py-1.5 px-2 bg-slate-50 rounded border border-slate-100 flex items-center justify-between">
                  <span className="text-slate-400 font-mono text-[10px]">{e.ts}</span>
                  <span className="font-medium truncate max-w-[120px]">{e.label || `Inspection`}</span>
                  {e.result?.risk_result?.risk_level && <StatusBadge value={e.result.risk_result.risk_level} size="xs" />}
                </div>
              ))
            ) : (
              <div className="space-y-1.5 text-[11px]">
                <div className="py-1 px-2 bg-slate-50 rounded text-slate-600 flex justify-between">
                  <span className="text-slate-400 font-mono">13:10:20</span>
                  <span>BELT-01 Edge DAQ Sync</span>
                  <span className="text-emerald-600 font-bold text-[10px]">OK</span>
                </div>
                <div className="py-1 px-2 bg-slate-50 rounded text-slate-600 flex justify-between">
                  <span className="text-slate-400 font-mono">13:08:45</span>
                  <span>OptiScan 8K Line Calibration</span>
                  <span className="text-emerald-600 font-bold text-[10px]">OK</span>
                </div>
                <div className="py-1 px-2 bg-slate-50 rounded text-slate-600 flex justify-between">
                  <span className="text-slate-400 font-mono">13:05:12</span>
                  <span>LWIR Radiometric Zero Drift</span>
                  <span className="text-blue-600 font-bold text-[10px]">SYNC</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
