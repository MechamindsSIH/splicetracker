import logging
import time
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# Severity ordering for comparison (higher number = more severe)
_SEVERITY_ORDER = {
    "WARNING": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


class AlertEngine:
    """Generates and manages alerts based on risk assessment output.

    Evaluates inspection/risk results against configurable thresholds and
    generates alerts when conditions are met. Manages alert lifecycle
    (create, acknowledge, resolve).
    """

    def __init__(self, event_bus=None, db_session_factory=None):
        """
        Args:
            event_bus: Optional EventBus for publishing alert events (may be None)
            db_session_factory: Optional async session factory for persistence (may be None).
                Should be a callable that returns an async context manager yielding an AsyncSession,
                or an async_sessionmaker instance.
        """
        self.event_bus = event_bus
        self.db_session_factory = db_session_factory
        self.alert_counter = 0
        self.thresholds = {
            "WARNING": 30,
            "HIGH": 60,
            "CRITICAL": 85,
        }
        self.active_alerts = {}  # alert_id -> alert_dict
        self.alert_history = []  # all alerts ever created
        self.cooldown_seconds = 30  # minimum time between alerts for same splice
        self._last_alert_time = {}  # splice_id -> timestamp of last alert
        self.suppression_rules = []  # list of dicts for alert suppression

    async def evaluate(self, risk_result: dict, splice_id: str, location: dict) -> dict:
        """Evaluate whether an alert should be generated based on risk assessment.

        Args:
            risk_result: dict from risk engine with at least:
                - risk_score: float (0-100)
                - risk_level: str (LOW/MODERATE/HIGH/CRITICAL)
                - condition: str (GOOD/FAIR/DEGRADED/POOR/CRITICAL)
                - confidence: float (0-1)
                - defect_type: str or None
                - contributing_factors: list of str (optional)
                - recommended_action: str (optional)
            splice_id: str identifier for the splice
            location: dict from localization engine with position info

        Returns:
            alert dict if threshold met, None otherwise
        """
        if risk_result is None:
            risk_result = {}
        if location is None:
            location = {}

        risk_score = risk_result.get("risk_score", 0.0)
        if risk_score is None:
            risk_score = 0.0

        # Determine severity from risk score
        severity = self._determine_severity(risk_score)
        if severity is None:
            logger.debug(
                "Risk score %.1f for splice %s is below alert threshold; no alert generated",
                risk_score, splice_id,
            )
            return None

        # Check cooldown
        if self._is_in_cooldown(splice_id):
            logger.debug(
                "Splice %s is in cooldown period; suppressing %s alert",
                splice_id, severity,
            )
            return None

        # Check if an active alert already exists at same or higher severity
        if self._has_higher_active_alert(splice_id, severity):
            logger.debug(
                "Splice %s already has an active alert at severity >= %s; suppressing",
                splice_id, severity,
            )
            return None

        # Build alert fields
        confidence = risk_result.get("confidence", 0.0) or 0.0
        defect_type = risk_result.get("defect_type")
        reason = self._generate_reason(risk_result, severity)
        recommended_action = risk_result.get("recommended_action") or self._generate_recommendation(risk_result, severity)

        # Create the alert
        alert = await self.create_alert(
            severity=severity,
            splice_id=splice_id,
            risk_score=risk_score,
            confidence=confidence,
            defect_type=defect_type,
            reason=reason,
            recommended_action=recommended_action,
            location=location,
        )

        # Publish event to event bus if available
        if self.event_bus is not None:
            try:
                from ..core.events import EventType
                await self.event_bus.publish(
                    EventType.ALERT_CREATED,
                    payload=alert,
                    source="AlertEngine",
                )
                logger.debug("Published ALERT_CREATED event for alert %d", alert["id"])
            except Exception as exc:
                logger.warning("Failed to publish alert event: %s", exc)

        return alert

    async def create_alert(self, severity: str, splice_id: str, risk_score: float,
                           confidence: float, defect_type: str, reason: str,
                           recommended_action: str, location: dict) -> dict:
        """Create a new alert.

        Builds the alert dict, stores it in active_alerts and alert_history,
        persists to database if db_session_factory is available, and updates
        the cooldown tracker.
        """
        self.alert_counter += 1
        alert_id = self.alert_counter
        now = datetime.now(timezone.utc)

        # Format location string
        location_str = self._format_location(location)

        alert = {
            "id": alert_id,
            "splice_id": splice_id,
            "timestamp": now.isoformat(),
            "severity": severity,
            "defect_type": defect_type,
            "confidence": confidence,
            "risk_score": risk_score,
            "reason": reason,
            "recommended_action": recommended_action,
            "status": "ACTIVE",
            "acknowledged_at": None,
            "acknowledged_by": None,
            "location": location_str,
        }

        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self._last_alert_time[splice_id] = time.monotonic()

        logger.info(
            "Alert #%d created: severity=%s splice=%s risk_score=%.1f location=%s",
            alert_id, severity, splice_id, risk_score, location_str,
        )

        # Persist to database
        await self._persist_alert(alert)

        return alert

    async def acknowledge_alert(self, alert_id: int, acknowledged_by: str = "operator") -> dict:
        """Acknowledge an active alert.

        Update status to ACKNOWLEDGED, set acknowledged_at and acknowledged_by.
        Raises ValueError if alert_id not found.
        """
        if alert_id not in self.active_alerts:
            raise ValueError(f"Alert {alert_id} not found in active alerts")

        alert = self.active_alerts[alert_id]
        now = datetime.now(timezone.utc)

        alert["status"] = "ACKNOWLEDGED"
        alert["acknowledged_at"] = now.isoformat()
        alert["acknowledged_by"] = acknowledged_by

        logger.info("Alert #%d acknowledged by %s", alert_id, acknowledged_by)

        # Update in database
        await self._update_alert_in_db(alert_id, {
            "status": "ACKNOWLEDGED",
            "acknowledged_at": now,
            "acknowledged_by": acknowledged_by,
        })

        return alert

    async def resolve_alert(self, alert_id: int) -> dict:
        """Resolve an alert (remove from active).

        Update status to RESOLVED and remove from active_alerts.
        Raises ValueError if alert_id not found.
        """
        if alert_id not in self.active_alerts:
            raise ValueError(f"Alert {alert_id} not found in active alerts")

        alert = self.active_alerts.pop(alert_id)
        alert["status"] = "RESOLVED"

        # Also update in history
        for hist_alert in self.alert_history:
            if hist_alert["id"] == alert_id:
                hist_alert["status"] = "RESOLVED"
                break

        logger.info("Alert #%d resolved", alert_id)

        # Update in database
        await self._update_alert_in_db(alert_id, {"status": "RESOLVED"})

        return alert

    async def get_active_alerts(self) -> list:
        """Return list of all active (non-resolved) alerts, sorted by severity then timestamp.

        Sort order: CRITICAL first, then HIGH, then WARNING.
        Within same severity, most recent first.
        """
        alerts = list(self.active_alerts.values())
        alerts.sort(
            key=lambda a: (
                -_SEVERITY_ORDER.get(a.get("severity", "WARNING"), 0),
                a.get("timestamp", ""),
            ),
            reverse=False,
        )
        # Within the same severity group, we want most recent first.
        # The primary sort puts CRITICAL first (highest negative value).
        # For the secondary key (timestamp as ISO string), lexicographic reverse = most recent first.
        # Re-sort properly:
        alerts.sort(
            key=lambda a: (
                -_SEVERITY_ORDER.get(a.get("severity", "WARNING"), 0),
                a.get("timestamp", ""),
            ),
        )
        # Reverse within same severity group for recency: timestamps are ISO strings,
        # so reverse lexicographic order means most recent first.
        # Simplest correct approach: sort with a tuple that negates both axes.
        alerts.sort(
            key=lambda a: (
                -_SEVERITY_ORDER.get(a.get("severity", "WARNING"), 0),
                # Negate timestamp by reversing the string is fragile; instead
                # parse and negate epoch. Fall back to 0 on parse failure.
                -self._iso_to_epoch(a.get("timestamp", "")),
            ),
        )
        return alerts

    async def get_alerts_for_splice(self, splice_id: str) -> list:
        """Return all alerts (active and historical) for a given splice."""
        return [a for a in self.alert_history if a.get("splice_id") == splice_id]

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _determine_severity(self, risk_score: float) -> str:
        """Map risk score to severity level. Returns None if below WARNING threshold."""
        if risk_score >= self.thresholds["CRITICAL"]:
            return "CRITICAL"
        if risk_score >= self.thresholds["HIGH"]:
            return "HIGH"
        if risk_score >= self.thresholds["WARNING"]:
            return "WARNING"
        return None

    def _generate_reason(self, risk_result: dict, severity: str) -> str:
        """Generate a human-readable reason string for the alert."""
        risk_score = risk_result.get("risk_score", 0.0)
        defect_type = risk_result.get("defect_type")
        confidence = risk_result.get("confidence", 0.0) or 0.0
        contributing_factors = risk_result.get("contributing_factors") or []
        condition = risk_result.get("condition", "unknown")

        severity_label = severity.lower()

        parts = []

        # Main description
        if defect_type:
            parts.append(
                f"{severity.capitalize()} risk detected: {defect_type} defect "
                f"with {confidence * 100:.0f}% confidence (risk score: {risk_score:.0f})"
            )
        else:
            parts.append(
                f"{severity.capitalize()} risk detected: risk score {risk_score:.0f} "
                f"with {confidence * 100:.0f}% confidence"
            )

        # Condition
        if condition and condition != "unknown":
            parts.append(f"Splice condition: {condition}")

        # Contributing factors
        if contributing_factors:
            factors_str = ", ".join(str(f) for f in contributing_factors)
            parts.append(f"Contributing factors: {factors_str}")

        return ". ".join(parts) + "."

    def _generate_recommendation(self, risk_result: dict, severity: str) -> str:
        """Generate recommended action based on severity and defect type."""
        defect_type = risk_result.get("defect_type")

        base_recommendations = {
            "WARNING": "Schedule inspection at next maintenance window",
            "HIGH": "Prioritize inspection within 24 hours. Monitor for further degradation.",
            "CRITICAL": "Immediate inspection required. Consider stopping belt for safety assessment.",
        }

        recommendation = base_recommendations.get(severity, "Monitor and reassess.")

        # Add defect-specific guidance
        if defect_type:
            defect_lower = defect_type.lower()
            if "crack" in defect_lower:
                recommendation += f" Check for crack propagation in splice area."
            elif "delamination" in defect_lower or "separation" in defect_lower:
                recommendation += f" Inspect adhesive bond integrity."
            elif "wear" in defect_lower or "abrasion" in defect_lower:
                recommendation += f" Measure remaining material thickness."
            elif "thermal" in defect_lower or "heat" in defect_lower:
                recommendation += f" Verify thermal conditions and check for friction sources."
            elif "alignment" in defect_lower or "misalign" in defect_lower:
                recommendation += f" Check belt tracking and splice alignment."
            else:
                recommendation += f" Investigate {defect_type} condition."

        return recommendation

    def _is_in_cooldown(self, splice_id: str) -> bool:
        """Check if a splice is in alert cooldown period."""
        last_time = self._last_alert_time.get(splice_id)
        if last_time is None:
            return False
        elapsed = time.monotonic() - last_time
        return elapsed < self.cooldown_seconds

    def _has_higher_active_alert(self, splice_id: str, severity: str) -> bool:
        """Check if there's already an active alert at same or higher severity for this splice."""
        new_severity_rank = _SEVERITY_ORDER.get(severity, 0)

        for alert in self.active_alerts.values():
            if alert.get("splice_id") != splice_id:
                continue
            if alert.get("status") == "RESOLVED":
                continue
            existing_rank = _SEVERITY_ORDER.get(alert.get("severity", ""), 0)
            if existing_rank >= new_severity_rank:
                return True

        return False

    def _format_location(self, location: dict) -> str:
        """Format a location dict into a human-readable string."""
        if not location:
            return "unknown location"

        belt_id = location.get("belt_id", "unknown")
        position = location.get("position", 0.0)

        if belt_id and belt_id != "unknown" and position is not None:
            return f"Belt {belt_id} @ {position:.1f}m"
        elif belt_id and belt_id != "unknown":
            return f"Belt {belt_id}"
        else:
            return "unknown location"

    async def _persist_alert(self, alert: dict):
        """Persist an alert to the database if db_session_factory is available."""
        if self.db_session_factory is None:
            return

        try:
            from ..database.models import Alert as AlertModel, AlertSeverity, AlertStatus

            severity_map = {
                "WARNING": AlertSeverity.WARNING,
                "HIGH": AlertSeverity.HIGH,
                "CRITICAL": AlertSeverity.CRITICAL,
            }

            async with self.db_session_factory() as session:
                db_alert = AlertModel(
                    splice_id=self._parse_splice_id_for_db(alert["splice_id"]),
                    severity=severity_map.get(alert["severity"], AlertSeverity.WARNING),
                    defect_type=alert.get("defect_type"),
                    confidence=alert.get("confidence", 0.0),
                    risk_score=alert.get("risk_score", 0.0),
                    reason=alert.get("reason"),
                    recommended_action=alert.get("recommended_action"),
                    status=AlertStatus.ACTIVE,
                    location=alert.get("location"),
                )
                session.add(db_alert)
                await session.commit()
                logger.debug("Alert #%d persisted to database", alert["id"])
        except Exception as exc:
            logger.warning("Failed to persist alert #%d to database: %s", alert["id"], exc)

    async def _update_alert_in_db(self, alert_id: int, updates: dict):
        """Update an alert in the database if db_session_factory is available."""
        if self.db_session_factory is None:
            return

        try:
            from ..database.models import Alert as AlertModel, AlertSeverity, AlertStatus
            from sqlalchemy import select

            status_map = {
                "ACTIVE": AlertStatus.ACTIVE,
                "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
                "RESOLVED": AlertStatus.RESOLVED,
            }

            async with self.db_session_factory() as session:
                # Find the alert by matching the in-memory counter to the DB.
                # Since we create alerts sequentially, the Nth alert corresponds to DB id.
                # However, DB auto-increments may differ, so we look up by position
                # in the history or fall back to the DB id.
                result = await session.execute(
                    select(AlertModel).where(AlertModel.id == alert_id)
                )
                db_alert = result.scalar_one_or_none()
                if db_alert is None:
                    logger.debug("Alert #%d not found in database for update", alert_id)
                    return

                if "status" in updates:
                    db_alert.status = status_map.get(updates["status"], db_alert.status)
                if "acknowledged_at" in updates:
                    db_alert.acknowledged_at = updates["acknowledged_at"]
                if "acknowledged_by" in updates:
                    db_alert.acknowledged_by = updates["acknowledged_by"]

                await session.commit()
                logger.debug("Alert #%d updated in database", alert_id)
        except Exception as exc:
            logger.warning("Failed to update alert #%d in database: %s", alert_id, exc)

    @staticmethod
    def _parse_splice_id_for_db(splice_id: str):
        """Attempt to extract a numeric splice ID for the database foreign key.

        The in-memory splice_id may be a string like 'SPL-001' or a numeric string.
        If it can be parsed as an integer, return the int; otherwise return 1 as a
        safe fallback (the caller is responsible for ensuring valid foreign keys
        when database persistence is enabled).
        """
        if splice_id is None:
            return 1
        # Try direct int parse
        try:
            return int(splice_id)
        except (ValueError, TypeError):
            pass
        # Try extracting trailing digits (e.g. 'SPL-003' -> 3)
        import re
        match = re.search(r"(\d+)$", str(splice_id))
        if match:
            return int(match.group(1))
        return 1

    @staticmethod
    def _iso_to_epoch(iso_str: str) -> float:
        """Parse an ISO format timestamp string to a Unix epoch float."""
        if not iso_str:
            return 0.0
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

    def update_thresholds(self, thresholds: dict):
        """Update alert thresholds. Input: {'WARNING': 30, 'HIGH': 60, 'CRITICAL': 85}"""
        self.thresholds.update(thresholds)

    def get_statistics(self) -> dict:
        """Return alert statistics.

        Returns dict with:
            total_alerts, active_count, acknowledged_count, resolved_count,
            by_severity (dict of severity -> count),
            average_time_to_acknowledge (seconds or None)
        """
        total = len(self.alert_history)
        active_count = 0
        acknowledged_count = 0
        resolved_count = 0
        by_severity = defaultdict(int)
        ack_durations = []

        for alert in self.alert_history:
            status = alert.get("status", "ACTIVE")
            severity = alert.get("severity", "WARNING")

            by_severity[severity] += 1

            if status == "ACTIVE":
                active_count += 1
            elif status == "ACKNOWLEDGED":
                acknowledged_count += 1
            elif status == "RESOLVED":
                resolved_count += 1

            # Calculate time-to-acknowledge for acknowledged or resolved alerts
            if alert.get("acknowledged_at") and alert.get("timestamp"):
                try:
                    created = datetime.fromisoformat(alert["timestamp"])
                    acked = datetime.fromisoformat(alert["acknowledged_at"])
                    duration = (acked - created).total_seconds()
                    if duration >= 0:
                        ack_durations.append(duration)
                except (ValueError, TypeError):
                    pass

        avg_time_to_ack = None
        if ack_durations:
            avg_time_to_ack = sum(ack_durations) / len(ack_durations)

        return {
            "total_alerts": total,
            "active_count": active_count,
            "acknowledged_count": acknowledged_count,
            "resolved_count": resolved_count,
            "by_severity": dict(by_severity),
            "average_time_to_acknowledge": avg_time_to_ack,
        }
