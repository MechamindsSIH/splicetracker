# SpliceTracker — Output Catalog

## Subsystem Output Matrix

| Subsystem | Input | Processing | Output | DB Storage | API Endpoint | WS Event | Dashboard | Log |
|-----------|-------|-----------|--------|------------|-------------|----------|-----------|-----|
| Camera | USB frame / synthetic | Preprocessing, ROI | Frame + metadata | vision_events (frame_path) | GET /api/inspections/{id} | camera_update | Live Inspection | sensor.log |
| Thermal | Temp reading / synthetic | Baseline, delta, rate | Thermal analysis | thermal_events | GET /api/inspections/{id} | sensor_update | Dashboard sensor card | sensor.log |
| Conductive | Continuity bool / synthetic | State transition | Break event | conductive_events | GET /api/inspections/{id} | sensor_update | Dashboard sensor card | sensor.log |
| Mechanical | Vibration signal / synthetic | RMS, FFT, features | Mech analysis | mechanical_events | GET /api/inspections/{id} | sensor_update | Dashboard sensor card | sensor.log |
| Vision | Camera frame | OpenCV pipeline | Defect + confidence | vision_events | GET /api/inspections/{id} | defect_detected | Live Inspection | application.log |
| Optical Flow | Frame pair | Farneback | Displacement stats | vision_events (optical_flow_json) | GET /api/inspections/{id} | - | Live Inspection (detail) | - |
| Deformation | Optical flow field | Strain computation | Deformation metrics | vision_events (deformation_json) | GET /api/inspections/{id} | - | Event Inspector | - |
| Sensor Fusion | All sensor scores | Weighted fusion | Confidence + evidence | fusion_results | GET /api/inspections/{id} | fusion_updated | Dashboard fusion panel | application.log |
| DIVE | Fusion result | Event grouping | Event + persistence | dive_events | GET /api/events/{id} | - | Event Inspector | application.log |
| ATCE | DIVE event + history | Temporal correlation | Trend + classification | atce_results | GET /api/events/{id} | - | Event Inspector | application.log |
| Temporal Twin | ATCE + fusion + risk | State machine | Condition state | condition_history | GET /api/splices/{id} | condition_updated | Temporal Twin page | application.log |
| Risk Engine | Fusion + ATCE + twin | Factor scoring | Risk score + factors | (via inspections) | GET /api/splices/{id} | risk_updated | Dashboard risk gauge | application.log |
| Localization | Belt position provider | Coordinate mapping | Position + splice ID | (via events) | GET /api/splices/{id} | - | Splice Detail | - |
| Alerts | Risk result | Threshold check | Alert record | alerts | GET /api/alerts | alert_created | Alerts page | alerts.log |
| Simulation | Scenario config | Step progression | Sensor configs | system_events | POST /api/simulation/* | system_status | Simulation page | simulation.log |

## Output Detail Per Subsystem

### Camera
- Raw: numpy array (width x height x 3)
- Processed: grayscale, denoised, equalized
- Intermediate: ROI bounds, feature vector
- Final: splice_detected, defect_type, confidence
- DB: vision_events table
- Log: frame ID, timestamp, detection result

### Thermal
- Raw: temperature float
- Processed: baseline, delta, rate_of_change
- Final: thermal_anomaly_score
- DB: thermal_events table
- Log: temperature, delta, anomaly score

### Sensor Fusion
- Input: per-sensor anomaly scores
- Output: overall_confidence, supporting_sensors, fusion_status, evidence
- DB: fusion_results table
- WS: fusion_updated event
- Dashboard: fusion display with sensor checkmarks

### DIVE
- Input: fusion result
- Output: event_id (EVT-XXXXXX), event_type, persistence_count, status
- DB: dive_events table
- Dashboard: Event Inspector

### ATCE
- Input: DIVE event + condition history
- Output: trend, persistence, recurrence, classification
- DB: atce_results table
- Dashboard: Event Inspector

### Risk Engine
- Input: fusion + ATCE + twin state
- Output: risk_score (0-100), risk_level, contributing_factors, recommended_action
- Dashboard: risk gauge, factor breakdown
- Log: risk level changes

### Alerts
- Input: risk result exceeding threshold
- Output: alert with severity, reason, recommended_action
- DB: alerts table
- WS: alert_created event
- Dashboard: alerts panel, alerts page
- Log: alert creation, acknowledgement
