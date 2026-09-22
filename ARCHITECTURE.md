# SpliceTracker — Architecture Document

## System Overview

SpliceTracker is a multi-modal industrial splice monitoring system that combines computer vision, thermal analysis, conductive sensing, and mechanical vibration analysis to detect, classify, and track conveyor belt splice conditions over time.

## Full Pipeline

```
PHYSICAL CONVEYOR BELT
        │
  ┌─────┼─────┬──────────┬──────────┐
  │     │     │          │          │
Camera Thermal Conductive Mechanical Belt Encoder
  │     │     │          │          │
  └─────┼─────┴──────────┴──────────┘
        │
  DATA ACQUISITION (Hardware Abstraction Layer)
        │
  TIME SYNCHRONIZATION (SignalSynchronizer)
        │
  SIGNAL PROCESSING
  ├── VisionProcessor (OpenCV pipeline)
  ├── ThermalProcessor (baseline tracking)
  └── MechanicalProcessor (FFT features)
        │
  SENSOR FUSION (SensorFusionEngine)
  - Weighted combination
  - Agreement detection
  - Evidence collection
        │
  DIVE — Defect Intelligence & Validation Engine
  - Event grouping
  - Persistence tracking
  - Classification
        │
  ATCE — Adaptive Temporal Correlation Engine
  - History correlation
  - Trend detection
  - Recurrence analysis
        │
  TEMPORAL DIGITAL TWIN
  - Per-splice state machine
  - Condition tracking
  - History maintenance
        │
  RISK ENGINE
  - Factor-based scoring (0-100)
  - Level classification
  - Action recommendation
        │
  LOCALIZATION
  - Belt coordinate mapping
  - Splice position tracking
        │
  ┌─────┴─────┐
  │           │
ALERTS    DASHBOARD
  │           │
Database  WebSocket → React UI
```

## Component Descriptions

### Hardware Abstraction Layer
Abstract base classes for each sensor type with simulation and real provider implementations. The intelligence layer is hardware-agnostic.

- **CameraProvider**: Frame capture (USB webcam or simulation)
- **ThermalProvider**: Temperature readings
- **ConductiveProvider**: Continuity sensing
- **MechanicalProvider**: Vibration/accelerometer data
- **BeltPositionProvider**: Belt coordinate tracking
- **HardwareManager**: Unified initialization and reading

### Signal Processing
- **VisionProcessor**: Frame preprocessing, ROI detection, feature extraction, anomaly detection, optical flow (Farneback), deformation analysis
- **ThermalProcessor**: Running baseline, delta calculation, rate of change, anomaly scoring
- **MechanicalProcessor**: RMS/peak/variance computation, FFT frequency features, baseline comparison
- **SignalSynchronizer**: Time-window based multi-sensor event correlation

### Intelligence Pipeline
- **SensorFusionEngine**: Weighted multi-modal fusion with agreement detection. Outputs confidence, supporting/contradicting sensors, evidence
- **DIVEEngine**: Groups observations into events (EVT-XXXXXX), tracks persistence, classifies event types
- **ATCEEngine**: Correlates current events with history, detects trends (IMPROVING/STABLE/WORSENING), identifies recurrence
- **TemporalDigitalTwin**: Per-splice state machine (NORMAL → MINOR_ANOMALY → WARNING → DEGRADING → HIGH_RISK → CRITICAL)
- **RiskEngine**: Factor-based scoring (0-100) with explainable contributing factors and recommended actions
- **IntelligencePipeline**: Orchestrates the full chain: fusion → DIVE → ATCE → twin → risk → alert

### Alert Engine
Generates alerts when risk thresholds are exceeded. Severity levels: NORMAL, WARNING, HIGH, CRITICAL. Each alert includes reason, evidence, and recommended action.

### Localization
Maps events to belt coordinates and splice positions. Supports encoder-based and estimation-based position tracking.

### Simulation Engine
Provides complete sensor simulation with configurable scenarios. Uses the same backend processing path as real hardware.

## Database Architecture

SQLite with SQLAlchemy async ORM. Key entities:

- **Splice** → has many Inspections, ConditionHistory, Alerts
- **Inspection** → has many SensorMeasurements, VisionEvents, ThermalEvents, etc.
- **FusionResult** → links to Inspection, has DIVEEvent
- **DIVEEvent** → has ATCEResult
- **Alert** → links to Splice

All entities have timestamps, proper foreign keys, and indexes.

## API Architecture

- **REST API**: FastAPI with Pydantic validation, async handlers, structured responses
- **WebSocket**: Real-time event broadcasting to connected dashboard clients
- **Event Types**: sensor_update, inspection_completed, defect_detected, fusion_updated, condition_updated, risk_updated, alert_created, hardware_status, system_status

## Frontend Architecture

React 18 + TypeScript + Vite + Tailwind CSS:

- **Pages**: Dashboard, LiveInspection, SpliceDetail, ConditionHistory, TemporalTwin, Alerts, Analytics, Hardware, Simulation, Settings, PipelineView, EventInspector
- **Services**: API client (fetch-based), WebSocket client (auto-reconnect)
- **Hooks**: useWebSocket, usePolling, useSplices, useAlerts, useSystemHealth
- **State**: React Context store for global state
- **Charts**: Recharts for condition trends, risk distribution, analytics

## Event System

AsyncIO-based event bus for internal pub/sub:
- Backend components publish events
- WebSocket manager subscribes and broadcasts to clients
- Loose coupling between producers and consumers

## Security

- Input validation via Pydantic
- Safe filesystem handling (no directory traversal)
- Environment-based configuration (no hardcoded secrets)
- Controlled CORS
- Error handling without internal leakage
