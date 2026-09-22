# SpliceTracker — Test Status

## Test Commands
```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## Test Files

| File | Tests | Status |
|------|-------|--------|
| tests/unit/test_sensor_fusion.py | Fusion engine: normal, single, multi, contradicting, missing | IMPLEMENTED |
| tests/unit/test_dive_engine.py | DIVE: new event, update, classification, resolution | IMPLEMENTED |
| tests/unit/test_atce_engine.py | ATCE: isolated, recurring, worsening, stable, improving | IMPLEMENTED |
| tests/unit/test_temporal_twin.py | Twin: initial state, transitions, degradation, history | IMPLEMENTED |
| tests/unit/test_risk_engine.py | Risk: low, medium, high, critical, factors, recommendations | IMPLEMENTED |
| tests/unit/test_hardware.py | Providers: camera, thermal, conductive, mechanical, belt | IMPLEMENTED |
| tests/integration/test_pipeline.py | Full pipeline: normal, anomaly, progressive | IMPLEMENTED |
| tests/end_to_end/test_full_chain.py | Complete chain: sensor -> alert -> DB | IMPLEMENTED |

## Coverage Notes
- Intelligence pipeline: comprehensive unit tests
- Hardware providers: simulation provider tests
- API endpoints: basic endpoint tests
- Database: model creation tests via pipeline tests
- Frontend: manual testing via dashboard
