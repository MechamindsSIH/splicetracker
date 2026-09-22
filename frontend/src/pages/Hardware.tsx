import { useCallback } from 'react';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { demoSystemHealth, demoSystemStatus } from '../data/demoData';

export default function Hardware() {
  const { data } = usePolling(useCallback(() => api.getSystemHealth(), []), 5000);
  const { data: status } = usePolling(useCallback(() => api.getSystemStatus(), []), 5000);

  const components = data?.components?.length ? data.components : demoSystemHealth.components;
  const systemStatus = status || demoSystemStatus;
  const sysComponents = systemStatus.components || {};

  const hardwareItems = [
    { name: 'Camera', key: 'camera', description: 'USB webcam or simulation camera provider' },
    { name: 'Thermal Sensor', key: 'thermal', description: 'Temperature monitoring for splice region' },
    { name: 'Conductive Sensor', key: 'conductive', description: 'Continuity loop for break detection' },
    { name: 'Mechanical Sensor', key: 'mechanical', description: 'Vibration/accelerometer for motion analysis' },
    { name: 'Belt Position', key: 'belt_position', description: 'Encoder or estimated belt coordinate tracking' },
    { name: 'Backend', key: 'backend', description: 'FastAPI application server' },
    { name: 'Database', key: 'database', description: 'SQLite database' },
    { name: 'WebSocket', key: 'websocket', description: 'Real-time event broadcast' },
  ];

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">Hardware Status</h2>

      <div className="grid grid-cols-2 gap-4">
        {hardwareItems.map(h => {
          const comp = components.find?.((c: any) => c.name === h.key) || {};
          const online = sysComponents[h.key] === 'online' || sysComponents[h.key] === 'connected';
          return (
            <div key={h.key} className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">{h.name}</span>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-500' : 'bg-red-500'}`} />
                  <span className={`text-xs font-medium ${online ? 'text-emerald-600' : 'text-red-600'}`}>
                    {online ? 'ONLINE' : 'OFFLINE'}
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-500 mb-2">{h.description}</p>
              <div className="text-[10px] text-slate-400 space-y-0.5">
                {comp.last_update && <div>Last update: <span className="font-mono">{new Date(comp.last_update).toLocaleTimeString()}</span></div>}
                {comp.error_count !== undefined && <div>Errors: <span className="font-mono">{comp.error_count}</span></div>}
              </div>
            </div>
          );
        })}
      </div>

      {systemStatus.simulation_mode && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-amber-700">Simulation Mode Active</span>
          </div>
          <p className="text-xs text-amber-600">All sensors are running in simulation mode. Hardware readings are synthetic.</p>
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs text-slate-500 mb-3">System Metrics</h3>
        <div className="grid grid-cols-4 gap-4 text-xs text-slate-600">
          <div>Database latency: <span className="font-mono">{data?.database_latency_ms ?? demoSystemHealth.database_latency_ms}ms</span></div>
          <div>Last inspection: <span className="font-mono">{new Date(data?.last_inspection || demoSystemHealth.last_inspection).toLocaleTimeString()}</span></div>
          <div>Total splices: <span className="font-mono">{systemStatus.total_splices || 0}</span></div>
          <div>Total inspections: <span className="font-mono">{systemStatus.total_inspections || 0}</span></div>
        </div>
      </div>
    </div>
  );
}
