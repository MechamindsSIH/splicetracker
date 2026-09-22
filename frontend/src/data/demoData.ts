/**
 * Local demo mirror used only when the API is unavailable. It mirrors the four
 * conveyor assets and sixteen splices in backend/app/database/seed_database.py,
 * so the dashboard stays presentable for offline demos without masking live data.
 */
const makeSplice = (id: number, belt_id: string, name: string, position: number, condition: string, risk_level: string, severity: number) => ({
  id, belt_id, name, position, condition, risk_level, severity,
  confidence: Number((0.89 + (id % 8) * 0.01).toFixed(2)),
  installed_date: `202${id % 4}-0${(id % 8) + 1}-15T08:00:00Z`,
});

export const demoSplices = [
  makeSplice(1, 'BELT-01', 'Splice-001', 120, 'GOOD', 'LOW', 0.06),
  makeSplice(2, 'BELT-01', 'Splice-002', 360, 'GOOD', 'LOW', 0.08),
  makeSplice(3, 'BELT-01', 'Splice-003', 600, 'FAIR', 'MODERATE', 0.28),
  makeSplice(4, 'BELT-01', 'Splice-004', 840, 'DEGRADED', 'HIGH', 0.62),
  makeSplice(5, 'BELT-01', 'Splice-005', 1080, 'GOOD', 'LOW', 0.04),
  makeSplice(6, 'BELT-02', 'Splice-101', 45, 'GOOD', 'LOW', 0.05),
  makeSplice(7, 'BELT-02', 'Splice-102', 150, 'GOOD', 'LOW', 0.04),
  makeSplice(8, 'BELT-02', 'Splice-103', 270, 'FAIR', 'LOW', 0.22),
  makeSplice(9, 'BELT-02', 'Splice-104', 390, 'GOOD', 'LOW', 0.07),
  makeSplice(10, 'BELT-03', 'Splice-201', 60, 'GOOD', 'LOW', 0.05),
  makeSplice(11, 'BELT-03', 'Splice-202', 180, 'CRITICAL', 'CRITICAL', 0.91),
  makeSplice(12, 'BELT-03', 'Splice-203', 280, 'GOOD', 'LOW', 0.03),
  makeSplice(13, 'BELT-04', 'Splice-301', 90, 'GOOD', 'LOW', 0.06),
  makeSplice(14, 'BELT-04', 'Splice-302', 260, 'POOR', 'HIGH', 0.74),
  makeSplice(15, 'BELT-04', 'Splice-303', 440, 'GOOD', 'LOW', 0.08),
  makeSplice(16, 'BELT-04', 'Splice-304', 590, 'GOOD', 'LOW', 0.02),
];

export const demoAssets: Record<string, { name: string; length: string; speed: string }> = {
  'BELT-01': { name: 'Overland Main Line 1', length: '1,200 m', speed: '4.2 m/s' },
  'BELT-02': { name: 'In-Plant Secondary Feeder', length: '450 m', speed: '2.5 m/s' },
  'BELT-03': { name: 'Stacker Staging Conveyor', length: '320 m', speed: '3.1 m/s' },
  'BELT-04': { name: 'Decline Transfer Line', length: '680 m', speed: '3.8 m/s' },
};

export const demoStatus = { components: { camera: 'online', thermal: 'online', conductive: 'online', mechanical: 'online' } };
export const demoAnalytics = {
  total_inspections: 17520, inspection_count: 17520, total_anomalies: 1248, anomaly_count: 1248, total_alerts: 312, alert_count: 312, active_alerts: 3,
  risk_distribution: { LOW: 9, MODERATE: 2, HIGH: 3, CRITICAL: 2 },
  defect_frequency: { surface_wear: 486, edge_crack: 308, splice_separation: 236, thermal_hotspot: 218 },
  condition_trends: Array.from({ length: 18 }, (_, i) => ({ timestamp: new Date(Date.now() - (17 - i) * 3600000).toISOString(), condition: ['NORMAL', 'MINOR_ANOMALY', 'WARNING', 'DEGRADING', 'HIGH_RISK'][Math.min(4, Math.floor(i / 4))], splice_id: i < 11 ? 4 : 11 })),
};
export const demoAlerts = [
  { id: 301, splice_id: 11, severity: 'CRITICAL', risk_score: 0.91, defect_type: 'splice_separation', location: 'BELT-03:180m', reason: 'Multi-sensor corroboration on Splice-202.', status: 'ACTIVE', timestamp: '2026-09-08T08:14:00Z' },
  { id: 302, splice_id: 14, severity: 'HIGH', risk_score: 0.74, defect_type: 'edge_crack', location: 'BELT-04:260m', reason: 'Accelerating edge damage trend.', status: 'ACTIVE', timestamp: '2026-09-08T07:48:00Z' },
  { id: 303, splice_id: 4, severity: 'WARNING', risk_score: 0.62, defect_type: 'surface_wear', location: 'BELT-01:840m', reason: 'Condition threshold crossed.', status: 'ACTIVE', timestamp: '2026-09-08T07:21:00Z' },
  { id: 304, splice_id: 8, severity: 'WARNING', risk_score: 0.43, defect_type: 'thermal_hotspot', location: 'BELT-02:270m', reason: 'Thermal delta exceeds the operating baseline by 8.2°C.', status: 'ACTIVE', timestamp: '2026-09-08T06:54:00Z' },
  { id: 305, splice_id: 3, severity: 'WARNING', risk_score: 0.38, defect_type: 'tracking_deviation', location: 'BELT-01:600m', reason: 'Lateral tracking drift detected across three scan windows.', status: 'ACKNOWLEDGED', timestamp: '2026-09-08T06:32:00Z' },
  { id: 306, splice_id: 12, severity: 'HIGH', risk_score: 0.69, defect_type: 'vibration_rms', location: 'BELT-03:280m', reason: 'Vibration RMS and kurtosis exceeded warning profile.', status: 'ACKNOWLEDGED', timestamp: '2026-09-08T05:48:00Z' },
  { id: 307, splice_id: 9, severity: 'WARNING', risk_score: 0.34, defect_type: 'cover_bulge', location: 'BELT-02:390m', reason: 'Vision model detected cover deformation near the splice boundary.', status: 'RESOLVED', timestamp: '2026-09-08T05:12:00Z' },
  { id: 308, splice_id: 15, severity: 'WARNING', risk_score: 0.31, defect_type: 'loop_continuity', location: 'BELT-04:440m', reason: 'Single transient conductive loop interruption recorded.', status: 'RESOLVED', timestamp: '2026-09-08T04:45:00Z' },
  { id: 309, splice_id: 5, severity: 'WARNING', risk_score: 0.29, defect_type: 'surface_wear', location: 'BELT-01:1080m', reason: 'Abrasion trend is approaching the configured inspection threshold.', status: 'RESOLVED', timestamp: '2026-09-08T03:27:00Z' },
];

export const demoAnomalies = [
  ['ANM-8821', 'Vision', 'Splice separation', 'BELT-03 / 180 m', '91%', 'CRITICAL'],
  ['ANM-8816', 'Thermal', 'Hotspot +8.2°C', 'BELT-02 / 270 m', '78%', 'HIGH'],
  ['ANM-8811', 'Mechanical', 'RMS vibration excursion', 'BELT-03 / 280 m', '74%', 'HIGH'],
  ['ANM-8807', 'Vision', 'Edge crack growth', 'BELT-04 / 260 m', '71%', 'HIGH'],
  ['ANM-8799', 'Tracking', 'Lateral drift', 'BELT-01 / 600 m', '63%', 'WARNING'],
  ['ANM-8793', 'Conductive', 'Transient loop interruption', 'BELT-04 / 440 m', '58%', 'WARNING'],
];

export const demoPipelineStages = ['Camera', 'Preprocessing', 'Vision Processing', 'Sensor Fusion', 'DIVE', 'ATCE', 'Temporal Twin', 'Risk Engine', 'Localization', 'Alert', 'Pipeline'].map((name, index) => ({
  name, status: index === 3 ? 'processing' : 'completed', last_event: new Date(Date.now() - index * 1200).toISOString(), processing_result: index === 3 ? 'Fusing four sensor modalities' : 'Operational', error_state: null,
}));

export const demoSystemHealth = {
  components: ['camera', 'thermal', 'conductive', 'mechanical', 'belt_position', 'backend', 'database', 'websocket'].map(name => ({ name, last_update: new Date().toISOString(), error_count: 0 })),
  database_latency_ms: 14, last_inspection: new Date(Date.now() - 18000).toISOString(),
};
export const demoSystemStatus = { ...demoStatus, simulation_mode: true, total_splices: 16, total_inspections: 17520 };
