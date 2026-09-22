"""End-to-end test: sensor input -> processing -> fusion -> DIVE -> ATCE -> DB.

This test exercises the complete chain from hardware simulation providers
through the intelligence pipeline to database persistence.
"""

import json
import pytest
from datetime import datetime

from backend.app.hardware.thermal import SimulationThermalProvider
from backend.app.hardware.conductive import SimulationConductiveProvider
from backend.app.hardware.mechanical import SimulationMechanicalProvider
from backend.app.intelligence.sensor_fusion import SensorFusionEngine
from backend.app.intelligence.dive_engine import DIVEEngine
from backend.app.intelligence.atce_engine import ATCEEngine
from backend.app.database.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    ConditionHistory,
    Inspection,
    InspectionStatus,
    RiskLevel,
    Splice,
    SpliceCondition,
)
from backend.app.database.repositories import (
    AlertRepository,
    ConditionRepository,
    InspectionRepository,
    SpliceRepository,
)


def _risk_from_score(overall, is_anomaly):
    if not is_anomaly:
        return SpliceCondition.GOOD, RiskLevel.LOW
    if overall > 0.8:
        return SpliceCondition.CRITICAL, RiskLevel.CRITICAL
    if overall > 0.6:
        return SpliceCondition.POOR, RiskLevel.HIGH
    if overall > 0.4:
        return SpliceCondition.DEGRADED, RiskLevel.MODERATE
    return SpliceCondition.FAIR, RiskLevel.LOW


def _alert_severity(overall):
    if overall > 0.8:
        return AlertSeverity.CRITICAL
    if overall > 0.6:
        return AlertSeverity.HIGH
    return AlertSeverity.WARNING


class TestSensorToAlert:
    """Full chain: sensor -> processing -> fusion -> DIVE -> ATCE -> risk -> alert -> DB."""

    async def test_sensor_to_alert(self, db_session):
        """Complete chain from sensor input to alert stored in DB."""
        splice_repo = SpliceRepository(db_session)
        splice = await splice_repo.create(
            name="Splice-E2E-001",
            belt_id="BELT-A",
            position=42.0,
            installed_date=datetime.utcnow(),
            condition=SpliceCondition.GOOD,
            severity=0.0,
            confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        await db_session.flush()
        splice_id = splice.id

        insp_repo = InspectionRepository(db_session)
        inspection = await insp_repo.create(
            splice_id=splice_id,
            status=InspectionStatus.IN_PROGRESS,
        )
        await db_session.flush()

        thermal = SimulationThermalProvider(baseline=36.0)
        thermal.set_anomaly(True, intensity=0.8)
        thermal_reading = await thermal.read()

        conductive = SimulationConductiveProvider()
        conductive.trigger_break()
        conductive_reading = await conductive.read()

        mechanical = SimulationMechanicalProvider()
        mechanical.set_anomaly(True, intensity=0.7)
        mech_reading = await mechanical.read()

        vision_score = 0.85
        observations = {
            "vision": {"anomaly_score": vision_score, "confidence": 0.9, "available": True},
            "thermal": {
                "anomaly_score": thermal_reading["thermal_anomaly_score"],
                "confidence": 0.85, "available": True,
            },
            "conductive": {
                "anomaly_score": conductive_reading["anomaly_score"],
                "confidence": 0.95, "available": True,
            },
            "mechanical": {
                "anomaly_score": mech_reading["anomaly_score"],
                "confidence": 0.9, "available": True,
            },
        }

        fusion_engine = SensorFusionEngine()
        fusion_result = await fusion_engine.fuse(observations)
        assert fusion_result.fusion_status in (
            "HIGH_CONFIDENCE_DEFECT", "MODERATE_CONFIDENCE", "LOW_CONFIDENCE"
        )
        assert fusion_result.weighted_anomaly_score > 0.3

        dive_engine = DIVEEngine(config={"merge_window_seconds": 999})
        dive_event = await dive_engine.process(fusion_result.to_dict(), str(splice_id))
        assert dive_event.status == "ACTIVE"
        assert dive_event.persistence_count >= 1

        atce_engine = ATCEEngine()
        atce_result = await atce_engine.analyze(dive_event.to_dict(), str(splice_id), [])
        assert atce_result.current_state != "NORMAL"

        overall_score = fusion_result.weighted_anomaly_score
        is_anomaly = fusion_result.fusion_status != "NORMAL"
        new_condition, new_risk = _risk_from_score(overall_score, is_anomaly)

        await splice_repo.update(
            splice_id,
            condition=new_condition,
            severity=round(overall_score, 4),
            confidence=round(fusion_result.overall_confidence, 4),
            risk_level=new_risk,
        )
        await db_session.flush()

        cond_repo = ConditionRepository(db_session)
        await cond_repo.create(
            splice_id=splice_id,
            condition=new_condition,
            severity=round(overall_score, 4),
            confidence=round(fusion_result.overall_confidence, 4),
            risk_level=new_risk,
            trigger_event_id=inspection.id,
            notes="E2E test",
        )
        await db_session.flush()

        alert_repo = AlertRepository(db_session)
        if is_anomaly and overall_score > 0.3:
            sev = _alert_severity(overall_score)
            alert = await alert_repo.create(
                splice_id=splice_id,
                severity=sev,
                defect_type="multi_sensor",
                confidence=round(fusion_result.overall_confidence, 4),
                risk_score=round(overall_score, 4),
                reason=f"E2E anomaly (score={overall_score:.2f})",
                recommended_action="Schedule maintenance",
                status=AlertStatus.ACTIVE,
                location="Position 42.0m",
            )
            await db_session.flush()

        updated_splice = await splice_repo.get_by_id(splice_id)
        assert updated_splice is not None
        assert updated_splice.condition == new_condition
        assert updated_splice.risk_level == new_risk
        assert updated_splice.severity > 0

        history = await cond_repo.get_by_splice(splice_id)
        assert len(history) >= 1
        assert history[0].condition == new_condition

        alerts = await alert_repo.get_active_by_splice(splice_id)
        assert len(alerts) >= 1
        assert alerts[0].status == AlertStatus.ACTIVE
        assert alerts[0].defect_type == "multi_sensor"
        assert alerts[0].risk_score > 0

        await insp_repo.update_status(
            inspection.id,
            InspectionStatus.COMPLETED,
            results_json=json.dumps({
                "fusion_status": fusion_result.fusion_status,
                "overall_score": overall_score,
                "dive_event_type": dive_event.event_type,
                "atce_classification": atce_result.classification,
            }),
        )
        await db_session.flush()

        completed_insp = await insp_repo.get_by_id(inspection.id)
        assert completed_insp.status == InspectionStatus.COMPLETED
        assert completed_insp.completed_at is not None
        assert completed_insp.results_json is not None

    async def test_normal_sensor_to_no_alert(self, db_session):
        """Normal sensor readings produce no alert in the DB."""
        splice_repo = SpliceRepository(db_session)
        splice = await splice_repo.create(
            name="Splice-E2E-Normal",
            belt_id="BELT-A",
            position=50.0,
            condition=SpliceCondition.GOOD,
            severity=0.0,
            confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        await db_session.flush()

        thermal = SimulationThermalProvider(baseline=36.0)
        thermal_reading = await thermal.read()

        conductive = SimulationConductiveProvider()
        conductive_reading = await conductive.read()

        mechanical = SimulationMechanicalProvider()
        mech_reading = await mechanical.read()

        observations = {
            "vision": {"anomaly_score": 0.1, "confidence": 0.9, "available": True},
            "thermal": {
                "anomaly_score": thermal_reading["thermal_anomaly_score"],
                "confidence": 0.85, "available": True,
            },
            "conductive": {
                "anomaly_score": conductive_reading["anomaly_score"],
                "confidence": 0.95, "available": True,
            },
            "mechanical": {
                "anomaly_score": mech_reading["anomaly_score"],
                "confidence": 0.9, "available": True,
            },
        }

        fusion_engine = SensorFusionEngine()
        fusion_result = await fusion_engine.fuse(observations)
        assert fusion_result.fusion_status == "NORMAL"

        dive_engine = DIVEEngine()
        dive_event = await dive_engine.process(fusion_result.to_dict(), str(splice.id))
        assert dive_event.event_type == "normal"

        alert_repo = AlertRepository(db_session)
        alerts = await alert_repo.get_active_by_splice(splice.id)
        assert len(alerts) == 0
