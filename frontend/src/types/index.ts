export interface Splice {
  id: number;
  name: string;
  belt_id: string;
  position: number;
  condition: string;
  severity: string;
  confidence: number;
  risk_level: string;
  created_at: string;
  updated_at: string;
}

export interface Inspection {
  id: number;
  splice_id: number;
  started_at: string;
  completed_at: string;
  status: string;
  results: Record<string, any>;
}

export interface Alert {
  id: number;
  splice_id: number;
  timestamp: string;
  severity: string;
  defect_type: string;
  confidence: number;
  risk_score: number;
  reason: string;
  recommended_action: string;
  status: string;
  acknowledged_at: string | null;
  location: string;
}

export interface SensorData {
  sensor_type: string;
  anomaly_score: number;
  confidence: number;
  timestamp: string;
  details: Record<string, any>;
}

export interface FusionResult {
  overall_confidence: number;
  supporting_sensors: string[];
  contradicting_sensors: string[];
  fusion_status: string;
  evidence: Record<string, any>;
  vision_score: number;
  thermal_score: number;
  mechanical_score: number;
  conductive_score: number;
}

export interface DIVEEvent {
  event_id: string;
  event_type: string;
  evidence: string[];
  supporting_sensors: string[];
  confidence: number;
  persistence_count: number;
  status: string;
  start_time: string;
}

export interface ATCEResult {
  previous_state: string;
  current_state: string;
  trend: string;
  persistence: number;
  recurrence: boolean;
  classification: string;
}

export interface SpliceState {
  splice_id: string;
  condition: string;
  severity: string;
  confidence: number;
  risk_level: string;
  trend: string;
  recent_events: any[];
  last_inspection: string;
  history: Array<{ timestamp: string; condition: string }>;
}

export interface RiskResult {
  risk_score: number;
  risk_level: string;
  risk_trend: string;
  contributing_factors: Array<{ factor: string; score: number; description: string }>;
  recommended_action: string;
  confidence: number;
}

export interface SystemHealth {
  backend: string;
  database: string;
  websocket: string;
  camera: string;
  thermal: string;
  conductive: string;
  mechanical: string;
  simulation: string;
}

export interface PipelineStage {
  name: string;
  status: string;
  last_event: string;
  processing_result: string;
  error_state: string | null;
}

export interface Analytics {
  inspection_count: number;
  anomaly_count: number;
  alert_count: number;
  risk_distribution: Record<string, number>;
  condition_trends: Array<{ timestamp: string; condition: string; splice_id: number }>;
  defect_frequency: Record<string, number>;
}

export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

export interface SimulationStatus {
  running: boolean;
  scenario: string | null;
  current_step: number;
  total_steps: number;
  available_scenarios: Record<string, { name: string; description: string; duration_steps: number }>;
}
