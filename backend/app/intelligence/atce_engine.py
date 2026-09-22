"""ATCE (Adaptive Temporal Correlation Engine).

Correlates current DIVE events with historical condition data to determine
temporal patterns, trends, persistence, and recurrence for a splice.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ATCEResult:
    """Result of temporal correlation analysis for a splice event."""

    splice_id: str
    previous_state: str
    current_state: str
    trend: str  # IMPROVING, STABLE, WORSENING, RAPIDLY_WORSENING
    persistence: int  # consecutive abnormal inspections
    recurrence: bool
    classification: str  # ISOLATED, RECURRING, PERSISTENT, WORSENING, STABLE, RESOLVED
    history_summary: List[Dict[str, Any]]
    confidence: float
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Ordered severity so that index comparisons give directionality
_STATE_SEVERITY = [
    "NORMAL",
    "MINOR_ANOMALY",
    "WARNING",
    "DEGRADING",
    "HIGH_RISK",
    "CRITICAL",
]


def _state_index(state: str) -> int:
    """Return the ordinal severity of a state string (0 = normal)."""
    upper = state.upper().replace(" ", "_")
    try:
        return _STATE_SEVERITY.index(upper)
    except ValueError:
        # Unknown states treated as midpoint
        return 2


class ATCEEngine:
    """Adaptive Temporal Correlation Engine.

    Accepts a DIVE event (as dict), a splice identifier, and a condition
    history list and produces an :class:`ATCEResult` describing the temporal
    pattern.

    The ``condition_history`` list should contain dicts with at least
    ``condition`` (str) and ``timestamp`` (ISO string), ordered oldest-first.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.history_window: int = config.get("history_window", 10)
        self.trend_weights: List[float] = config.get(
            "trend_weights", [0.30, 0.25, 0.20, 0.15, 0.10],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(
        self,
        dive_event: Dict[str, Any],
        splice_id: str,
        condition_history: List[Dict[str, Any]],
    ) -> ATCEResult:
        """Run temporal correlation analysis.

        Parameters
        ----------
        dive_event:
            Output of :meth:`DIVEEngine.process` (or its ``to_dict()``).
        splice_id:
            Splice identifier.
        condition_history:
            Historical condition records (oldest first).  Each entry needs
            at least ``condition`` and ``timestamp``.

        Returns
        -------
        ATCEResult
        """
        # Use only the most recent window
        recent = condition_history[-self.history_window:] if condition_history else []

        previous_state = recent[-1]["condition"] if recent else "NORMAL"
        current_state = self._derive_current_state(dive_event)

        trend = self._determine_trend(recent, current_state)
        persistence = self._calculate_persistence(recent, current_state)
        recurrence = self._check_recurrence(recent, current_state)
        classification = self._classify_temporal_pattern(
            trend, persistence, recurrence, dive_event,
        )
        history_summary = self._build_history_summary(recent)

        # Confidence is based on how much history we have
        history_confidence = min(1.0, len(recent) / self.history_window)
        event_confidence = dive_event.get("confidence", 0.5)
        confidence = round(0.6 * event_confidence + 0.4 * history_confidence, 4)

        result = ATCEResult(
            splice_id=splice_id,
            previous_state=previous_state,
            current_state=current_state,
            trend=trend,
            persistence=persistence,
            recurrence=recurrence,
            classification=classification,
            history_summary=history_summary,
            confidence=confidence,
        )

        logger.debug(
            "ATCE splice=%s trend=%s persistence=%d classification=%s",
            splice_id, trend, persistence, classification,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_current_state(self, dive_event: Dict[str, Any]) -> str:
        """Map a DIVE event to a condition state string."""
        status = dive_event.get("status", "RESOLVED")
        event_type = dive_event.get("event_type", "normal")
        score = dive_event.get("weighted_anomaly_score", 0.0)
        confidence = dive_event.get("confidence", 0.0)

        if status == "RESOLVED" or event_type == "normal":
            return "NORMAL"

        combined = score * confidence
        if combined >= 0.7:
            return "CRITICAL"
        if combined >= 0.5:
            return "HIGH_RISK"
        if combined >= 0.35:
            return "DEGRADING"
        if combined >= 0.2:
            return "WARNING"
        if combined >= 0.1:
            return "MINOR_ANOMALY"
        return "NORMAL"

    def _determine_trend(
        self, history: List[Dict[str, Any]], current_state: str,
    ) -> str:
        """Determine the trend direction using weighted recent history.

        Compares a weighted average of recent severity indices against the
        current severity to decide the direction.
        """
        if not history:
            return "STABLE"

        current_idx = _state_index(current_state)

        # Build severity index series from history + current
        indices = [_state_index(h["condition"]) for h in history]
        indices.append(current_idx)

        # Use the last N entries (matching trend_weights length)
        recent_indices = indices[-(len(self.trend_weights) + 1):]

        if len(recent_indices) < 2:
            return "STABLE"

        # Weighted score of history (excluding current)
        hist_part = recent_indices[:-1]
        weights = self.trend_weights[:len(hist_part)]
        # Reverse so most recent history entry gets highest weight
        hist_part_reversed = list(reversed(hist_part))
        total_w = sum(weights[:len(hist_part_reversed)])
        if total_w == 0:
            return "STABLE"

        weighted_avg = sum(
            w * s for w, s in zip(weights, hist_part_reversed)
        ) / total_w

        delta = current_idx - weighted_avg

        if delta >= 1.5:
            return "RAPIDLY_WORSENING"
        if delta >= 0.5:
            return "WORSENING"
        if delta <= -0.5:
            return "IMPROVING"
        return "STABLE"

    @staticmethod
    def _calculate_persistence(
        history: List[Dict[str, Any]], current_state: str,
    ) -> int:
        """Count consecutive abnormal inspections ending at the current one.

        Returns 0 if the current state is NORMAL.
        """
        if _state_index(current_state) == 0:
            return 0

        count = 1  # current is abnormal
        for entry in reversed(history):
            if _state_index(entry["condition"]) > 0:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _check_recurrence(
        history: List[Dict[str, Any]], current_state: str,
    ) -> bool:
        """Check if the current state has occurred before in history.

        A state is "recurring" if the same severity level appeared, then
        went to NORMAL, and has now returned.
        """
        current_idx = _state_index(current_state)
        if current_idx == 0:
            return False

        saw_similar = False
        saw_normal_after = False
        for entry in history:
            entry_idx = _state_index(entry["condition"])
            if entry_idx >= current_idx:
                saw_similar = True
            elif saw_similar and entry_idx == 0:
                saw_normal_after = True

        return saw_similar and saw_normal_after

    @staticmethod
    def _classify_temporal_pattern(
        trend: str,
        persistence: int,
        recurrence: bool,
        dive_event: Dict[str, Any],
    ) -> str:
        """Assign a high-level temporal classification."""
        status = dive_event.get("status", "RESOLVED")

        if status == "RESOLVED":
            return "RESOLVED"

        if trend in ("RAPIDLY_WORSENING", "WORSENING"):
            return "WORSENING"

        if recurrence:
            return "RECURRING"

        if persistence >= 3:
            return "PERSISTENT"

        if trend == "STABLE" and persistence >= 1:
            return "STABLE"

        if persistence <= 1:
            return "ISOLATED"

        return "STABLE"

    @staticmethod
    def _build_history_summary(
        history: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build a compact summary of the condition history window."""
        summary: List[Dict[str, Any]] = []
        for entry in history:
            summary.append({
                "condition": entry.get("condition", "UNKNOWN"),
                "timestamp": entry.get("timestamp", ""),
                "severity": entry.get("severity", 0.0),
                "confidence": entry.get("confidence", 0.0),
            })
        return summary
