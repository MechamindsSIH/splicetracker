"""Risk Engine — explainable factor-based risk scoring."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class RiskResult:
    risk_score: float = 0.0
    risk_level: str = "LOW"
    risk_trend: str = "STABLE"
    contributing_factors: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    confidence: float = 0.0
    recommended_action: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class RiskEngine:
    def __init__(self):
        self.factor_weights = {
            "thermal_anomaly": 18,
            "mechanical_anomaly": 16,
            "visual_defect": 20,
            "persistence": 12,
            "recurrence": 8,
            "sensor_corroboration": 10,
            "trend_worsening": 10,
            "conductive_break": 6,
        }
        self.thresholds = {"LOW": 0, "MEDIUM": 30, "HIGH": 60, "CRITICAL": 85}
        self.previous_scores: dict[str, list] = {}

    async def evaluate(
        self,
        splice_id: str,
        fusion_result: dict,
        atce_result: dict,
        twin_state: dict,
    ) -> dict:
        factors = self._calculate_factor_scores(fusion_result, atce_result, twin_state)
        raw_score = sum(f["score"] for f in factors)
        risk_score = min(100.0, max(0.0, raw_score))
        risk_level = self._determine_level(risk_score)
        risk_trend = self._determine_trend(splice_id, risk_score)
        confidence = fusion_result.get("overall_confidence", 0.0)
        recommended_action = self._generate_recommendation(risk_level, risk_score, factors)

        if splice_id not in self.previous_scores:
            self.previous_scores[splice_id] = []
        self.previous_scores[splice_id].append(risk_score)
        if len(self.previous_scores[splice_id]) > 20:
            self.previous_scores[splice_id] = self.previous_scores[splice_id][-20:]

        evidence = {
            "fusion_status": fusion_result.get("fusion_status", "UNKNOWN"),
            "supporting_sensors": fusion_result.get("supporting_sensors", []),
            "trend": atce_result.get("trend", "STABLE"),
            "persistence": atce_result.get("persistence", 0),
            "twin_condition": twin_state.get("condition", "NORMAL"),
        }

        result = RiskResult(
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            risk_trend=risk_trend,
            contributing_factors=factors,
            evidence=evidence,
            confidence=confidence,
            recommended_action=recommended_action,
        )
        return result.to_dict()

    def _calculate_factor_scores(
        self, fusion_result: dict, atce_result: dict, twin_state: dict
    ) -> list:
        factors = []

        vision_score = fusion_result.get("vision_score", 0.0)
        if vision_score > 0.3:
            score = self.factor_weights["visual_defect"] * min(1.0, vision_score)
            factors.append(
                {
                    "factor": "visual_defect",
                    "score": round(score, 1),
                    "description": f"Visual anomaly score: {vision_score:.2f}",
                }
            )

        thermal_score = fusion_result.get("thermal_score", 0.0)
        if thermal_score > 0.3:
            score = self.factor_weights["thermal_anomaly"] * min(1.0, thermal_score)
            factors.append(
                {
                    "factor": "thermal_anomaly",
                    "score": round(score, 1),
                    "description": f"Thermal anomaly score: {thermal_score:.2f}",
                }
            )

        mech_score = fusion_result.get("mechanical_score", 0.0)
        if mech_score > 0.3:
            score = self.factor_weights["mechanical_anomaly"] * min(1.0, mech_score)
            factors.append(
                {
                    "factor": "mechanical_anomaly",
                    "score": round(score, 1),
                    "description": f"Mechanical anomaly score: {mech_score:.2f}",
                }
            )

        cond_score = fusion_result.get("conductive_score", 0.0)
        if cond_score > 0.5:
            factors.append(
                {
                    "factor": "conductive_break",
                    "score": self.factor_weights["conductive_break"],
                    "description": "Conductive break detected",
                }
            )

        supporting = fusion_result.get("supporting_sensors", [])
        if len(supporting) >= 2:
            corr_score = self.factor_weights["sensor_corroboration"] * (
                len(supporting) / 4.0
            )
            factors.append(
                {
                    "factor": "sensor_corroboration",
                    "score": round(corr_score, 1),
                    "description": f"{len(supporting)} sensors corroborate anomaly",
                }
            )

        persistence = atce_result.get("persistence", 0)
        if persistence >= 2:
            p_score = self.factor_weights["persistence"] * min(
                1.0, persistence / 5.0
            )
            factors.append(
                {
                    "factor": "persistence",
                    "score": round(p_score, 1),
                    "description": f"Anomaly persisted for {persistence} inspections",
                }
            )

        recurrence = atce_result.get("recurrence", False)
        if recurrence:
            factors.append(
                {
                    "factor": "recurrence",
                    "score": self.factor_weights["recurrence"],
                    "description": "Pattern has recurred previously",
                }
            )

        trend = atce_result.get("trend", "STABLE")
        if trend in ("WORSENING", "RAPIDLY_WORSENING"):
            t_score = self.factor_weights["trend_worsening"]
            if trend == "RAPIDLY_WORSENING":
                t_score *= 1.5
            factors.append(
                {
                    "factor": "trend_worsening",
                    "score": round(min(t_score, 15.0), 1),
                    "description": f"Condition trend: {trend}",
                }
            )

        return factors

    def _determine_level(self, score: float) -> str:
        if score >= self.thresholds["CRITICAL"]:
            return "CRITICAL"
        elif score >= self.thresholds["HIGH"]:
            return "HIGH"
        elif score >= self.thresholds["MEDIUM"]:
            return "MEDIUM"
        return "LOW"

    def _determine_trend(self, splice_id: str, current_score: float) -> str:
        history = self.previous_scores.get(splice_id, [])
        if len(history) < 2:
            return "STABLE"
        recent = history[-3:]
        avg_recent = sum(recent) / len(recent)
        if current_score > avg_recent + 5:
            return "INCREASING"
        elif current_score < avg_recent - 5:
            return "DECREASING"
        return "STABLE"

    def _generate_recommendation(
        self, level: str, score: float, factors: list
    ) -> str:
        if level == "CRITICAL":
            return "IMMEDIATE ACTION: Stop belt and inspect splice. Multiple severe anomalies detected with high confidence."
        elif level == "HIGH":
            return "Schedule inspection at next safe maintenance opportunity. Progressive degradation detected."
        elif level == "MEDIUM":
            return "Monitor closely. Increase inspection frequency for this splice."
        return "No action required. Continue normal monitoring."

    def _build_explanation(self, factors: list) -> str:
        if not factors:
            return "No significant risk factors detected."
        lines = ["Risk factors:"]
        for f in sorted(factors, key=lambda x: x["score"], reverse=True):
            lines.append(f"  - {f['description']} (+{f['score']})")
        return "\n".join(lines)
