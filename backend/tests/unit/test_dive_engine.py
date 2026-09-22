"""Tests for the DIVE (Defect Intelligence and Validation Engine)."""

import pytest

from backend.app.intelligence.dive_engine import DIVEEngine, DIVEEvent


def _make_fusion_result(
    fusion_status="HIGH_CONFIDENCE_DEFECT",
    weighted_anomaly_score=0.8,
    overall_confidence=0.85,
    supporting_sensors=None,
    contradicting_sensors=None,
    sensor_scores=None,
):
    """Build a fusion result dict mimicking SensorFusionEngine output."""
    return {
        "fusion_status": fusion_status,
        "weighted_anomaly_score": weighted_anomaly_score,
        "overall_confidence": overall_confidence,
        "supporting_sensors": supporting_sensors or ["vision", "thermal"],
        "contradicting_sensors": contradicting_sensors or ["mechanical"],
        "sensor_scores": sensor_scores or {"vision": 0.9, "thermal": 0.8, "mechanical": 0.1},
    }


class TestDIVEEngine:
    """Tests for the DIVEEngine.process method and event lifecycle."""

    @pytest.fixture
    def engine(self):
        return DIVEEngine(config={"merge_window_seconds": 999, "resolution_streak": 3})

    async def test_create_new_event(self, engine):
        """First anomalous observation creates a new ACTIVE event."""
        fusion = _make_fusion_result()
        event = await engine.process(fusion, "splice-1")

        assert isinstance(event, DIVEEvent)
        assert event.status == "ACTIVE"
        assert event.persistence_count == 1
        assert event.splice_id == "splice-1"
        assert len(event.evidence) == 1
        assert set(event.supporting_sensors) == {"thermal", "vision"}

    async def test_update_existing_event(self, engine):
        """Repeated anomalous observations increase persistence on the same event."""
        fusion = _make_fusion_result()
        event1 = await engine.process(fusion, "splice-1")
        event_id = event1.event_id

        event2 = await engine.process(fusion, "splice-1")
        assert event2.event_id == event_id
        assert event2.persistence_count == 2
        assert event2.status == "ACTIVE"

        event3 = await engine.process(fusion, "splice-1")
        assert event3.event_id == event_id
        assert event3.persistence_count == 3

    async def test_event_classification(self, engine):
        """Different supporting sensor counts produce different event types."""
        fusion_single = _make_fusion_result(
            supporting_sensors=["vision"],
            contradicting_sensors=["thermal", "mechanical", "conductive"],
        )
        event_single = await engine.process(fusion_single, "splice-single")
        assert event_single.event_type == "isolated_anomaly"

        fusion_multi = _make_fusion_result(
            supporting_sensors=["vision", "thermal", "mechanical"],
            contradicting_sensors=["conductive"],
        )
        event_multi = await engine.process(fusion_multi, "splice-multi")
        assert event_multi.event_type == "multi_sensor_defect"

    async def test_event_resolution(self, engine):
        """Normal observations eventually resolve an active event."""
        fusion_bad = _make_fusion_result()
        event = await engine.process(fusion_bad, "splice-1")
        assert event.status == "ACTIVE"

        fusion_ok = _make_fusion_result(
            fusion_status="NORMAL",
            weighted_anomaly_score=0.1,
            overall_confidence=0.9,
            supporting_sensors=[],
            contradicting_sensors=["vision", "thermal", "mechanical"],
        )

        event = await engine.process(fusion_ok, "splice-1")
        assert event.status == "MONITORING"

        event = await engine.process(fusion_ok, "splice-1")
        assert event.status == "MONITORING"

        event = await engine.process(fusion_ok, "splice-1")
        assert event.status == "RESOLVED"

    async def test_event_id_format(self, engine):
        """Event IDs follow the EVT-XXXXXX format."""
        fusion = _make_fusion_result()
        event = await engine.process(fusion, "splice-1")

        assert event.event_id.startswith("EVT-")
        suffix = event.event_id.split("-")[1]
        assert len(suffix) == 6
        assert suffix.isdigit()

    async def test_persistence_counting(self, engine):
        """Persistence increments correctly with each anomalous observation."""
        fusion = _make_fusion_result()

        counts = []
        for _ in range(5):
            event = await engine.process(fusion, "splice-1")
            counts.append(event.persistence_count)

        assert counts == [1, 2, 3, 4, 5]

    async def test_normal_event_not_tracked(self, engine):
        """Normal observations without an active event produce transient RESOLVED events."""
        fusion_ok = _make_fusion_result(
            fusion_status="NORMAL",
            weighted_anomaly_score=0.05,
            overall_confidence=0.9,
            supporting_sensors=[],
        )
        event = await engine.process(fusion_ok, "splice-1")

        assert event.event_type == "normal"
        assert event.status == "RESOLVED"
        assert event.persistence_count == 0
        assert engine.get_active_events("splice-1") == []

    async def test_get_all_active_events(self, engine):
        """get_all_active_events returns active events across all splices."""
        fusion = _make_fusion_result()
        await engine.process(fusion, "splice-A")
        await engine.process(fusion, "splice-B")

        all_active = engine.get_all_active_events()
        assert "splice-A" in all_active
        assert "splice-B" in all_active
        assert len(all_active["splice-A"]) == 1
        assert len(all_active["splice-B"]) == 1

    async def test_progressive_anomaly_classification(self, engine):
        """After persistence_threshold observations, event type becomes progressive_anomaly."""
        engine_low_thresh = DIVEEngine(config={
            "merge_window_seconds": 999,
            "persistence_threshold": 3,
        })
        fusion = _make_fusion_result(
            supporting_sensors=["vision"],
            contradicting_sensors=["thermal", "mechanical"],
        )

        event = await engine_low_thresh.process(fusion, "splice-1")
        assert event.event_type == "isolated_anomaly"

        event = await engine_low_thresh.process(fusion, "splice-1")

        event = await engine_low_thresh.process(fusion, "splice-1")
        assert event.event_type == "progressive_anomaly"
