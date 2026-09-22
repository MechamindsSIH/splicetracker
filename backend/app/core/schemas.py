"""Pydantic models for all API request and response types."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Splice ─────────────────────────────────────────────────────────────────

class SpliceResponse(BaseModel):
    id: int
    name: str
    belt_id: str
    position: float
    installed_date: Optional[datetime] = None
    condition: str
    severity: float
    confidence: float
    risk_level: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SpliceListResponse(BaseModel):
    splices: List[SpliceResponse]
    total: int


# ── Inspection ─────────────────────────────────────────────────────────────

class InspectionResponse(BaseModel):
    id: int
    splice_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    results_json: Optional[str] = None

    model_config = {"from_attributes": True}


class SensorDataResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    sensor_type: str
    timestamp: datetime
    value_json: Optional[str] = None
    anomaly_score: float
    confidence: float
    raw_value_json: Optional[str] = None

    model_config = {"from_attributes": True}


class VisionEventResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    timestamp: datetime
    frame_path: Optional[str] = None
    roi_json: Optional[str] = None
    defect_type: Optional[str] = None
    defect_confidence: float
    bounding_region_json: Optional[str] = None
    optical_flow_json: Optional[str] = None
    deformation_json: Optional[str] = None
    anomaly_score: float

    model_config = {"from_attributes": True}


class ThermalEventResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    timestamp: datetime
    temperature: float
    baseline_temperature: float
    delta_temperature: float
    rate_of_change: float
    thermal_anomaly_score: float
    hotspot_location_json: Optional[str] = None

    model_config = {"from_attributes": True}


class ConductiveEventResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    timestamp: datetime
    continuity: bool
    previous_state: Optional[str] = None
    transition: Optional[str] = None
    duration_ms: float
    anomaly_score: float

    model_config = {"from_attributes": True}


class MechanicalEventResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    timestamp: datetime
    rms: float
    peak: float
    variance: float
    frequency_features_json: Optional[str] = None
    anomaly_score: float

    model_config = {"from_attributes": True}


class FusionResultResponse(BaseModel):
    id: int
    inspection_id: int
    splice_id: int
    timestamp: datetime
    vision_score: float
    thermal_score: float
    mechanical_score: float
    conductive_score: float
    supporting_sensors: Optional[str] = None
    contradicting_sensors: Optional[str] = None
    overall_confidence: float
    fusion_status: str
    evidence_json: Optional[str] = None

    model_config = {"from_attributes": True}


class DIVEEventResponse(BaseModel):
    id: int
    fusion_result_id: int
    splice_id: int
    event_type: str
    evidence_json: Optional[str] = None
    supporting_sensors_json: Optional[str] = None
    confidence: float
    start_time: datetime
    end_time: Optional[datetime] = None
    persistence_count: int
    status: str

    model_config = {"from_attributes": True}


class ATCEResultResponse(BaseModel):
    id: int
    dive_event_id: int
    splice_id: int
    timestamp: datetime
    previous_state: Optional[str] = None
    current_state: str
    trend: str
    persistence: int
    recurrence: bool
    history_json: Optional[str] = None

    model_config = {"from_attributes": True}


class InspectionDetailResponse(BaseModel):
    inspection: InspectionResponse
    sensor_data: List[SensorDataResponse] = []
    vision_events: List[VisionEventResponse] = []
    thermal_events: List[ThermalEventResponse] = []
    conductive_events: List[ConductiveEventResponse] = []
    mechanical_events: List[MechanicalEventResponse] = []
    fusion_results: List[FusionResultResponse] = []
    dive_events: List[DIVEEventResponse] = []
    atce_results: List[ATCEResultResponse] = []


# ── Condition History ──────────────────────────────────────────────────────

class ConditionHistoryResponse(BaseModel):
    id: int
    splice_id: int
    timestamp: datetime
    condition: str
    severity: float
    confidence: float
    risk_level: str
    trigger_event_id: Optional[int] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Alerts ─────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: int
    splice_id: int
    timestamp: datetime
    severity: str
    defect_type: Optional[str] = None
    confidence: float
    risk_score: float
    reason: Optional[str] = None
    recommended_action: Optional[str] = None
    status: str
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    location: Optional[str] = None

    model_config = {"from_attributes": True}


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(..., min_length=1, max_length=128)
    notes: Optional[str] = None


# ── System ─────────────────────────────────────────────────────────────────

class ComponentStatus(BaseModel):
    name: str
    status: str  # "online", "offline", "degraded"
    details: Optional[Dict[str, Any]] = None


class SystemStatusResponse(BaseModel):
    status: str  # "healthy", "degraded", "offline"
    uptime_seconds: float
    simulation_mode: bool
    components: List[ComponentStatus]
    active_splices: int
    active_alerts: int
    inspection_count: int
    last_inspection_at: Optional[datetime] = None


class SystemHealthResponse(BaseModel):
    status: str
    database: str
    event_bus: str
    websocket_connections: int
    memory_usage_mb: float
    cpu_percent: float
    uptime_seconds: float
    components: Dict[str, str]


class SystemEventResponse(BaseModel):
    id: int
    timestamp: datetime
    event_type: str
    module: str
    message: str
    details_json: Optional[str] = None
    severity: str

    model_config = {"from_attributes": True}


# ── Simulation ─────────────────────────────────────────────────────────────

class SimulationStartRequest(BaseModel):
    splice_count: int = Field(default=5, ge=1, le=50)
    inspection_interval_seconds: float = Field(default=10.0, ge=1.0, le=300.0)
    anomaly_probability: float = Field(default=0.15, ge=0.0, le=1.0)


class SimulationScenarioRequest(BaseModel):
    scenario: str = Field(..., description="Scenario name: normal, degrading, critical, intermittent, multi_defect")
    splice_id: Optional[int] = None
    duration_seconds: float = Field(default=60.0, ge=1.0, le=600.0)


# ── Config ─────────────────────────────────────────────────────────────────

class ConfigResponse(BaseModel):
    camera_index: int
    camera_width: int
    camera_height: int
    camera_fps: int
    thermal_enabled: bool
    conductive_enabled: bool
    mechanical_enabled: bool
    database_url: str
    belt_speed: float
    belt_length: float
    simulation_mode: bool
    log_level: str
    ws_heartbeat: int
    frame_buffer_size: int
    event_window_ms: int


class ConfigUpdateRequest(BaseModel):
    thermal_enabled: Optional[bool] = None
    conductive_enabled: Optional[bool] = None
    mechanical_enabled: Optional[bool] = None
    belt_speed: Optional[float] = Field(default=None, gt=0.0, le=20.0)
    belt_length: Optional[float] = Field(default=None, gt=0.0, le=10000.0)
    simulation_mode: Optional[bool] = None
    log_level: Optional[str] = None
    ws_heartbeat: Optional[int] = Field(default=None, ge=1, le=60)
    frame_buffer_size: Optional[int] = Field(default=None, ge=10, le=10000)
    event_window_ms: Optional[int] = Field(default=None, ge=100, le=5000)


# ── WebSocket ──────────────────────────────────────────────────────────────

class WebSocketMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = {}
    timestamp: Optional[datetime] = None


# ── Analytics ──────────────────────────────────────────────────────────────

class TimelineEntry(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    severity: Optional[str] = None
    splice_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class RiskResponse(BaseModel):
    splice_id: int
    splice_name: str
    risk_level: str
    risk_score: float
    condition: str
    contributing_factors: List[str] = []


class AnalyticsResponse(BaseModel):
    total_splices: int
    total_inspections: int
    total_anomalies: int
    total_alerts: int
    active_alerts: int
    risk_distribution: Dict[str, int]
    condition_distribution: Dict[str, int]
    recent_timeline: List[TimelineEntry] = []
    splice_risks: List[RiskResponse] = []


# ── Pipeline Status ───────────────────────────────────────────────────────

class PipelineStageStatus(BaseModel):
    name: str
    status: str  # "active", "idle", "error"
    last_processed_at: Optional[datetime] = None
    items_processed: int = 0
    error_count: int = 0


class PipelineStatusResponse(BaseModel):
    stages: List[PipelineStageStatus]
    overall_status: str
    throughput_per_second: float = 0.0
