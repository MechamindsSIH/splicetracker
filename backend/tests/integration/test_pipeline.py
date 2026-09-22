"""Integration tests for the full intelligence pipeline.

These tests chain SensorFusionEngine -> DIVEEngine -> ATCEEngine to verify
end-to-end intelligence processing without requiring a database or API.
"""

import pytest

from backend.app.intelligence.sensor_fusion import SensorFusionEngine
from backend.app.intelligence.dive_engine import DIVEEngine
from backend.app.intelligence.atce_engine import ATCEEngine


def _obs(anomaly_score, confidence, available=True):
    return {"anomaly_score": anomaly_score, "confidence": confidence, "available": available}


class TestPipeline:
    """Integration tests for the sensor fusion -> DIVE -> ATCE pipeline."""

    @pytest.fixture
    def fusion_engine(self):
        return SensorFusionEngine()

    @pytest.fixture
    def dive_engine(self):
        return DIVEEngine(config={"merge_window_seconds": 999, "resolution_streak": 3})

    @pytest.fixture
    def atce_engine(self):
        return ATCEEngine()

    async def test_normal_pipeline(self, fusion_engine, dive_engine, atce_engine):
        """Normal sensor readings produce no defect and a NORMAL/RESOLVED state."""
        observations = {
            "vision": _obs(0.1, 0.9),
            "thermal": _obs(0.05, 0.85),
            "mechanical": _obs(0.08, 0.9),
            "conductive": _obs(0.02, 0.95),
        }
        fusion_result = await fusion_engine.fuse(observations)
        assert fusion_result.fusion_status == "NORMAL"

        dive_event = await dive_engine.process(
            fusion_result.to_dict(), "splice-test"
        )
        assert dive_event.event_type == "normal"
        assert dive_event.status == "RESOLVED"

        atce_result = await atce_engine.analyze(
            dive_event.to_dict(), "splice-test", []
        )
        assert atce_result.classification == "RESOLVED"
        assert atce_result.current_state == "NORMAL"

    async def test_anomaly_pipeline(self, fusion_engine, dive_engine, atce_engine):
        """Anomalous sensor readings trigger defect detection through the pipeline."""
        observations = {
            "vision": _obs(0.95, 0.95),
            "thermal": _obs(0.92, 0.95),
            "mechanical": _obs(0.90, 0.95),
            "conductive": _obs(0.88, 0.95),
        }
        fusion_result = await fusion_engine.fuse(observations)
        assert fusion_result.fusion_status == "HIGH_CONFIDENCE_DEFECT"

        dive_event = await dive_engine.process(
            fusion_result.to_dict(), "splice-anomaly"
        )
        assert dive_event.status == "ACTIVE"
        assert dive_event.event_type in ("multi_sensor_defect", "isolated_anomaly")
        assert dive_event.persistence_count == 1

        atce_result = await atce_engine.analyze(
            dive_event.to_dict(), "splice-anomaly", []
        )
        assert atce_result.current_state != "NORMAL"
        assert atce_result.classification in ("ISOLATED", "STABLE", "WORSENING")

    async def test_progressive_degradation(self, fusion_engine, dive_engine, atce_engine):
        """Escalating anomaly observations produce worsening trend and condition."""
        splice_id = "splice-degrade"
        condition_history = []

        score_sequence = [0.3, 0.5, 0.7, 0.85]

        for score in score_sequence:
            observations = {
                "vision": _obs(score, 0.9),
                "thermal": _obs(score * 0.9, 0.85),
                "mechanical": _obs(score * 0.8, 0.9),
                "conductive": _obs(score * 0.5, 0.95),
            }
            fusion_result = await fusion_engine.fuse(observations)
            dive_event = await dive_engine.process(
                fusion_result.to_dict(), splice_id
            )
            atce_result = await atce_engine.analyze(
                dive_event.to_dict(), splice_id, condition_history
            )

            condition_history.append({
                "condition": atce_result.current_state,
                "timestamp": atce_result.timestamp,
                "severity": score,
                "confidence": 0.85,
            })

        final_atce = atce_result
        assert final_atce.current_state in ("HIGH_RISK", "CRITICAL", "DEGRADING")
        assert final_atce.trend in ("WORSENING", "RAPIDLY_WORSENING")
        assert final_atce.persistence >= 2

    async def test_recovery_pipeline(self, fusion_engine, dive_engine, atce_engine):
        """After anomalies, normal readings lead to event resolution."""
        splice_id = "splice-recover"

        bad_obs = {
            "vision": _obs(0.8, 0.9),
            "thermal": _obs(0.75, 0.85),
            "mechanical": _obs(0.7, 0.9),
            "conductive": _obs(0.6, 0.95),
        }
        fusion_bad = await fusion_engine.fuse(bad_obs)
        dive_bad = await dive_engine.process(fusion_bad.to_dict(), splice_id)
        assert dive_bad.status == "ACTIVE"

        normal_obs = {
            "vision": _obs(0.1, 0.9),
            "thermal": _obs(0.05, 0.85),
            "mechanical": _obs(0.08, 0.9),
            "conductive": _obs(0.02, 0.95),
        }

        for i in range(3):
            fusion_ok = await fusion_engine.fuse(normal_obs)
            dive_ok = await dive_engine.process(fusion_ok.to_dict(), splice_id)

        assert dive_ok.status == "RESOLVED"

    async def test_pipeline_data_flows_correctly(self, fusion_engine, dive_engine, atce_engine):
        """Verify data integrity flows through all pipeline stages."""
        observations = {
            "vision": _obs(0.7, 0.9),
            "thermal": _obs(0.6, 0.85),
            "mechanical": _obs(0.3, 0.9),
            "conductive": _obs(0.1, 0.95),
        }

        fusion_result = await fusion_engine.fuse(observations)
        fusion_dict = fusion_result.to_dict()
        assert "fusion_status" in fusion_dict
        assert "weighted_anomaly_score" in fusion_dict
        assert "overall_confidence" in fusion_dict

        dive_event = await dive_engine.process(fusion_dict, "splice-flow")
        dive_dict = dive_event.to_dict()
        assert "event_id" in dive_dict
        assert "status" in dive_dict
        assert "weighted_anomaly_score" in dive_dict

        atce_result = await atce_engine.analyze(dive_dict, "splice-flow", [])
        atce_dict = atce_result.to_dict()
        assert "splice_id" in atce_dict
        assert "current_state" in atce_dict
        assert "trend" in atce_dict
        assert "classification" in atce_dict
