# SpliceTracker — Demo Guide

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+

### Install
```bash
# Backend
cd SpliceTracker/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## Starting the System

### Terminal 1 — Backend
```bash
cd SpliceTracker/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend
```bash
cd SpliceTracker/frontend
npm run dev
```

### Open Dashboard
Navigate to: `http://localhost:3000`

## Running the Demo

### Step 1: Verify System Online
- Check top-right: green dot + "ONLINE"
- Check Dashboard: all sensor indicators green
- WebSocket should show "connected"

### Step 2: Run Demo Scenario
- Navigate to **Simulation** page
- Click **Full Demo** card (the 13-step scenario)
- Or via API: `curl -X POST http://localhost:8000/api/simulation/scenario -H "Content-Type: application/json" -d '{"scenario": "demo"}'`

### Step 3: Observe the Pipeline (switch back to Dashboard)

The demo runs through 13 steps, ~3 seconds each:

| Step | What to show | Where to look |
|------|-------------|---------------|
| 1-2 | Normal operation | Dashboard: all green, risk 0 |
| 3 | Visual anomaly appears | Vision sensor card shows anomaly |
| 4 | Thermal joins | Thermal sensor card shows anomaly |
| 5 | Mechanical joins | Mechanical card, fusion shows 3 sensors |
| 6 | Corroboration | Fusion display: 3/4 supporting, HIGH_CONFIDENCE |
| 7 | Temporal validation | Events feed shows "persistent" |
| 8 | Condition degrades | Current Splice: condition changes to DEGRADING |
| 9 | Risk increases | Risk gauge climbs, level changes |
| 10 | Conductive break | 4th sensor joins, risk spikes |
| 11 | Localization | Position data updates |
| 12 | Alert generated | Active Alerts panel shows HIGH alert |
| 13 | Maintenance action | Alert recommendation visible |

### Step 4: Deep Dive (after demo completes)
- Click splice name to see **Splice Detail** with condition timeline
- Navigate to **Temporal Twin** to see splice state machine
- Navigate to **Alerts** to see full alert details
- Navigate to **Pipeline** to see processing chain status
- Navigate to **Analytics** to see aggregated charts

## Talking Points for Judges

### 1. Multi-Modal Sensing
"The system fuses four independent sensor modalities — not relying on any single sensor."

### 2. Temporal Intelligence
"A single anomaly doesn't trigger an alarm. The system tracks persistence and trends over time before escalating."

### 3. Explainability
"Every risk score shows contributing factors. Every alert shows evidence. The system explains WHY it reached its conclusion."

### 4. Traceability
"You can trace any HIGH RISK alert backwards through: Risk Engine → ATCE → DIVE → Fusion → individual sensor readings."

### 5. Architecture
"The entire pipeline runs through the same code path whether using real hardware or simulation. Simulation providers plug into the same abstraction layer."

### 6. Real Processing
"The computer vision uses actual OpenCV algorithms — Farneback optical flow, edge detection, texture analysis. Not fake scores."

## Troubleshooting During Demo

| Problem | Fix |
|---------|-----|
| Dashboard shows OFFLINE | Restart backend, check port 8000 |
| No WebSocket updates | Refresh browser page |
| Simulation not progressing | Check backend terminal for errors |
| No data on dashboard | Run a scenario first |
| Risk stays at 0 | Make sure demo scenario is running |
