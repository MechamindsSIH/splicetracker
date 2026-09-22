# SpliceTracker — Simulation Guide

## Starting Simulation Mode

Set in `.env`:
```
SIMULATION_MODE=true
```

The system starts in simulation mode by default. All sensor providers use synthetic data.

## Running Simulations

### Via Dashboard
1. Navigate to **Simulation** page
2. Click a scenario card
3. Watch real-time progress

### Via API
```bash
# Start specific scenario
curl -X POST http://localhost:8000/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario": "demo"}'

# Stop simulation
curl -X POST http://localhost:8000/api/simulation/stop
```

## Available Scenarios

### normal (5 steps)
Normal splice operation with no defects. All sensors report near-zero anomaly scores. Baseline behavior for the system.

### visual_anomaly (5 steps)
Camera detects a visual defect while other sensors remain mostly normal. Demonstrates single-sensor anomaly handling — low confidence since only one modality confirms.

### thermal_anomaly (5 steps)
Elevated temperature at splice region. Thermal anomaly score escalates while other sensors stay low. Demonstrates thermal monitoring capability.

### conductive_break (4 steps)
Conductive continuity loop breaks. Binary event — splice loop goes from CLOSED to OPEN. Demonstrates break detection.

### mechanical_anomaly (5 steps)
Abnormal vibration pattern. Mechanical sensor shows increasing RMS, peak, and variance while others stay low.

### multi_sensor (4 steps)
Multiple sensors detect anomalies simultaneously. Vision, thermal, and mechanical all escalate together, then conductive breaks. Demonstrates sensor corroboration and high-confidence detection.

### progressive_degradation (8 steps)
**Key scenario.** Gradually worsening condition over 8 inspections:
1. Normal
2. Slight visual anomaly
3. Vision + thermal begin
4. Multi-sensor moderate
5. Escalating
6. High multi-sensor
7. Severe
8. Critical with conductive break

Demonstrates the temporal intelligence pipeline: how DIVE groups events, ATCE detects worsening trend, Twin transitions through condition states, and Risk Engine escalates.

### high_risk (4 steps)
Rapid escalation to critical risk. Aggressive anomaly scores across all sensors. Demonstrates alert generation for severe conditions.

### resolved (7 steps)
Defect that peaks and then improves. Anomaly scores rise to moderate levels then decrease back to normal. Demonstrates the system's ability to track improvement and resolve conditions.

### demo (13 steps)
**Full demonstration sequence** showing the complete intelligence chain:

| Step | Description |
|------|-------------|
| 1 | Normal operation |
| 2 | Splice detected, normal |
| 3 | Visual anomaly appears |
| 4 | Thermal anomaly develops |
| 5 | Mechanical anomaly joins |
| 6 | Multi-sensor corroboration |
| 7 | Temporal validation — persistent |
| 8 | Condition degrading |
| 9 | Risk increasing |
| 10 | Conductive break — high risk |
| 11 | Belt coordinate localized |
| 12 | High priority alert generated |
| 13 | Maintenance action recommended |

This is the recommended scenario for SIH demonstrations.

## What Happens During Simulation

1. SimulationEngine sets anomaly levels on hardware providers
2. HardwareManager reads from all providers
3. Observations pass through the full intelligence pipeline
4. Results are published via WebSocket to dashboard
5. Database records are created for each inspection
6. The dashboard updates in real-time

The simulation uses the **exact same processing path** as real hardware. The only difference is data source.

## Inspection Interval

Default: 3 seconds between inspection steps. Configurable in SimulationEngine.

## Custom Scenarios

Edit `backend/app/simulation/scenarios.py` to add scenarios. Each step specifies:
```python
{"step": N, "vision": 0.0-1.0, "thermal": 0.0-1.0, "mechanical": 0.0-1.0, "conductive": bool}
```
