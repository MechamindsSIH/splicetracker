"""Tests for alert generation logic.

Alert generation is embedded in the simulation loop. These tests exercise
the same thresholds using the database repositories against an in-memory DB.
"""

import pytest
from datetime import datetime

from backend.app.database.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    RiskLevel,
    Splice,
    SpliceCondition,
)
from backend.app.database.repositories import AlertRepository, SpliceRepository


def _should_alert(is_anomaly: bool, overall_score: float):
    """Determine if an alert should be generated and at what severity."""
    if not is_anomaly or overall_score <= 0.5:
        return None
    if overall_score > 0.8:
        return AlertSeverity.CRITICAL
    if overall_score > 0.6:
        return AlertSeverity.HIGH
    return AlertSeverity.WARNING


class TestAlertEngine:
    """Tests for alert generation thresholds and DB persistence."""

    async def test_no_alert_low_risk(self, db_session):
        """Low risk (normal, score 0.2) -> no alert generated."""
        severity = _should_alert(is_anomaly=False, overall_score=0.2)
        assert severity is None

    async def test_no_alert_low_anomaly_score(self, db_session):
        """Anomaly detected but score too low (0.4) -> no alert."""
        severity = _should_alert(is_anomaly=True, overall_score=0.4)
        assert severity is None

    async def test_warning_alert(self, db_session):
        """Medium risk (score 0.55) -> WARNING alert."""
        severity = _should_alert(is_anomaly=True, overall_score=0.55)
        assert severity == AlertSeverity.WARNING

    async def test_high_alert(self, db_session):
        """High risk (score 0.7) -> HIGH alert."""
        severity = _should_alert(is_anomaly=True, overall_score=0.7)
        assert severity == AlertSeverity.HIGH

    async def test_critical_alert(self, db_session):
        """Critical risk (score 0.85) -> CRITICAL alert."""
        severity = _should_alert(is_anomaly=True, overall_score=0.85)
        assert severity == AlertSeverity.CRITICAL

    async def test_alert_persisted_to_db(self, db_session):
        """An alert can be created and retrieved from the database."""
        # Create a splice first (FK constraint)
        splice_repo = SpliceRepository(db_session)
        splice = await splice_repo.create(
            name="Splice-Test-Alert",
            belt_id="BELT-A",
            position=10.0,
            condition=SpliceCondition.DEGRADED,
            severity=0.7,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
        )
        await db_session.flush()

        alert_repo = AlertRepository(db_session)
        alert = await alert_repo.create(
            splice_id=splice.id,
            severity=AlertSeverity.HIGH,
            defect_type="crack",
            confidence=0.85,
            risk_score=0.7,
            reason="Anomaly detected: crack (score=0.70)",
            recommended_action="Schedule maintenance inspection",
            status=AlertStatus.ACTIVE,
            location="Position 42.5m",
        )
        await db_session.flush()

        retrieved = await alert_repo.get_by_id(alert.id)
        assert retrieved is not None
        assert retrieved.severity == AlertSeverity.HIGH
        assert retrieved.status == AlertStatus.ACTIVE
        assert retrieved.defect_type == "crack"

    async def test_alert_acknowledge(self, db_session):
        """An active alert can be acknowledged."""
        splice_repo = SpliceRepository(db_session)
        splice = await splice_repo.create(
            name="Splice-Test-Ack",
            belt_id="BELT-A",
            position=20.0,
            condition=SpliceCondition.POOR,
            severity=0.8,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
        )
        await db_session.flush()

        alert_repo = AlertRepository(db_session)
        alert = await alert_repo.create(
            splice_id=splice.id,
            severity=AlertSeverity.CRITICAL,
            confidence=0.9,
            risk_score=0.85,
            reason="Critical anomaly",
            status=AlertStatus.ACTIVE,
        )
        await db_session.flush()

        acked = await alert_repo.acknowledge(alert.id, "operator_1")
        assert acked.status == AlertStatus.ACKNOWLEDGED
        assert acked.acknowledged_by == "operator_1"
        assert acked.acknowledged_at is not None

    async def test_alert_count_by_status(self, db_session):
        """Count alerts filtered by status."""
        splice_repo = SpliceRepository(db_session)
        splice = await splice_repo.create(
            name="Splice-Test-Count",
            belt_id="BELT-A",
            position=30.0,
            condition=SpliceCondition.GOOD,
            severity=0.0,
            confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        await db_session.flush()

        alert_repo = AlertRepository(db_session)
        await alert_repo.create(
            splice_id=splice.id, severity=AlertSeverity.WARNING,
            confidence=0.6, risk_score=0.5, status=AlertStatus.ACTIVE,
        )
        await alert_repo.create(
            splice_id=splice.id, severity=AlertSeverity.HIGH,
            confidence=0.8, risk_score=0.7, status=AlertStatus.ACTIVE,
        )
        await alert_repo.create(
            splice_id=splice.id, severity=AlertSeverity.HIGH,
            confidence=0.8, risk_score=0.7, status=AlertStatus.RESOLVED,
        )
        await db_session.flush()

        active_count = await alert_repo.count(status=AlertStatus.ACTIVE)
        assert active_count == 2

        total = await alert_repo.count()
        assert total == 3
