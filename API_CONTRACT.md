# SpliceTracker — API Contract

API Version: 1.0
Base URL: `http://localhost:8000`
Authentication: None (prototype)

## Error Response Format
```json
{
  "detail": "Error description"
}
```

---

## Health & System

### GET /api/health
Health check.

**Response 200:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

### GET /api/system/status
Full system status including all components.

**Response 200:**
```json
{
  "status": "online",
  "simulation_mode": true,
  "uptime_seconds": 3600,
  "components": {
    "backend": "online",
    "database": "online",
    "websocket": "connected",
    "camera": "online",
    "thermal": "online",
    "conductive": "online",
    "mechanical": "online",
    "simulation": "running"
  },
  "active_alerts": 2,
  "total_splices": 5,
  "total_inspections": 142
}
```

### GET /api/system/health
Detailed component health with last update times.

**Response 200:**
```json
{
  "components": [
    {
      "name": "camera",
      "status": "online",
      "last_update": "2024-01-01T00:00:00Z",
      "error_count": 0,
      "details": {}
    }
  ],
  "database_latency_ms": 2,
  "last_inspection": "2024-01-01T00:00:00Z"
}
```

---

## Splices

### GET /api/splices
List all splices with current condition.

**Response 200:**
```json
{
  "splices": [
    {
      "id": 1,
      "name": "SP-001",
      "belt_id": "B-01",
      "position": 12.43,
      "condition": "NORMAL",
      "severity": "NONE",
      "confidence": 0.95,
      "risk_level": "LOW",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 5
}
```

### GET /api/splices/{id}
Get splice detail including latest sensor data and twin state.

**Response 200:**
```json
{
  "splice": { ... },
  "twin_state": {
    "condition": "DEGRADING",
    "severity": "MEDIUM",
    "confidence": 0.87,
    "risk_level": "HIGH",
    "trend": "WORSENING",
    "recent_events": [],
    "last_inspection": "2024-01-01T00:00:00Z"
  },
  "latest_readings": { ... }
}
```

### GET /api/splices/{id}/history
Get condition history for a splice.

**Response 200:**
```json
{
  "splice_id": 1,
  "history": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "condition": "NORMAL",
      "severity": "NONE",
      "confidence": 0.95,
      "risk_level": "LOW",
      "trigger_event_id": null
    }
  ]
}
```

---

## Inspections

### GET /api/inspections
List inspections. Query params: `splice_id`, `limit` (default 50), `offset` (default 0).

**Response 200:**
```json
{
  "inspections": [
    {
      "id": 1,
      "splice_id": 1,
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:00:01Z",
      "status": "completed"
    }
  ],
  "total": 142
}
```

### GET /api/inspections/{id}
Get full inspection detail with all sensor data, fusion, DIVE, ATCE, risk.

**Response 200:**
```json
{
  "inspection": { ... },
  "sensor_measurements": [ ... ],
  "vision_events": [ ... ],
  "thermal_events": [ ... ],
  "conductive_events": [ ... ],
  "mechanical_events": [ ... ],
  "fusion_result": { ... },
  "dive_event": { ... },
  "atce_result": { ... },
  "risk_result": { ... }
}
```

---

## Alerts

### GET /api/alerts
List alerts. Query params: `severity`, `status` (ACTIVE/ACKNOWLEDGED/RESOLVED), `splice_id`, `limit`, `offset`.

**Response 200:**
```json
{
  "alerts": [
    {
      "id": 1,
      "splice_id": 1,
      "timestamp": "2024-01-01T00:00:00Z",
      "severity": "HIGH",
      "defect_type": "progressive_anomaly",
      "confidence": 0.89,
      "risk_score": 78,
      "reason": "Repeated visual + thermal + mechanical anomalies",
      "recommended_action": "Inspect splice at next safe maintenance opportunity",
      "status": "ACTIVE",
      "acknowledged_at": null,
      "location": "12.43 m"
    }
  ],
  "total": 5
}
```

### POST /api/alerts/{id}/acknowledge
Acknowledge an alert.

**Request:**
```json
{
  "acknowledged_by": "operator"
}
```

**Response 200:**
```json
{
  "id": 1,
  "status": "ACKNOWLEDGED",
  "acknowledged_at": "2024-01-01T00:00:00Z",
  "acknowledged_by": "operator"
}
```

---

## Analytics

### GET /api/analytics

**Response 200:**
```json
{
  "inspection_count": 142,
  "anomaly_count": 23,
  "alert_count": 5,
  "risk_distribution": {
    "LOW": 85,
    "MEDIUM": 34,
    "HIGH": 18,
    "CRITICAL": 5
  },
  "condition_trends": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "condition": "NORMAL",
      "splice_id": 1
    }
  ],
  "defect_frequency": {
    "visual": 12,
    "thermal": 8,
    "mechanical": 6,
    "conductive": 2
  }
}
```

---

## Configuration

### GET /api/config
Get current configuration.

**Response 200:**
```json
{
  "camera_index": 0,
  "camera_width": 1280,
  "camera_height": 720,
  "camera_fps": 30,
  "thermal_enabled": true,
  "conductive_enabled": true,
  "mechanical_enabled": true,
  "belt_speed": 2.0,
  "belt_length": 100.0,
  "simulation_mode": true,
  "log_level": "INFO"
}
```

### PUT /api/config
Update configuration.

**Request:** Partial config object (only fields to update).

**Response 200:** Full updated config.

---

## Simulation

### POST /api/simulation/start
Start simulation.

**Request:**
```json
{
  "scenario": "demo"
}
```

**Response 200:**
```json
{
  "status": "started",
  "scenario": "demo",
  "message": "Simulation started with scenario: demo"
}
```

### POST /api/simulation/stop

**Response 200:**
```json
{
  "status": "stopped",
  "message": "Simulation stopped"
}
```

### POST /api/simulation/scenario
Run a specific scenario.

**Request:**
```json
{
  "scenario": "progressive_degradation"
}
```

**Response 200:**
```json
{
  "status": "running",
  "scenario": "progressive_degradation",
  "total_steps": 8,
  "description": "Gradually worsening splice condition"
}
```

---

## Events

### GET /api/events
List recent events. Query params: `limit` (default 50), `splice_id`.

**Response 200:**
```json
{
  "events": [
    {
      "event_id": "EVT-000142",
      "event_type": "progressive_anomaly",
      "splice_id": 1,
      "confidence": 0.91,
      "persistence_count": 4,
      "status": "ACTIVE",
      "start_time": "2024-01-01T00:00:00Z",
      "supporting_sensors": ["vision", "thermal", "mechanical"]
    }
  ],
  "total": 42
}
```

### GET /api/events/{id}
Full event detail (Event Inspector).

**Response 200:**
```json
{
  "event": { ... },
  "raw_inputs": { ... },
  "processed_signals": { ... },
  "fusion_result": { ... },
  "atce_result": { ... },
  "risk_result": { ... },
  "localization": { ... },
  "alert": { ... }
}
```

---

## Pipeline

### GET /api/pipeline/status
Data pipeline stage status.

**Response 200:**
```json
{
  "stages": [
    {
      "name": "Camera",
      "status": "active",
      "last_event": "2024-01-01T00:00:00Z",
      "processing_result": "Frame captured",
      "error_state": null
    },
    {
      "name": "Vision Processing",
      "status": "active",
      "last_event": "2024-01-01T00:00:00Z",
      "processing_result": "ROI detected",
      "error_state": null
    }
  ]
}
```

---

## WebSocket

### WS /ws/live
Real-time event stream.

**Event Types:**
```json
{
  "type": "sensor_update",
  "payload": { "sensor_type": "thermal", "data": { ... } },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

| Event Type | Payload Description |
|------------|-------------------|
| sensor_update | Individual sensor reading |
| camera_update | New frame processed |
| inspection_started | Inspection begun |
| inspection_completed | Inspection finished with results |
| defect_detected | Defect found by vision/fusion |
| fusion_updated | New fusion result |
| condition_updated | Splice condition changed |
| risk_updated | Risk level changed |
| alert_created | New alert generated |
| hardware_status | Sensor connection change |
| system_status | System state change |
