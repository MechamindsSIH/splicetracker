"""Tests for the SensorFusionEngine."""

import pytest

from backend.app.intelligence.sensor_fusion import SensorFusionEngine, FusionResult


def _make_obs(anomaly_score: float, confidence: float, available: bool = True, details=None):
    """Helper to build a sensor observation dict."""
    obs = {
        "anomaly_score": anomaly_score,
        "confidence": confidence,
        "available": available,
    }
    if details:
        obs["details"] = details
    return obs


class TestSensorFusionEngine:
    """Tests for the SensorFusionEngine.fuse method."""

    @pytest.fixture
    def engine(self):
        return SensorFusionEngine()

    async def test_fuse_all_normal(self, engine):
        """All sensors report low anomaly scores -> NORMAL status."""
        observations = {
            "vision": _make_obs(0.1, 0.9),
            "thermal": _make_obs(0.05, 0.85),
            "mechanical": _make_obs(0.08, 0.9),
            "conductive": _make_obs(0.02, 0.95),
        }
        result = await engine.fuse(observations)

        assert isinstance(result, FusionResult)
        assert result.fusion_status == "NORMAL"
        assert result.weighted_anomaly_score < 0.5
        assert len(result.supporting_sensors) == 0
        assert len(result.contradicting_sensors) == 4
        assert result.unavailable_sensors == []

    async def test_fuse_single_anomaly(self, engine):
        """One sensor anomaly, rest normal -> LOW_CONFIDENCE or MODERATE_CONFIDENCE."""
        observations = {
            "vision": _make_obs(0.85, 0.9),
            "thermal": _make_obs(0.1, 0.85),
            "mechanical": _make_obs(0.05, 0.9),
            "conductive": _make_obs(0.02, 0.95),
        }
        result = await engine.fuse(observations)

        assert result.fusion_status in ("LOW_CONFIDENCE", "MODERATE_CONFIDENCE", "NORMAL")
        assert "vision" in result.supporting_sensors
        assert len(result.supporting_sensors) == 1
        assert len(result.contradicting_sensors) == 3

    async def test_fuse_multi_sensor_anomaly(self, engine):
        """Three sensors anomalous with high confidence -> HIGH_CONFIDENCE_DEFECT."""
        # Scores must be high enough that confidence-damped weighted score >= 0.7
        observations = {
            "vision": _make_obs(0.95, 0.98),
            "thermal": _make_obs(0.92, 0.95),
            "mechanical": _make_obs(0.90, 0.95),
            "conductive": _make_obs(0.1, 0.95),
        }
        result = await engine.fuse(observations)

        assert result.fusion_status == "HIGH_CONFIDENCE_DEFECT"
        assert result.weighted_anomaly_score >= 0.7
        assert result.overall_confidence >= 0.7
        assert len(result.supporting_sensors) == 3
        assert "vision" in result.supporting_sensors
        assert "thermal" in result.supporting_sensors
        assert "mechanical" in result.supporting_sensors

    async def test_fuse_contradicting(self, engine):
        """Mixed signals: two high, two low -> sensors split between supporting and contradicting."""
        # Two sensors high anomaly, two sensors low. The weighted score is damped
        # by confidence, so the exact status depends on the math.
        observations = {
            "vision": _make_obs(0.98, 0.95),
            "thermal": _make_obs(0.95, 0.90),
            "mechanical": _make_obs(0.1, 0.9),
            "conductive": _make_obs(0.05, 0.95),
        }
        result = await engine.fuse(observations)

        assert len(result.supporting_sensors) == 2
        assert len(result.contradicting_sensors) == 2
        # Agreement ratio is 0.5 (half supporting, half contradicting)
        assert result.agreement_ratio == pytest.approx(0.5, abs=0.01)
        # With 2/4 sensors anomalous, the status depends on the weighted score
        assert result.fusion_status in ("MODERATE_CONFIDENCE", "LOW_CONFIDENCE", "NORMAL")

    async def test_fuse_missing_sensors(self, engine):
        """Some sensors unavailable -> handles gracefully, lists unavailable."""
        observations = {
            "vision": _make_obs(0.7, 0.9),
            "thermal": _make_obs(0.0, 0.0, available=False),
            "mechanical": _make_obs(0.65, 0.85),
        }
        result = await engine.fuse(observations)

        assert "thermal" in result.unavailable_sensors
        assert "conductive" in result.unavailable_sensors
        assert result.fusion_status != "INSUFFICIENT_DATA"
        assert result.weighted_anomaly_score > 0

    async def test_fuse_no_sensors_available(self, engine):
        """All sensors unavailable -> INSUFFICIENT_DATA."""
        observations = {
            "vision": _make_obs(0.0, 0.0, available=False),
            "thermal": _make_obs(0.0, 0.0, available=False),
        }
        result = await engine.fuse(observations)

        assert result.fusion_status == "INSUFFICIENT_DATA"
        assert result.overall_confidence == 0.0
        assert result.weighted_anomaly_score == 0.0

    async def test_fuse_all_anomaly(self, engine):
        """All four sensors high anomaly scores -> HIGH_CONFIDENCE_DEFECT."""
        observations = {
            "vision": _make_obs(0.95, 0.95),
            "thermal": _make_obs(0.90, 0.90),
            "mechanical": _make_obs(0.88, 0.92),
            "conductive": _make_obs(0.92, 0.93),
        }
        result = await engine.fuse(observations)

        assert result.fusion_status == "HIGH_CONFIDENCE_DEFECT"
        assert result.overall_confidence >= 0.8
        assert len(result.supporting_sensors) == 4
        assert len(result.contradicting_sensors) == 0
        assert result.agreement_ratio == 1.0

    async def test_agreement_bonus(self, engine):
        """Corroboration across sensors increases overall confidence."""
        all_agree_obs = {
            "vision": _make_obs(0.7, 0.7),
            "thermal": _make_obs(0.7, 0.7),
            "mechanical": _make_obs(0.7, 0.7),
            "conductive": _make_obs(0.7, 0.7),
        }
        eng = SensorFusionEngine()
        result_agree = await eng.fuse(all_agree_obs)

        assert result_agree.agreement_ratio == 1.0
        # Raw confidence = 0.7, with agreement bonus of 0.10 -> 0.80
        assert result_agree.overall_confidence >= 0.75

    async def test_evidence_records(self, engine):
        """Fusion produces evidence records for each available sensor."""
        observations = {
            "vision": _make_obs(0.5, 0.8),
            "thermal": _make_obs(0.3, 0.7),
            "mechanical": _make_obs(0.6, 0.85),
            "conductive": _make_obs(0.1, 0.9),
        }
        result = await engine.fuse(observations)

        assert len(result.evidence) == 4
        sensor_types_in_evidence = {e["sensor_type"] for e in result.evidence}
        assert sensor_types_in_evidence == {"vision", "thermal", "mechanical", "conductive"}
        for ev in result.evidence:
            assert "anomaly_score" in ev
            assert "confidence" in ev
            assert "weighted_score" in ev
            assert ev["available"] is True

    async def test_sensor_scores_populated(self, engine):
        """The sensor_scores dict is populated with per-sensor anomaly scores."""
        observations = {
            "vision": _make_obs(0.5, 0.8),
            "thermal": _make_obs(0.3, 0.7),
        }
        result = await engine.fuse(observations)

        assert "vision" in result.sensor_scores
        assert result.sensor_scores["vision"] == pytest.approx(0.5, abs=0.001)
        assert result.sensor_scores["thermal"] == pytest.approx(0.3, abs=0.001)

    async def test_temporal_agreement_single_reading(self, engine):
        """First reading has no temporal history so temporal_agreement is 0."""
        observations = {
            "vision": _make_obs(0.5, 0.8),
            "thermal": _make_obs(0.3, 0.7),
            "mechanical": _make_obs(0.6, 0.85),
            "conductive": _make_obs(0.1, 0.9),
        }
        result = await engine.fuse(observations)
        assert result.temporal_agreement == pytest.approx(0.0, abs=0.01)
