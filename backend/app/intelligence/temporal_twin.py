"""Temporal Digital Twin — per-splice state machine with condition history."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


CONDITION_LEVELS = ["NORMAL", "MINOR_ANOMALY", "WARNING", "DEGRADING", "HIGH_RISK", "CRITICAL"]
SEVERITY_MAP = {
    "NORMAL": "NONE",
    "MINOR_ANOMALY": "LOW",
    "WARNING": "MEDIUM",
    "DEGRADING": "HIGH",
    "HIGH_RISK": "HIGH",
    "CRITICAL": "CRITICAL",
}


@dataclass
class SpliceState:
    splice_id: str
    condition: str = "NORMAL"
    severity: str = "NONE"
    confidence: float = 0.0
    risk_level: str = "LOW"
    trend: str = "STABLE"
    recent_events: list = field(default_factory=list)
    last_inspection: Optional[str] = None
    history: list = field(default_factory=list)
    event_count: int = 0
    consecutive_anomalies: int = 0
    consecutive_normal: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class TemporalDigitalTwin:
    def __init__(self):
        self.splice_states: dict[str, SpliceState] = {}
        self.max_recent_events = 10
        self.max_history = 100

    async def update(
        self,
        splice_id: str,
        atce_result: dict,
        fusion_result: dict,
        risk_result: dict = None,
    ) -> dict:
        state = self._get_or_create(splice_id)
        now = datetime.utcnow().isoformat()
        state.last_inspection = now

        new_condition = self._determine_condition(
            state, atce_result, fusion_result, risk_result
        )
        old_condition = state.condition

        if new_condition != old_condition:
            state.history.append(
                {"timestamp": now, "condition": new_condition, "previous": old_condition}
            )
            if len(state.history) > self.max_history:
                state.history = state.history[-self.max_history:]

        state.condition = new_condition
        state.severity = SEVERITY_MAP.get(new_condition, "NONE")
        state.confidence = fusion_result.get("overall_confidence", 0.0)
        state.trend = atce_result.get("trend", "STABLE")

        if risk_result:
            state.risk_level = risk_result.get("risk_level", "LOW")

        is_anomaly = new_condition not in ("NORMAL",)
        if is_anomaly:
            state.consecutive_anomalies += 1
            state.consecutive_normal = 0
        else:
            state.consecutive_normal += 1
            state.consecutive_anomalies = 0

        event_summary = {
            "timestamp": now,
            "condition": new_condition,
            "confidence": state.confidence,
            "trend": state.trend,
        }
        state.recent_events.append(event_summary)
        if len(state.recent_events) > self.max_recent_events:
            state.recent_events = state.recent_events[-self.max_recent_events:]
        state.event_count += 1

        return state.to_dict()

    def _determine_condition(
        self,
        state: SpliceState,
        atce_result: dict,
        fusion_result: dict,
        risk_result: dict = None,
    ) -> str:
        current_idx = CONDITION_LEVELS.index(state.condition)
        fusion_confidence = fusion_result.get("overall_confidence", 0.0)
        fusion_status = fusion_result.get("fusion_status", "NORMAL")
        trend = atce_result.get("trend", "STABLE")
        classification = atce_result.get("classification", "ISOLATED")

        target_idx = current_idx

        if fusion_status == "NORMAL" or fusion_confidence < 0.2:
            target_idx = max(0, current_idx - 1)
        elif fusion_status == "LOW_CONFIDENCE":
            if trend == "WORSENING":
                target_idx = min(len(CONDITION_LEVELS) - 1, current_idx + 1)
            else:
                target_idx = current_idx
        elif fusion_status == "MODERATE_CONFIDENCE":
            if trend in ("WORSENING", "RAPIDLY_WORSENING"):
                target_idx = min(len(CONDITION_LEVELS) - 1, current_idx + 1)
            elif classification == "PERSISTENT":
                target_idx = min(len(CONDITION_LEVELS) - 1, current_idx + 1)
            else:
                target_idx = max(current_idx, 1)
        elif fusion_status in ("HIGH_CONFIDENCE_DEFECT",):
            if trend in ("WORSENING", "RAPIDLY_WORSENING"):
                target_idx = min(len(CONDITION_LEVELS) - 1, current_idx + 2)
            else:
                target_idx = min(len(CONDITION_LEVELS) - 1, current_idx + 1)
        elif fusion_status == "INSUFFICIENT_DATA":
            target_idx = current_idx

        if fusion_confidence > 0.95 and risk_result and risk_result.get("risk_level") == "CRITICAL":
            target_idx = max(target_idx, CONDITION_LEVELS.index("HIGH_RISK"))

        max_step = 1
        if fusion_confidence > 0.95:
            max_step = 2

        if target_idx > current_idx:
            target_idx = min(target_idx, current_idx + max_step)
        elif target_idx < current_idx:
            target_idx = max(target_idx, current_idx - 1)

        target_idx = max(0, min(len(CONDITION_LEVELS) - 1, target_idx))
        return CONDITION_LEVELS[target_idx]

    def _get_or_create(self, splice_id: str) -> SpliceState:
        if splice_id not in self.splice_states:
            self.splice_states[splice_id] = SpliceState(splice_id=splice_id)
        return self.splice_states[splice_id]

    def get_state(self, splice_id: str) -> dict:
        state = self._get_or_create(splice_id)
        return state.to_dict()

    def get_history(self, splice_id: str) -> list:
        state = self._get_or_create(splice_id)
        return list(state.history)

    def get_all_states(self) -> dict:
        return {sid: s.to_dict() for sid, s in self.splice_states.items()}
