"""DIVE (Defect Intelligence and Validation Engine).

Groups raw fusion observations into meaningful events, classifies them,
tracks persistence, and manages event lifecycle (create / update / merge / resolve).
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DIVEEvent:
    """A coherent defect event tracked by the DIVE engine."""

    event_id: str  # EVT-XXXXXX
    splice_id: str
    event_type: str  # progressive_anomaly, isolated_anomaly, multi_sensor_defect, sensor_disagreement, intermittent_fault
    evidence: List[Dict[str, Any]]
    supporting_sensors: List[str]
    contradicting_sensors: List[str]
    confidence: float
    persistence_count: int
    status: str  # ACTIVE, MONITORING, RESOLVED
    created_at: str
    updated_at: str
    fusion_status: str = ""
    weighted_anomaly_score: float = 0.0
    merge_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DIVEEngine:
    """Defect Intelligence and Validation Engine.

    Maintains a map of active events per splice and manages their lifecycle:

    * **Create** -- a new event when a fusion result indicates an anomaly that
      does not match any open event.
    * **Update** -- an existing event when a subsequent observation is
      consistent with the ongoing event (increases persistence count).
    * **Merge** -- two events that occur within the merge window and share
      sensors.
    * **Resolve** -- an event when the anomaly is no longer detected for
      enough consecutive inspections.

    All inputs and outputs are plain dicts for loose coupling.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.active_events: Dict[str, List[DIVEEvent]] = {}  # splice_id -> events
        self.event_counter: int = 0
        self.persistence_threshold: int = config.get("persistence_threshold", 3)
        self.merge_window_seconds: float = config.get("merge_window_seconds", 30.0)
        self.resolution_streak: int = config.get("resolution_streak", 3)
        # Track consecutive normal readings per event for resolution
        self._normal_streak: Dict[str, int] = {}  # event_id -> count of consecutive normals

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, fusion_result: Dict[str, Any], splice_id: str) -> DIVEEvent:
        """Process a fusion result for a given splice.

        Parameters
        ----------
        fusion_result:
            Dict produced by :meth:`SensorFusionEngine.fuse` (or its
            ``to_dict()`` output).
        splice_id:
            Identifier for the splice under inspection.

        Returns
        -------
        DIVEEvent reflecting the current state after processing.
        """
        is_anomalous = fusion_result.get("fusion_status", "NORMAL") not in (
            "NORMAL", "INSUFFICIENT_DATA",
        )

        matching = self._find_matching_event(splice_id, fusion_result)

        if matching and is_anomalous:
            event = self._update_event(matching, fusion_result)
        elif is_anomalous:
            event = self._create_event(splice_id, fusion_result)
        elif matching:
            event = self._check_resolution(matching, fusion_result)
        else:
            # No anomaly and no active event -- return a synthetic NORMAL event
            event = self._create_normal_event(splice_id, fusion_result)

        logger.debug(
            "DIVE processed splice=%s event=%s type=%s status=%s persistence=%d",
            splice_id, event.event_id, event.event_type, event.status,
            event.persistence_count,
        )
        return event

    def get_active_events(self, splice_id: str) -> List[Dict[str, Any]]:
        """Return active events for a splice as plain dicts."""
        return [e.to_dict() for e in self.active_events.get(splice_id, [])]

    def get_all_active_events(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return all active events across all splices."""
        return {
            sid: [e.to_dict() for e in evts]
            for sid, evts in self.active_events.items()
            if evts
        }

    # ------------------------------------------------------------------
    # Event lifecycle
    # ------------------------------------------------------------------

    def _find_matching_event(
        self, splice_id: str, fusion_result: Dict[str, Any],
    ) -> Optional[DIVEEvent]:
        """Find an active event that the new observation can be merged into.

        Matching criteria:
        1. Event is ACTIVE or MONITORING for this splice.
        2. At least one supporting sensor overlaps.
        3. Event was last updated within the merge window.
        """
        events = self.active_events.get(splice_id, [])
        now = datetime.now(timezone.utc).timestamp()
        supporting = set(fusion_result.get("supporting_sensors", []))

        for evt in events:
            if evt.status == "RESOLVED":
                continue
            try:
                dt = datetime.fromisoformat(evt.updated_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                evt_time = dt.timestamp()
            except (ValueError, TypeError):
                evt_time = 0.0
            age = now - evt_time
            if age > self.merge_window_seconds:
                continue
            overlap = supporting & set(evt.supporting_sensors)
            if overlap or not supporting:
                return evt
        return None

    def _create_event(
        self, splice_id: str, fusion_result: Dict[str, Any],
    ) -> DIVEEvent:
        """Create a brand new event from a fusion result."""
        self.event_counter += 1
        event_id = f"EVT-{self.event_counter:06d}"
        now_iso = datetime.now(timezone.utc).isoformat()

        supporting = fusion_result.get("supporting_sensors", [])
        contradicting = fusion_result.get("contradicting_sensors", [])
        event_type = self._classify_event_type(fusion_result)

        event = DIVEEvent(
            event_id=event_id,
            splice_id=splice_id,
            event_type=event_type,
            evidence=[self._extract_evidence_entry(fusion_result)],
            supporting_sensors=list(supporting),
            contradicting_sensors=list(contradicting),
            confidence=fusion_result.get("overall_confidence", 0.0),
            persistence_count=1,
            status="ACTIVE",
            created_at=now_iso,
            updated_at=now_iso,
            fusion_status=fusion_result.get("fusion_status", ""),
            weighted_anomaly_score=fusion_result.get("weighted_anomaly_score", 0.0),
        )

        self.active_events.setdefault(splice_id, []).append(event)
        self._normal_streak[event_id] = 0
        logger.info("DIVE created event %s for splice %s (type=%s)", event_id, splice_id, event_type)
        return event

    def _update_event(
        self, event: DIVEEvent, fusion_result: Dict[str, Any],
    ) -> DIVEEvent:
        """Update an existing event with new supporting evidence."""
        now_iso = datetime.now(timezone.utc).isoformat()

        event.persistence_count += 1
        event.updated_at = now_iso
        event.evidence.append(self._extract_evidence_entry(fusion_result))
        # Keep evidence list bounded
        if len(event.evidence) > 50:
            event.evidence = event.evidence[-50:]

        # Update supporting / contradicting sensors (union over time)
        new_supporting = set(event.supporting_sensors) | set(
            fusion_result.get("supporting_sensors", [])
        )
        new_contradicting = set(fusion_result.get("contradicting_sensors", [])) - new_supporting
        event.supporting_sensors = sorted(new_supporting)
        event.contradicting_sensors = sorted(new_contradicting)

        # Update confidence -- exponential moving average
        alpha = 0.3
        event.confidence = round(
            alpha * fusion_result.get("overall_confidence", 0.0)
            + (1 - alpha) * event.confidence,
            4,
        )
        event.weighted_anomaly_score = round(
            alpha * fusion_result.get("weighted_anomaly_score", 0.0)
            + (1 - alpha) * event.weighted_anomaly_score,
            4,
        )
        event.fusion_status = fusion_result.get("fusion_status", event.fusion_status)

        # Re-classify as more evidence arrives
        event.event_type = self._classify_event_type(
            fusion_result, persistence=event.persistence_count,
        )

        # Reset normal streak since we got another anomalous reading
        self._normal_streak[event.event_id] = 0

        return event

    def _check_resolution(
        self, event: DIVEEvent, fusion_result: Dict[str, Any],
    ) -> DIVEEvent:
        """Check whether an active event should be resolved.

        Called when the latest fusion result is NORMAL but we have an open event.
        After ``resolution_streak`` consecutive normal readings the event is resolved.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        event.updated_at = now_iso

        streak = self._normal_streak.get(event.event_id, 0) + 1
        self._normal_streak[event.event_id] = streak

        if streak >= self.resolution_streak:
            event.status = "RESOLVED"
            event.evidence.append({
                "action": "resolved",
                "reason": f"Normal readings for {streak} consecutive inspections",
                "timestamp": now_iso,
            })
            # Remove from active list
            splice_events = self.active_events.get(event.splice_id, [])
            self.active_events[event.splice_id] = [
                e for e in splice_events if e.event_id != event.event_id
            ]
            self._normal_streak.pop(event.event_id, None)
            logger.info("DIVE resolved event %s after %d normal readings", event.event_id, streak)
        else:
            event.status = "MONITORING"
            event.evidence.append({
                "action": "monitoring",
                "normal_streak": streak,
                "needed_for_resolution": self.resolution_streak,
                "timestamp": now_iso,
            })

        return event

    def _create_normal_event(
        self, splice_id: str, fusion_result: Dict[str, Any],
    ) -> DIVEEvent:
        """Return a transient NORMAL event (not tracked in active_events)."""
        self.event_counter += 1
        event_id = f"EVT-{self.event_counter:06d}"
        now_iso = datetime.now(timezone.utc).isoformat()
        return DIVEEvent(
            event_id=event_id,
            splice_id=splice_id,
            event_type="normal",
            evidence=[self._extract_evidence_entry(fusion_result)],
            supporting_sensors=[],
            contradicting_sensors=fusion_result.get("contradicting_sensors", []),
            confidence=fusion_result.get("overall_confidence", 0.0),
            persistence_count=0,
            status="RESOLVED",
            created_at=now_iso,
            updated_at=now_iso,
            fusion_status=fusion_result.get("fusion_status", "NORMAL"),
            weighted_anomaly_score=fusion_result.get("weighted_anomaly_score", 0.0),
        )

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _classify_event_type(
        self,
        fusion_result: Dict[str, Any],
        persistence: int = 1,
    ) -> str:
        """Determine the semantic event type from the fusion result."""
        supporting = fusion_result.get("supporting_sensors", [])
        contradicting = fusion_result.get("contradicting_sensors", [])
        fusion_status = fusion_result.get("fusion_status", "")
        score = fusion_result.get("weighted_anomaly_score", 0.0)

        n_supporting = len(supporting)
        n_contradicting = len(contradicting)

        if n_supporting >= 3:
            return "multi_sensor_defect"
        if n_supporting >= 2 and n_contradicting >= 1:
            return "sensor_disagreement"
        if persistence >= self.persistence_threshold:
            return "progressive_anomaly"
        if n_supporting == 1 and persistence <= 1:
            return "isolated_anomaly"
        if n_supporting >= 2:
            return "multi_sensor_defect"
        if persistence >= 2:
            return "progressive_anomaly"
        return "isolated_anomaly"

    @staticmethod
    def _calculate_persistence(event: DIVEEvent) -> int:
        """Return current persistence count."""
        return event.persistence_count

    @staticmethod
    def _extract_evidence_entry(fusion_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a compact evidence entry from a fusion result."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fusion_status": fusion_result.get("fusion_status", ""),
            "weighted_anomaly_score": fusion_result.get("weighted_anomaly_score", 0.0),
            "overall_confidence": fusion_result.get("overall_confidence", 0.0),
            "supporting_sensors": fusion_result.get("supporting_sensors", []),
            "sensor_scores": fusion_result.get("sensor_scores", {}),
        }
