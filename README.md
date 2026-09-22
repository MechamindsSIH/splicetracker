# SpliceTracker — Industrial Conveyor Belt Splice Monitoring System

## Overview

SpliceTracker is an industrial conveyor-belt splice monitoring and predictive-maintenance prototype. It observes splice condition through multiple sensor modalities (vision, thermal, conductive, mechanical), fuses observations through an intelligence pipeline, and provides real-time condition assessment, risk scoring, and maintenance alerts.

## Architecture

```
              PHYSICAL CONVEYOR
                     │
        ┌────────────┼────────────┐
        │            │            │
     CAMERA       THERMAL     SENSORS
        │            │            │
        └────────────┼────────────┘
                     │
              DATA ACQUISITION
                     │
             TIME SYNCHRONIZATION
                     │
             SIGNAL PROCESSING
                     │
          ┌──────────┴──────────┐
          │                     │
   COMPUTER VISION       SENSOR ANALYSIS
          │                     │
          └──────────┬──────────┘
                     │
               SENSOR FUSION
                     │
            DIVE (Event Intelligence)
                     │
            ATCE (Temporal Correlation)
                     │
           TEMPORAL DIGITAL TWIN
                     │
                RISK ENGINE
                     │
              LOCALIZATION
                     │
          ┌──────────┴──────────┐
          │                     │
      DASHBOARD              ALERTS
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy, asyncio |
| Database | SQLite (via aiosqlite) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Vision | OpenCV, NumPy, SciPy |
| Real-time | WebSockets |
| Charts | Recharts |

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+

## Installation

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

Key settings:
- `SIMULATION_MODE=true` — Run with simulated sensors (default)
- `DATABASE_URL=sqlite+aiosqlite:///./data/splicetracker.db`
- `CAMERA_INDEX=0` — USB camera index
- `BELT_SPEED=2.0` — Belt speed in m/s
- `LOG_LEVEL=INFO`

## Starting the System

### Backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev
```

Dashboard: http://localhost:3000
API docs: http://localhost:8000/docs

## Running Simulation

The system starts in simulation mode by default. Use the Simulation page or API:

```bash
# Start simulation with demo scenario
curl -X POST http://localhost:8000/api/simulation/start -H "Content-Type: application/json" -d '{"scenario": "demo"}'

# Available scenarios: normal, visual_anomaly, thermal_anomaly, conductive_break,
# mechanical_anomaly, multi_sensor, progressive_degradation, high_risk, resolved, demo
```

## Dashboard Pages

| Page | Description |
|------|-------------|
| Dashboard | Live system overview with all key metrics |
| Live Inspection | Camera feed and current sensor readings |
| Splice Detail | Detailed condition of selected splice |
| Condition History | Historical degradation timeline |
| Temporal Twin | Time-evolving splice state digital twin |
| Alerts | Active and historical alerts management |
| Analytics | Trends, aggregated data, risk distribution |
| Hardware | Sensor connection and health status |
| Simulation | Demo scenario control panel |
| Pipeline | Data processing pipeline visualization |
| Event Inspector | Deep dive into individual events |
| Settings | System configuration |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Health check |
| GET | /api/system/status | Full system status |
| GET | /api/system/health | Component health |
| GET | /api/splices | List all splices |
| GET | /api/splices/{id} | Splice detail |
| GET | /api/splices/{id}/history | Condition history |
| GET | /api/inspections | List inspections |
| GET | /api/inspections/{id} | Inspection detail |
| GET | /api/alerts | List alerts |
| POST | /api/alerts/{id}/acknowledge | Acknowledge alert |
| GET | /api/analytics | Aggregated analytics |
| GET | /api/config | Current configuration |
| PUT | /api/config | Update configuration |
| POST | /api/simulation/start | Start simulation |
| POST | /api/simulation/stop | Stop simulation |
| POST | /api/simulation/scenario | Run scenario |
| GET | /api/events | List events |
| GET | /api/events/{id} | Event detail |
| GET | /api/pipeline/status | Pipeline status |
| WS | /ws/live | Real-time WebSocket |

## Database

SQLite database with tables: splices, inspections, sensor_measurements, vision_events, thermal_events, conductive_events, mechanical_events, fusion_results, dive_events, atce_results, condition_history, alerts, system_events.

See `DATABASE_SCHEMA.md` for full schema.

## Testing

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## Project Structure

```
SpliceTracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration
│   │   ├── api/                 # REST API routes
│   │   ├── core/                # Event bus, schemas, logging
│   │   ├── database/            # SQLAlchemy models, repos
│   │   ├── hardware/            # Sensor providers
│   │   ├── processing/          # Signal processing, CV
│   │   ├── intelligence/        # Fusion, DIVE, ATCE, Twin, Risk
│   │   ├── localization/        # Belt position tracking
│   │   ├── alerts/              # Alert engine
│   │   └── simulation/          # Simulation engine, scenarios
│   ├── tests/                   # Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Dashboard pages
│   │   ├── layouts/             # App shell layout
│   │   ├── hooks/               # React hooks
│   │   ├── services/            # API + WebSocket clients
│   │   ├── stores/              # State management
│   │   ├── types/               # TypeScript interfaces
│   │   └── utils/               # Utilities
│   └── package.json
├── data/                        # Runtime data (frames, exports)
├── logs/                        # Application logs
├── config/                      # Configuration files
├── docs/                        # Additional documentation
├── PROJECT_LOG.txt              # Engineering log
├── CHECKPOINT.md                # Continuation checkpoint
├── ARCHITECTURE.md              # Architecture document
├── DEVELOPMENT_STATUS.md        # Development status
├── DECISIONS.md                 # Architectural decisions
├── API_CONTRACT.md              # API documentation
├── DATABASE_SCHEMA.md           # Database schema
├── HARDWARE_INTERFACE.md        # Hardware integration guide
├── SIMULATION_GUIDE.md          # Simulation guide
├── DEMO_GUIDE.md                # Demo guide
└── TEST_STATUS.md               # Test status
```

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Backend won't start | Check Python version (3.10+), install requirements |
| Frontend won't start | Check Node version (18+), run `npm install` |
| Database errors | Delete `data/splicetracker.db`, restart backend |
| WebSocket disconnects | Check backend is running, check browser console |
| No sensor data | Ensure SIMULATION_MODE=true in .env |
| Camera not found | Check CAMERA_INDEX in .env, verify webcam connection |
