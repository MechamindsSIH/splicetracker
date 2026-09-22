"""Tests for the Temporal Digital Twin concept.

Since the project does not have a separate temporal_twin.py module, we test
the temporal tracking behaviour that is distributed across the ATCE engine
and the DIVE engine -- specifically the ability to track splice state over
time, detect condition transitions, and record state history.

These tests exercise the same logic the user described but through the
existing ATCEEngine which performs the temporal-twin role.
"""

import pytest
from datetime import datetime, timedelta

from backend.app.intelligence.atce_engine import ATCEEngine


def _dive_event(status="ACTIVE", score=0.6, confidence=0.7, event_type="multi_sensor_defect"):
    return {
        "event_id": "EVT-000001",
        "splice_id": "splice-1",
        "event_type": event_type,
        "status": status,
        "weighted_anomaly_score": score,
        "confidence": confidence,
        "supporting_sensors": ["vision", "thermal"],
        "persistence_count": 1,
    }


def _history(conditions, start=None):
    base = start or datetime(2026, 1, 1)
    return [
        {"condition": c, "timestamp": (base + timedelta(hours=i)).isoformat(),
         "severity": 0.0, "confidence": 0.8}
        for i, c in enumerate(conditions)
    ]


class TestTemporalDigitalTwin:
    """Tests for temporal state tracking via the ATCE engine."""

    @pytest.fixture
    def engine(self):
        return ATCEEngine()

    async def test_initial_state(self, engine):
        """A new splice with no history starts with NORMAL as previous state."""
        dive = _dive_event(status="RESOLVED", event_type="normal", score=0.0)
        result = await engine.analyze(dive, "splice-new", [])

        assert result.previous_state == "NORMAL"
        assert result.current_state == "NORMAL"

    async def test_condition_transition(self, engine):
        """An anomaly causes a condition change from NORMAL to a degraded state."""
        dive = _dive_event(score=0.6, confidence=0.8)
        history = _history(["NORMAL", "NORMAL"])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.current_state != "NORMAL"
        assert result.previous_state == "NORMAL"

    async def test_gradual_degradation(self, engine):
        """Multiple anomalies cause progressive degradation reflected in trend."""
        dive = _dive_event(score=0.8, confidence=0.9)
        history = _history(["NORMAL", "MINOR_ANOMALY", "WARNING", "DEGRADING"])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.trend in ("WORSENING", "RAPIDLY_WORSENING")
        assert result.current_state in ("HIGH_RISK", "CRITICAL")

    async def test_history_tracking(self, engine):
        """History records all state changes and builds a summary."""
        dive = _dive_event(score=0.3, confidence=0.5)
        history = _history(["NORMAL", "WARNING", "NORMAL", "WARNING"])
        result = await engine.analyze(dive, "splice-1", history)

        assert len(result.history_summary) == 4
        conditions_in_summary = [h["condition"] for h in result.history_summary]
        assert conditions_in_summary == ["NORMAL", "WARNING", "NORMAL", "WARNING"]

    async def test_get_all_states_via_multiple_splices(self, engine):
        """The engine can analyze multiple splices independently."""
        dive_a = _dive_event(score=0.7, confidence=0.8)
        dive_b = _dive_event(status="RESOLVED", event_type="normal", score=0.0)

        result_a = await engine.analyze(dive_a, "splice-A", _history(["NORMAL"]))
        result_b = await engine.analyze(dive_b, "splice-B", _history(["NORMAL"]))

        assert result_a.splice_id == "splice-A"
        assert result_b.splice_id == "splice-B"
        assert result_a.current_state != "NORMAL"
        assert result_b.current_state == "NORMAL"
