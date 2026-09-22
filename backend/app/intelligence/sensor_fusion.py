"""Explainable sensor fusion engine.

Combines multiple sensor observations (vision, thermal, mechanical, conductive)
into a unified defect assessment with full evidence trails and agreement analysis.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Anomaly score above this is considered a positive detection
_ANOMALY_THRESHOLD = 0.5


@dataclass
class SensorEvidence:
    """Evidence record for a single sensor's contribution to fusion."""

    sensor_type: str
    anomaly_score: float
    confidence: float
    weighted_score: float
    available: bool
    is_anomalous: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FusionResult:
    """Unified result of multi-sensor fusion."""

    overall_confidence: float
    weighted_anomaly_score: float
    supporting_sensors: List[str]
    contradicting_sensors: List[str]
    unavailable_sensors: List[str]
    evidence: List[Dict[str, Any]]
    fusion_status: str  # HIGH_CONFIDENCE_DEFECT, MODERATE_CONFIDENCE, LOW_CONFIDENCE, NORMAL, INSUFFICIENT_DATA
    temporal_agreement: float
    agreement_ratio: float
    sensor_scores: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SensorFusionEngine:
    """Explainable fusion engine that combines multiple sensor observations.

    Each sensor observation is expected as a dict with at least:
        anomaly_score (float 0-1), confidence (float 0-1), available (bool).
    An optional ``details`` dict carries sensor-specific metadata.

    The engine produces a :class:`FusionResult` whose ``fusion_status`` field
    reflects the combined assessment after weighting, agreement analysis, and
    temporal correlation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.weights: Dict[str, float] = config.get("fusion_weights", {
            "vision": 0.30,
            "thermal": 0.25,
            "mechanical": 0.25,
            "conductive": 0.20,
        })
        self.agreement_threshold: float = config.get("agreement_threshold", 0.5)
        self.high_confidence_threshold: float = config.get("high_confidence_threshold", 0.7)
        # Running buffer of recent per-sensor anomaly scores for temporal agreement
        self._recent_scores: Dict[str, List[float]] = {k: [] for k in self.weights}
        self._temporal_window: int = config.get("temporal_window", 5)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fuse(self, observations: Dict[str, Dict[str, Any]]) -> FusionResult:
        """Fuse observations from all available sensors.

        Parameters
        ----------
        observations:
            Mapping of sensor name to observation dict.  Each observation
            must contain ``anomaly_score``, ``confidence``, and ``available``.

        Returns
        -------
        FusionResult
        """
        available_obs = {
            k: v for k, v in observations.items()
            if v.get("available", False) and k in self.weights
        }
        unavailable = [
            k for k in self.weights
            if k not in available_obs
        ]

        if not available_obs:
            return FusionResult(
                overall_confidence=0.0,
                weighted_anomaly_score=0.0,
                supporting_sensors=[],
                contradicting_sensors=[],
                unavailable_sensors=list(self.weights.keys()),
                evidence=[],
                fusion_status="INSUFFICIENT_DATA",
                temporal_agreement=0.0,
                agreement_ratio=0.0,
            )

        evidence = self._build_evidence(available_obs)
        weighted_score = self._calculate_weighted_score(available_obs)
        supporting, contradicting = self._determine_agreement(available_obs)
        agreement_ratio = len(supporting) / len(available_obs) if available_obs else 0.0

        # Agreement bonus: if most sensors agree, boost confidence
        agreement_bonus = 0.0
        if agreement_ratio >= 0.75:
            agreement_bonus = 0.10
        elif agreement_ratio >= 0.5:
            agreement_bonus = 0.05

        # Compute overall confidence as weighted mean of sensor confidences + agreement
        total_weight = sum(self.weights[s] for s in available_obs)
        raw_confidence = sum(
            self.weights[s] * available_obs[s].get("confidence", 0.0)
            for s in available_obs
        ) / total_weight if total_weight > 0 else 0.0
        overall_confidence = min(1.0, raw_confidence + agreement_bonus)

        # Temporal agreement
        temporal_agreement = self._calculate_temporal_agreement(available_obs)

        # Classify
        fusion_status = self._classify_fusion_status(
            weighted_score, overall_confidence, agreement_ratio, len(available_obs),
        )

        sensor_scores = {
            s: obs.get("anomaly_score", 0.0) for s, obs in available_obs.items()
        }

        result = FusionResult(
            overall_confidence=round(overall_confidence, 4),
            weighted_anomaly_score=round(weighted_score, 4),
            supporting_sensors=supporting,
            contradicting_sensors=contradicting,
            unavailable_sensors=unavailable,
            evidence=[e.to_dict() for e in evidence],
            fusion_status=fusion_status,
            temporal_agreement=round(temporal_agreement, 4),
            agreement_ratio=round(agreement_ratio, 4),
            sensor_scores=sensor_scores,
        )

        logger.debug(
            "Fusion complete: status=%s score=%.3f confidence=%.3f supporting=%s",
            fusion_status, weighted_score, overall_confidence, supporting,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_weighted_score(
        self, available_obs: Dict[str, Dict[str, Any]],
    ) -> float:
        """Compute the confidence-adjusted weighted anomaly score.

        Only available sensors contribute.  Weights are re-normalised so
        that the available subset sums to 1.0.
        """
        total_weight = sum(self.weights[s] for s in available_obs)
        if total_weight == 0:
            return 0.0

        score = 0.0
        for sensor, obs in available_obs.items():
            normalised_weight = self.weights[sensor] / total_weight
            anomaly = obs.get("anomaly_score", 0.0)
            confidence = obs.get("confidence", 0.0)
            # Dampen the anomaly score by the sensor's own confidence
            score += normalised_weight * anomaly * confidence
        return score

    def _determine_agreement(
        self, available_obs: Dict[str, Dict[str, Any]],
    ) -> tuple:
        """Split sensors into supporting (anomaly detected) and contradicting.

        A sensor "supports" if its anomaly_score >= ``_ANOMALY_THRESHOLD``.

        Returns
        -------
        (supporting, contradicting) -- lists of sensor names
        """
        supporting: List[str] = []
        contradicting: List[str] = []
        for sensor, obs in available_obs.items():
            if obs.get("anomaly_score", 0.0) >= _ANOMALY_THRESHOLD:
                supporting.append(sensor)
            else:
                contradicting.append(sensor)
        return supporting, contradicting

    def _classify_fusion_status(
        self,
        weighted_score: float,
        overall_confidence: float,
        agreement_ratio: float,
        sensor_count: int,
    ) -> str:
        """Map the combined metrics into a human-readable status label."""
        if sensor_count < 2:
            if weighted_score >= self.high_confidence_threshold:
                return "MODERATE_CONFIDENCE"
            if weighted_score >= self.agreement_threshold:
                return "LOW_CONFIDENCE"
            return "INSUFFICIENT_DATA"

        if (
            weighted_score >= self.high_confidence_threshold
            and overall_confidence >= self.high_confidence_threshold
            and agreement_ratio >= 0.5
        ):
            return "HIGH_CONFIDENCE_DEFECT"

        if weighted_score >= self.agreement_threshold:
            if overall_confidence >= self.agreement_threshold:
                return "MODERATE_CONFIDENCE"
            return "LOW_CONFIDENCE"

        return "NORMAL"

    def _build_evidence(
        self, available_obs: Dict[str, Dict[str, Any]],
    ) -> List[SensorEvidence]:
        """Create an evidence record per available sensor."""
        total_weight = sum(self.weights[s] for s in available_obs)
        evidence: List[SensorEvidence] = []
        for sensor, obs in available_obs.items():
            anomaly = obs.get("anomaly_score", 0.0)
            confidence = obs.get("confidence", 0.0)
            norm_w = self.weights[sensor] / total_weight if total_weight else 0.0
            evidence.append(SensorEvidence(
                sensor_type=sensor,
                anomaly_score=round(anomaly, 4),
                confidence=round(confidence, 4),
                weighted_score=round(norm_w * anomaly * confidence, 4),
                available=True,
                is_anomalous=anomaly >= _ANOMALY_THRESHOLD,
                details=obs.get("details", {}),
            ))
        return evidence

    def _calculate_temporal_agreement(
        self, available_obs: Dict[str, Dict[str, Any]],
    ) -> float:
        """Track recent anomaly scores and measure temporal consistency.

        Returns a 0-1 score indicating how stable the current reading is
        compared to the recent window.  High values mean the sensors have
        been consistently reporting similar anomaly levels.
        """
        for sensor in self.weights:
            score = available_obs.get(sensor, {}).get("anomaly_score")
            buf = self._recent_scores.setdefault(sensor, [])
            if score is not None:
                buf.append(score)
                if len(buf) > self._temporal_window:
                    buf[:] = buf[-self._temporal_window:]

        # For each sensor with history, compute consistency as 1 - stdev
        consistencies: List[float] = []
        for sensor, buf in self._recent_scores.items():
            if len(buf) < 2:
                continue
            mean = sum(buf) / len(buf)
            variance = sum((x - mean) ** 2 for x in buf) / len(buf)
            stdev = variance ** 0.5
            consistencies.append(max(0.0, 1.0 - stdev))

        if not consistencies:
            return 0.0
        return sum(consistencies) / len(consistencies)
