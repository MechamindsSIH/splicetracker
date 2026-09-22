"""Repository classes encapsulating database queries for each model."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    ATCEResult,
    ConditionHistory,
    ConductiveEvent,
    DIVEEvent,
    FusionResult,
    Inspection,
    InspectionStatus,
    MechanicalEvent,
    RiskLevel,
    SensorMeasurement,
    Splice,
    SpliceCondition,
    SystemEvent,
    SystemEventSeverity,
    ThermalEvent,
    VisionEvent,
)


class SpliceRepository:
    """CRUD and query operations for Splice entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Splice:
        splice = Splice(**kwargs)
        self.session.add(splice)
        await self.session.flush()
        return splice

    async def get_by_id(self, splice_id: int) -> Optional[Splice]:
        result = await self.session.execute(
            select(Splice).where(Splice.id == splice_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Splice]:
        result = await self.session.execute(
            select(Splice).offset(skip).limit(limit).order_by(Splice.id)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Splice.id)))
        return result.scalar_one()

    async def update(self, splice_id: int, **kwargs) -> Optional[Splice]:
        kwargs["updated_at"] = datetime.utcnow()
        await self.session.execute(
            update(Splice).where(Splice.id == splice_id).values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(splice_id)

    async def get_by_belt(self, belt_id: str) -> List[Splice]:
        result = await self.session.execute(
            select(Splice)
            .where(Splice.belt_id == belt_id)
            .order_by(Splice.position)
        )
        return list(result.scalars().all())

    async def get_by_condition(self, condition: SpliceCondition) -> List[Splice]:
        result = await self.session.execute(
            select(Splice).where(Splice.condition == condition)
        )
        return list(result.scalars().all())

    async def get_by_risk_level(self, risk_level: RiskLevel) -> List[Splice]:
        result = await self.session.execute(
            select(Splice).where(Splice.risk_level == risk_level)
        )
        return list(result.scalars().all())

    async def get_risk_distribution(self) -> Dict[str, int]:
        result = await self.session.execute(
            select(Splice.risk_level, func.count(Splice.id)).group_by(Splice.risk_level)
        )
        return {str(row[0].value) if row[0] else "UNKNOWN": row[1] for row in result.all()}

    async def get_condition_distribution(self) -> Dict[str, int]:
        result = await self.session.execute(
            select(Splice.condition, func.count(Splice.id)).group_by(Splice.condition)
        )
        return {str(row[0].value) if row[0] else "UNKNOWN": row[1] for row in result.all()}

    async def delete(self, splice_id: int) -> bool:
        splice = await self.get_by_id(splice_id)
        if splice:
            await self.session.delete(splice)
            await self.session.flush()
            return True
        return False


class InspectionRepository:
    """CRUD and query operations for Inspection entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Inspection:
        inspection = Inspection(**kwargs)
        self.session.add(inspection)
        await self.session.flush()
        return inspection

    async def get_by_id(self, inspection_id: int) -> Optional[Inspection]:
        result = await self.session.execute(
            select(Inspection).where(Inspection.id == inspection_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_details(self, inspection_id: int) -> Optional[Inspection]:
        result = await self.session.execute(
            select(Inspection)
            .where(Inspection.id == inspection_id)
            .options(
                selectinload(Inspection.sensor_measurements),
                selectinload(Inspection.vision_events),
                selectinload(Inspection.thermal_events),
                selectinload(Inspection.conductive_events),
                selectinload(Inspection.mechanical_events),
                selectinload(Inspection.fusion_results).selectinload(FusionResult.dive_events).selectinload(DIVEEvent.atce_results),
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Inspection]:
        result = await self.session.execute(
            select(Inspection)
            .offset(skip)
            .limit(limit)
            .order_by(Inspection.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_splice(self, splice_id: int, limit: int = 50) -> List[Inspection]:
        result = await self.session.execute(
            select(Inspection)
            .where(Inspection.splice_id == splice_id)
            .order_by(Inspection.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Inspection.id)))
        return result.scalar_one()

    async def count_by_status(self, status: InspectionStatus) -> int:
        result = await self.session.execute(
            select(func.count(Inspection.id)).where(Inspection.status == status)
        )
        return result.scalar_one()

    async def update_status(
        self,
        inspection_id: int,
        status: InspectionStatus,
        results_json: Optional[str] = None,
    ) -> Optional[Inspection]:
        values: Dict[str, Any] = {"status": status}
        if status == InspectionStatus.COMPLETED:
            values["completed_at"] = datetime.utcnow()
        if results_json is not None:
            values["results_json"] = results_json
        await self.session.execute(
            update(Inspection).where(Inspection.id == inspection_id).values(**values)
        )
        await self.session.flush()
        return await self.get_by_id(inspection_id)

    async def get_latest(self) -> Optional[Inspection]:
        result = await self.session.execute(
            select(Inspection).order_by(Inspection.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()


class AlertRepository:
    """CRUD and query operations for Alert entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Alert:
        alert = Alert(**kwargs)
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get_by_id(self, alert_id: int) -> Optional[Alert]:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        splice_id: Optional[int] = None,
    ) -> List[Alert]:
        query = select(Alert)
        if status is not None:
            query = query.where(Alert.status == status)
        if severity is not None:
            query = query.where(Alert.severity == severity)
        if splice_id is not None:
            query = query.where(Alert.splice_id == splice_id)
        query = query.offset(skip).limit(limit).order_by(Alert.timestamp.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, status: Optional[AlertStatus] = None) -> int:
        query = select(func.count(Alert.id))
        if status is not None:
            query = query.where(Alert.status == status)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def acknowledge(
        self, alert_id: int, acknowledged_by: str
    ) -> Optional[Alert]:
        now = datetime.utcnow()
        await self.session.execute(
            update(Alert)
            .where(Alert.id == alert_id)
            .values(
                status=AlertStatus.ACKNOWLEDGED,
                acknowledged_at=now,
                acknowledged_by=acknowledged_by,
            )
        )
        await self.session.flush()
        return await self.get_by_id(alert_id)

    async def resolve(self, alert_id: int) -> Optional[Alert]:
        await self.session.execute(
            update(Alert)
            .where(Alert.id == alert_id)
            .values(status=AlertStatus.RESOLVED)
        )
        await self.session.flush()
        return await self.get_by_id(alert_id)

    async def get_active_by_splice(self, splice_id: int) -> List[Alert]:
        result = await self.session.execute(
            select(Alert)
            .where(Alert.splice_id == splice_id, Alert.status == AlertStatus.ACTIVE)
            .order_by(Alert.timestamp.desc())
        )
        return list(result.scalars().all())


class EventRepository:
    """CRUD and query operations for sensor and analysis event entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Sensor Measurements ────────────────────────────────────────────

    async def create_sensor_measurement(self, **kwargs) -> SensorMeasurement:
        measurement = SensorMeasurement(**kwargs)
        self.session.add(measurement)
        await self.session.flush()
        return measurement

    async def get_sensor_measurements(
        self, inspection_id: int, sensor_type: Optional[str] = None
    ) -> List[SensorMeasurement]:
        query = select(SensorMeasurement).where(
            SensorMeasurement.inspection_id == inspection_id
        )
        if sensor_type is not None:
            query = query.where(SensorMeasurement.sensor_type == sensor_type)
        result = await self.session.execute(query.order_by(SensorMeasurement.timestamp))
        return list(result.scalars().all())

    # ── Vision Events ──────────────────────────────────────────────────

    async def create_vision_event(self, **kwargs) -> VisionEvent:
        event = VisionEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_vision_events(self, inspection_id: int) -> List[VisionEvent]:
        result = await self.session.execute(
            select(VisionEvent)
            .where(VisionEvent.inspection_id == inspection_id)
            .order_by(VisionEvent.timestamp)
        )
        return list(result.scalars().all())

    # ── Thermal Events ─────────────────────────────────────────────────

    async def create_thermal_event(self, **kwargs) -> ThermalEvent:
        event = ThermalEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_thermal_events(self, inspection_id: int) -> List[ThermalEvent]:
        result = await self.session.execute(
            select(ThermalEvent)
            .where(ThermalEvent.inspection_id == inspection_id)
            .order_by(ThermalEvent.timestamp)
        )
        return list(result.scalars().all())

    # ── Conductive Events ──────────────────────────────────────────────

    async def create_conductive_event(self, **kwargs) -> ConductiveEvent:
        event = ConductiveEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_conductive_events(self, inspection_id: int) -> List[ConductiveEvent]:
        result = await self.session.execute(
            select(ConductiveEvent)
            .where(ConductiveEvent.inspection_id == inspection_id)
            .order_by(ConductiveEvent.timestamp)
        )
        return list(result.scalars().all())

    # ── Mechanical Events ──────────────────────────────────────────────

    async def create_mechanical_event(self, **kwargs) -> MechanicalEvent:
        event = MechanicalEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_mechanical_events(self, inspection_id: int) -> List[MechanicalEvent]:
        result = await self.session.execute(
            select(MechanicalEvent)
            .where(MechanicalEvent.inspection_id == inspection_id)
            .order_by(MechanicalEvent.timestamp)
        )
        return list(result.scalars().all())

    # ── Fusion Results ─────────────────────────────────────────────────

    async def create_fusion_result(self, **kwargs) -> FusionResult:
        result_obj = FusionResult(**kwargs)
        self.session.add(result_obj)
        await self.session.flush()
        return result_obj

    async def get_fusion_results(self, inspection_id: int) -> List[FusionResult]:
        result = await self.session.execute(
            select(FusionResult)
            .where(FusionResult.inspection_id == inspection_id)
            .order_by(FusionResult.timestamp)
        )
        return list(result.scalars().all())

    async def get_latest_fusion_for_splice(self, splice_id: int) -> Optional[FusionResult]:
        result = await self.session.execute(
            select(FusionResult)
            .where(FusionResult.splice_id == splice_id)
            .order_by(FusionResult.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── DIVE Events ────────────────────────────────────────────────────

    async def create_dive_event(self, **kwargs) -> DIVEEvent:
        event = DIVEEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_dive_events(
        self, fusion_result_id: Optional[int] = None, splice_id: Optional[int] = None
    ) -> List[DIVEEvent]:
        query = select(DIVEEvent)
        if fusion_result_id is not None:
            query = query.where(DIVEEvent.fusion_result_id == fusion_result_id)
        if splice_id is not None:
            query = query.where(DIVEEvent.splice_id == splice_id)
        result = await self.session.execute(query.order_by(DIVEEvent.start_time.desc()))
        return list(result.scalars().all())

    # ── ATCE Results ───────────────────────────────────────────────────

    async def create_atce_result(self, **kwargs) -> ATCEResult:
        result_obj = ATCEResult(**kwargs)
        self.session.add(result_obj)
        await self.session.flush()
        return result_obj

    async def get_atce_results(
        self, dive_event_id: Optional[int] = None, splice_id: Optional[int] = None
    ) -> List[ATCEResult]:
        query = select(ATCEResult)
        if dive_event_id is not None:
            query = query.where(ATCEResult.dive_event_id == dive_event_id)
        if splice_id is not None:
            query = query.where(ATCEResult.splice_id == splice_id)
        result = await self.session.execute(query.order_by(ATCEResult.timestamp.desc()))
        return list(result.scalars().all())

    async def get_latest_atce_for_splice(self, splice_id: int) -> Optional[ATCEResult]:
        result = await self.session.execute(
            select(ATCEResult)
            .where(ATCEResult.splice_id == splice_id)
            .order_by(ATCEResult.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Anomaly counts ─────────────────────────────────────────────────

    async def count_anomalies(self, threshold: float = 0.5) -> int:
        """Count sensor measurements whose anomaly_score exceeds threshold."""
        result = await self.session.execute(
            select(func.count(SensorMeasurement.id)).where(
                SensorMeasurement.anomaly_score > threshold
            )
        )
        return result.scalar_one()


class ConditionRepository:
    """CRUD and query operations for ConditionHistory."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ConditionHistory:
        entry = ConditionHistory(**kwargs)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_by_splice(
        self, splice_id: int, limit: int = 100
    ) -> List[ConditionHistory]:
        result = await self.session.execute(
            select(ConditionHistory)
            .where(ConditionHistory.splice_id == splice_id)
            .order_by(ConditionHistory.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_for_splice(self, splice_id: int) -> Optional[ConditionHistory]:
        result = await self.session.execute(
            select(ConditionHistory)
            .where(ConditionHistory.splice_id == splice_id)
            .order_by(ConditionHistory.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ConditionHistory]:
        result = await self.session.execute(
            select(ConditionHistory)
            .offset(skip)
            .limit(limit)
            .order_by(ConditionHistory.timestamp.desc())
        )
        return list(result.scalars().all())


class SystemEventRepository:
    """CRUD and query operations for SystemEvent."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> SystemEvent:
        event = SystemEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_by_id(self, event_id: int) -> Optional[SystemEvent]:
        result = await self.session.execute(
            select(SystemEvent).where(SystemEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        event_type: Optional[str] = None,
        severity: Optional[SystemEventSeverity] = None,
    ) -> List[SystemEvent]:
        query = select(SystemEvent)
        if event_type is not None:
            query = query.where(SystemEvent.event_type == event_type)
        if severity is not None:
            query = query.where(SystemEvent.severity == severity)
        query = query.offset(skip).limit(limit).order_by(SystemEvent.timestamp.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(SystemEvent.id)))
        return result.scalar_one()

    async def log(
        self,
        event_type: str,
        module: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: SystemEventSeverity = SystemEventSeverity.INFO,
    ) -> SystemEvent:
        return await self.create(
            event_type=event_type,
            module=module,
            message=message,
            details_json=json.dumps(details) if details else None,
            severity=severity,
        )
