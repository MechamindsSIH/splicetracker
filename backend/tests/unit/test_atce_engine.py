"""Tests for the ATCE (Adaptive Temporal Correlation Engine)."""

import pytest
from datetime import datetime, timedelta

from backend.app.intelligence.atce_engine import ATCEEngine, ATCEResult


def _make_dive_event(
    status="ACTIVE",
    event_type="multi_sensor_defect",
    weighted_anomaly_score=0.7,
    confidence=0.8,
):
    """Build a DIVE event dict mimicking DIVEEngine output."""
    return {
        "event_id": "EVT-000001",
        "splice_id": "splice-1",
        "event_type": event_type,
        "status": status,
        "weighted_anomaly_score": weighted_anomaly_score,
        "confidence": confidence,
        "supporting_sensors": ["vision", "thermal"],
        "persistence_count": 3,
    }


def _make_history(conditions, start_time=None):
    """Build a condition history list from a list of condition strings."""
    base = start_time or datetime(2026, 1, 1)
    return [
        {
            "condition": cond,
            "timestamp": (base + timedelta(hours=i)).isoformat(),
            "severity": 0.0,
            "confidence": 0.9,
        }
        for i, cond in enumerate(conditions)
    ]


class TestATCEEngine:
    """Tests for the ATCEEngine.analyze method."""

    @pytest.fixture
    def engine(self):
        return ATCEEngine()

    async def test_isolated_anomaly(self, engine):
        """A borderline reading that does not continue any historical pattern -> ISOLATED.

        ISOLATED requires: trend != WORSENING, recurrence=False, persistence <= 1.
        To achieve this reliably, we use a dive event whose combined score maps
        to NORMAL (current_state index 0) while status is still ACTIVE.  A
        declining history gives IMPROVING trend, persistence=0, recurrence=False.
        """
        # combined = 0.09 * 0.9 = 0.081 < 0.1 -> current_state = NORMAL
        dive = _make_dive_event(
            status="ACTIVE",
            event_type="isolated_anomaly",
            weighted_anomaly_score=0.09,
            confidence=0.9,
        )
        # History declines from WARNING to MINOR_ANOMALY -> weighted avg > 0 + 0.5
        # No entry has index >= current_idx (0), so recurrence = False.
        history = _make_history([
            "WARNING",
            "MINOR_ANOMALY",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert isinstance(result, ATCEResult)
        assert result.classification == "ISOLATED"
        assert result.trend == "IMPROVING"

    async def test_recurring_pattern(self, engine):
        """A pattern that appeared before, went to NORMAL, and returned -> RECURRING.

        The trend must be STABLE (not WORSENING) for RECURRING to beat
        WORSENING in the classification priority.  We use enough trailing
        DEGRADING entries so the single NORMAL entry's weight is diluted
        and the weighted average stays close to the current index.
        """
        # combined = 0.5 * 0.7 = 0.35 -> DEGRADING (index 3)
        dive = _make_dive_event(
            weighted_anomaly_score=0.5,
            confidence=0.7,
        )
        # Five DEGRADING entries after the NORMAL push the weighted avg close
        # to 3, keeping delta < 0.5 -> STABLE trend.
        # Recurrence is True because DEGRADING (idx 3) appeared, then NORMAL.
        history = _make_history([
            "DEGRADING",
            "NORMAL",
            "DEGRADING",
            "DEGRADING",
            "DEGRADING",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.recurrence is True
        assert result.classification == "RECURRING"

    async def test_worsening_trend(self, engine):
        """Escalating anomalies -> WORSENING trend and classification."""
        dive = _make_dive_event(
            weighted_anomaly_score=0.8,
            confidence=0.9,
            # combined = 0.72 -> CRITICAL (index 5)
        )
        history = _make_history([
            "NORMAL",
            "MINOR_ANOMALY",
            "WARNING",
            "DEGRADING",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.trend in ("WORSENING", "RAPIDLY_WORSENING")
        assert result.classification == "WORSENING"

    async def test_stable_condition(self, engine):
        """Consistent abnormal readings at the same level -> STABLE trend."""
        dive = _make_dive_event(
            weighted_anomaly_score=0.5,
            confidence=0.6,
            # combined = 0.3 -> WARNING (index 2)
        )
        history = _make_history([
            "WARNING",
            "WARNING",
            "WARNING",
            "WARNING",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.trend == "STABLE"
        assert result.classification in ("STABLE", "PERSISTENT")

    async def test_improving_trend(self, engine):
        """Decreasing anomalies -> IMPROVING trend."""
        dive = _make_dive_event(
            status="RESOLVED",
            event_type="normal",
            weighted_anomaly_score=0.05,
            confidence=0.9,
        )
        history = _make_history([
            "CRITICAL",
            "HIGH_RISK",
            "DEGRADING",
            "WARNING",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.current_state == "NORMAL"
        assert result.trend == "IMPROVING"

    async def test_empty_history(self, engine):
        """With no history, defaults are applied."""
        dive = _make_dive_event(
            weighted_anomaly_score=0.3,
            confidence=0.5,
        )
        result = await engine.analyze(dive, "splice-1", [])

        assert result.previous_state == "NORMAL"
        assert result.trend == "STABLE"

    async def test_resolved_classification(self, engine):
        """Resolved DIVE event -> RESOLVED classification."""
        dive = _make_dive_event(status="RESOLVED", event_type="normal")
        history = _make_history(["NORMAL", "NORMAL"])

        result = await engine.analyze(dive, "splice-1", history)
        assert result.classification == "RESOLVED"
        assert result.current_state == "NORMAL"

    async def test_persistence_counting(self, engine):
        """Persistence counts consecutive abnormal entries in history."""
        dive = _make_dive_event(
            weighted_anomaly_score=0.5,
            confidence=0.7,
        )
        history = _make_history([
            "NORMAL",
            "WARNING",
            "WARNING",
            "DEGRADING",
        ])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.persistence >= 3

    async def test_confidence_based_on_history_length(self, engine):
        """Confidence grows with the amount of history available."""
        dive = _make_dive_event()

        short_history = _make_history(["NORMAL"])
        result_short = await engine.analyze(dive, "splice-1", short_history)

        long_history = _make_history(["NORMAL"] * 10)
        result_long = await engine.analyze(dive, "splice-1", long_history)

        assert result_long.confidence >= result_short.confidence

    async def test_history_summary_built(self, engine):
        """The history_summary field summarizes the input history."""
        dive = _make_dive_event()
        history = _make_history(["NORMAL", "WARNING", "DEGRADING"])

        result = await engine.analyze(dive, "splice-1", history)

        assert len(result.history_summary) == 3
        assert result.history_summary[0]["condition"] == "NORMAL"
        assert result.history_summary[1]["condition"] == "WARNING"
        assert result.history_summary[2]["condition"] == "DEGRADING"

    async def test_first_anomaly_from_normal_is_worsening(self, engine):
        """A new anomaly after all-normal history produces WORSENING classification."""
        # combined = 0.4 * 0.6 = 0.24 -> WARNING (index 2)
        # delta from all-NORMAL (index 0) to WARNING (index 2) = 2.0 -> RAPIDLY_WORSENING
        dive = _make_dive_event(
            weighted_anomaly_score=0.4,
            confidence=0.6,
        )
        history = _make_history(["NORMAL", "NORMAL", "NORMAL", "NORMAL"])
        result = await engine.analyze(dive, "splice-1", history)

        assert result.trend in ("WORSENING", "RAPIDLY_WORSENING")
        assert result.classification == "WORSENING"
