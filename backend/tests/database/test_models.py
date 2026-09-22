"""Tests for SQLAlchemy ORM models and database operations."""

import pytest
from datetime import datetime

from sqlalchemy import select

from backend.app.database.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    ATCEResult,
    ATCETrend,
    ConditionHistory,
    ConductiveEvent,
    DIVEEvent,
    DIVEEventType,
    DIVEStatus,
    FusionResult,
    FusionStatus,
    Inspection,
    InspectionStatus,
    MechanicalEvent,
    RiskLevel,
    SensorMeasurement,
    SensorType,
    Splice,
    SpliceCondition,
    SystemEvent,
    SystemEventSeverity,
    ThermalEvent,
    VisionEvent,
)


class TestCreateSplice:
    """Test creating and reading splice records."""

    async def test_create_splice(self, db_session):
        """A splice can be created and read back."""
        splice = Splice(
            name="Splice-001",
            belt_id="BELT-A",
            position=25.5,
            condition=SpliceCondition.GOOD,
            severity=0.0,
            confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        assert splice.id is not None
        assert splice.id > 0

        result = await db_session.execute(
            select(Splice).where(Splice.id == splice.id)
        )
        fetched = result.scalar_one()
        assert fetched.name == "Splice-001"
        assert fetched.belt_id == "BELT-A"
        assert fetched.position == 25.5
        assert fetched.condition == SpliceCondition.GOOD
        assert fetched.risk_level == RiskLevel.LOW

    async def test_splice_defaults(self, db_session):
        """Splice defaults are applied correctly."""
        splice = Splice(
            name="Splice-Defaults",
            belt_id="BELT-B",
            position=50.0,
        )
        db_session.add(splice)
        await db_session.flush()

        assert splice.severity == 0.0
        assert splice.confidence == 0.0
        assert splice.condition == SpliceCondition.UNKNOWN
        assert splice.risk_level == RiskLevel.LOW


class TestCreateInspection:
    """Test creating inspection records with FK to splice."""

    async def test_create_inspection(self, db_session):
        """An inspection can be created linked to a splice."""
        splice = Splice(
            name="Splice-Insp", belt_id="BELT-A", position=10.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        inspection = Inspection(
            splice_id=splice.id,
            status=InspectionStatus.IN_PROGRESS,
        )
        db_session.add(inspection)
        await db_session.flush()

        assert inspection.id is not None
        assert inspection.splice_id == splice.id
        assert inspection.status == InspectionStatus.IN_PROGRESS
        assert inspection.completed_at is None

    async def test_inspection_completion(self, db_session):
        """An inspection can be marked as completed."""
        splice = Splice(
            name="Splice-InspComplete", belt_id="BELT-A", position=15.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        inspection = Inspection(
            splice_id=splice.id,
            status=InspectionStatus.IN_PROGRESS,
        )
        db_session.add(inspection)
        await db_session.flush()

        inspection.status = InspectionStatus.COMPLETED
        inspection.completed_at = datetime.utcnow()
        inspection.results_json = '{"anomaly": false}'
        await db_session.flush()

        result = await db_session.execute(
            select(Inspection).where(Inspection.id == inspection.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == InspectionStatus.COMPLETED
        assert fetched.completed_at is not None
        assert fetched.results_json == '{"anomaly": false}'


class TestCreateAlert:
    """Test creating alert records."""

    async def test_create_alert(self, db_session):
        """An alert can be created and read."""
        splice = Splice(
            name="Splice-Alert", belt_id="BELT-A", position=20.0,
            condition=SpliceCondition.DEGRADED, severity=0.6, confidence=0.8,
            risk_level=RiskLevel.MODERATE,
        )
        db_session.add(splice)
        await db_session.flush()

        alert = Alert(
            splice_id=splice.id,
            severity=AlertSeverity.WARNING,
            defect_type="wear",
            confidence=0.75,
            risk_score=0.6,
            reason="Wear detected",
            recommended_action="Schedule inspection",
            status=AlertStatus.ACTIVE,
            location="Position 20.0m",
        )
        db_session.add(alert)
        await db_session.flush()

        assert alert.id is not None
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE
        assert alert.defect_type == "wear"

    async def test_alert_severity_values(self, db_session):
        """All alert severity enum values can be stored."""
        splice = Splice(
            name="Splice-Sev", belt_id="BELT-A", position=22.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        for sev in AlertSeverity:
            alert = Alert(
                splice_id=splice.id,
                severity=sev,
                confidence=0.5,
                risk_score=0.5,
                status=AlertStatus.ACTIVE,
            )
            db_session.add(alert)

        await db_session.flush()

        result = await db_session.execute(
            select(Alert).where(Alert.splice_id == splice.id)
        )
        alerts = result.scalars().all()
        stored_severities = {a.severity for a in alerts}
        assert stored_severities == set(AlertSeverity)


class TestConditionHistory:
    """Test condition history entries."""

    async def test_create_condition_history(self, db_session):
        """Condition history entries can be created."""
        splice = Splice(
            name="Splice-Hist", belt_id="BELT-A", position=30.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        entries = []
        for cond, risk in [
            (SpliceCondition.GOOD, RiskLevel.LOW),
            (SpliceCondition.FAIR, RiskLevel.LOW),
            (SpliceCondition.DEGRADED, RiskLevel.MODERATE),
        ]:
            entry = ConditionHistory(
                splice_id=splice.id,
                condition=cond,
                severity=0.3,
                confidence=0.8,
                risk_level=risk,
                notes="Test entry",
            )
            db_session.add(entry)
            entries.append(entry)

        await db_session.flush()

        result = await db_session.execute(
            select(ConditionHistory).where(
                ConditionHistory.splice_id == splice.id
            )
        )
        fetched = result.scalars().all()
        assert len(fetched) == 3
        conditions = [h.condition for h in fetched]
        assert SpliceCondition.GOOD in conditions
        assert SpliceCondition.DEGRADED in conditions


class TestRelationships:
    """Test FK relationships between models."""

    async def test_splice_to_inspections(self, db_session):
        """Splice -> Inspection relationship works."""
        splice = Splice(
            name="Splice-Rel", belt_id="BELT-A", position=40.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        insp1 = Inspection(splice_id=splice.id, status=InspectionStatus.COMPLETED)
        insp2 = Inspection(splice_id=splice.id, status=InspectionStatus.PENDING)
        db_session.add_all([insp1, insp2])
        await db_session.flush()

        result = await db_session.execute(
            select(Inspection).where(Inspection.splice_id == splice.id)
        )
        inspections = result.scalars().all()
        assert len(inspections) == 2

    async def test_inspection_to_sensor_measurements(self, db_session):
        """Inspection -> SensorMeasurement relationship works."""
        splice = Splice(
            name="Splice-Sensor", belt_id="BELT-A", position=45.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        insp = Inspection(splice_id=splice.id, status=InspectionStatus.IN_PROGRESS)
        db_session.add(insp)
        await db_session.flush()

        measurement = SensorMeasurement(
            inspection_id=insp.id,
            splice_id=splice.id,
            sensor_type=SensorType.VISION,
            anomaly_score=0.3,
            confidence=0.8,
            value_json='{"score": 0.3}',
        )
        db_session.add(measurement)
        await db_session.flush()

        assert measurement.id is not None
        assert measurement.inspection_id == insp.id
        assert measurement.sensor_type == SensorType.VISION

    async def test_splice_to_alerts(self, db_session):
        """Splice -> Alert relationship works."""
        splice = Splice(
            name="Splice-Alert-Rel", belt_id="BELT-A", position=50.0,
            condition=SpliceCondition.POOR, severity=0.8, confidence=0.9,
            risk_level=RiskLevel.HIGH,
        )
        db_session.add(splice)
        await db_session.flush()

        alert = Alert(
            splice_id=splice.id,
            severity=AlertSeverity.HIGH,
            confidence=0.85,
            risk_score=0.8,
            status=AlertStatus.ACTIVE,
        )
        db_session.add(alert)
        await db_session.flush()

        result = await db_session.execute(
            select(Alert).where(Alert.splice_id == splice.id)
        )
        alerts = result.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH

    async def test_fusion_to_dive_chain(self, db_session):
        """FusionResult -> DIVEEvent -> ATCEResult chain works."""
        splice = Splice(
            name="Splice-Chain", belt_id="BELT-A", position=55.0,
            condition=SpliceCondition.GOOD, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        db_session.add(splice)
        await db_session.flush()

        insp = Inspection(splice_id=splice.id, status=InspectionStatus.COMPLETED)
        db_session.add(insp)
        await db_session.flush()

        fusion = FusionResult(
            inspection_id=insp.id,
            splice_id=splice.id,
            vision_score=0.8,
            thermal_score=0.7,
            mechanical_score=0.6,
            conductive_score=0.1,
            overall_confidence=0.75,
            fusion_status=FusionStatus.COMPLETE,
        )
        db_session.add(fusion)
        await db_session.flush()

        dive = DIVEEvent(
            fusion_result_id=fusion.id,
            splice_id=splice.id,
            event_type=DIVEEventType.DETECTION,
            confidence=0.75,
            start_time=datetime.utcnow(),
            persistence_count=1,
            status=DIVEStatus.ACTIVE,
        )
        db_session.add(dive)
        await db_session.flush()

        atce = ATCEResult(
            dive_event_id=dive.id,
            splice_id=splice.id,
            previous_state="GOOD",
            current_state="DEGRADED",
            trend=ATCETrend.DEGRADING,
            persistence=1,
            recurrence=False,
        )
        db_session.add(atce)
        await db_session.flush()

        assert atce.id is not None
        assert atce.dive_event_id == dive.id
        assert dive.fusion_result_id == fusion.id

    async def test_system_event_creation(self, db_session):
        """SystemEvent can be created independently."""
        event = SystemEvent(
            event_type="INSPECTION_COMPLETE",
            module="simulation",
            message="Test cycle completed",
            severity=SystemEventSeverity.INFO,
        )
        db_session.add(event)
        await db_session.flush()

        assert event.id is not None
        assert event.event_type == "INSPECTION_COMPLETE"
        assert event.severity == SystemEventSeverity.INFO
