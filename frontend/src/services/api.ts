const API_BASE = '/api';

async function get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function put<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => get('/health'),
  getSystemStatus: () => get('/system/status'),
  getSystemHealth: () => get('/system/health'),
  getSplices: () => get('/splices'),
  getSplice: (id: number) => get(`/splices/${id}`),
  getSpliceHistory: (id: number) => get(`/splices/${id}/history`),
  getInspections: (params?: any) => get('/inspections', params),
  getInspection: (id: number) => get(`/inspections/${id}`),
  getAlerts: (params?: any) => get('/alerts', params),
  acknowledgeAlert: (id: number) => post(`/alerts/${id}/acknowledge`),
  getAnalytics: () => get('/analytics'),
  getConfig: () => get('/config'),
  updateConfig: (data: any) => put('/config', data),
  startSimulation: (params?: any) => post('/simulation/start', params || {}),
  stopSimulation: () => post('/simulation/stop'),
  getSimulationStatus: () => get('/simulation/status'),
  stepSimulation: (data?: any) => post('/simulation/step', data || {}),
  runScenario: (scenario: string, splice_id?: number) => post('/simulation/scenario', { scenario, splice_id }),
  getEvents: (params?: any) => get('/events', params),
  getEvent: (id: number) => get(`/events/${id}`),
  getPipelineStatus: () => get('/pipeline/status'),
};
