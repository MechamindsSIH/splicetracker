"""Simulation control endpoints."""

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..core.events import EventBus, EventType
from ..core.schemas import SimulationScenarioRequest, SimulationStartRequest
from ..database.database import async_session, get_session_factory
from ..database.models import (
    AlertSeverity,
    AlertStatus,
    ATCETrend,
    DIVEEventType,
    DIVEStatus,
    FusionStatus,
    InspectionStatus,
    RiskLevel,
    SensorType,
    SpliceCondition,
    SystemEventSeverity,
)
from ..database.repositories import (
    AlertRepository,
    ConditionRepository,
    EventRepository,
    InspectionRepository,
    SpliceRepository,
    SystemEventRepository,
)

logger = logging.getLogger("app.simulation")
router = APIRouter(prefix="/api/simulation", tags=["simulation"])

_simulation_task: Optional[asyncio.Task] = None
_simulation_running = False


async def _create_seed_splices(session: AsyncSession, count: int) -> list:
    """Ensure at least `count` splices exist, creating new ones as needed."""
    repo = SpliceRepository(session)
    existing = await repo.get_all(limit=count)
    if len(existing) >= count:
        return existing[:count]

    needed = count - len(existing)
    for i in range(needed):
        idx = len(existing) + i + 1
        await repo.create(
            name=f"Splice-{idx:03d}",
            belt_id="BELT-A",
            position=round(idx * (100.0 / count), 2),
            installed_date=datetime.utcnow(),
            condition=SpliceCondition.GOOD,
            severity=0.0,
            confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
    await session.commit()
    return await repo.get_all(limit=count)


async def _run_simulation(splice_count: int, interval: float, anomaly_prob: float):
    """Main simulation loop that generates synthetic inspections and events."""
    global _simulation_running
    _simulation_running = True
    bus = EventBus.get_instance()
    factory = get_session_factory()

    logger.info(
        "Simulation started: splices=%d, interval=%.1fs, anomaly_prob=%.2f",
        splice_count, interval, anomaly_prob,
    )

    # Seed splices
    async with factory() as session:
        try:
            splices = await _create_seed_splices(session, splice_count)
            splice_ids = [s.id for s in splices]
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    cycle = 0
    while _simulation_running:
        cycle += 1
        try:
            async with factory() as session:
                try:
                    splice_id = random.choice(splice_ids)
                    await _run_inspection_cycle(
                        session, splice_id, anomaly_prob, bus, cycle
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Simulation cycle %d error: %s", cycle, exc)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break

    _simulation_running = False
    logger.info("Simulation stopped after %d cycles", cycle)


SCENARIO_CONFIGS: Dict[str, Dict[str, Any]] = {
    "normal": {
        "name": "Normal Operation",
        "description": "Nominal belt speeds and baseline multi-sensor signals",
        "duration_steps": 5,
        "anomaly_prob": 0.02,
        "modality_bias": "normal",
    },
    "visual_anomaly": {
        "name": "Visual Anomaly",
        "description": "High-speed line-scan camera detects cover tear / edge crack",
        "duration_steps": 5,
        "anomaly_prob": 0.95,
        "modality_bias": "vision",
    },
    "thermal_anomaly": {
        "name": "Thermal Anomaly",
        "description": "LWIR infrared radiometric hotspot with elevated delta-T",
        "duration_steps": 5,
        "anomaly_prob": 0.95,
        "modality_bias": "thermal",
    },
    "conductive_break": {
        "name": "Conductive Break",
        "description": "Inductive loop continuity loss indicating internal cord rupture",
        "duration_steps": 4,
        "anomaly_prob": 1.0,
        "modality_bias": "conductive",
    },
    "mechanical_anomaly": {
        "name": "Mechanical Anomaly",
        "description": "Dynamic imbalance and harmonic vibration resonance spike",
        "duration_steps": 5,
        "anomaly_prob": 0.95,
        "modality_bias": "mechanical",
    },
    "multi_sensor": {
        "name": "Multi-Sensor Fusion",
        "description": "Simultaneous co-located anomalies across all 4 sensing modalities",
        "duration_steps": 6,
        "anomaly_prob": 0.98,
        "modality_bias": "multi",
    },
    "multi_defect": {
        "name": "Multi-Defect Anomaly",
        "description": "Simultaneous multi-modality structural anomaly",
        "duration_steps": 5,
        "anomaly_prob": 0.98,
        "modality_bias": "multi",
    },
    "progressive_degradation": {
        "name": "Progressive Degradation",
        "description": "Stepwise fatigue wear increasing severity from 0.12 to 0.88",
        "duration_steps": 8,
        "anomaly_prob": 0.90,
        "modality_bias": "progressive",
    },
    "degrading": {
        "name": "Degrading Splice",
        "description": "Gradually worsening splice condition over time",
        "duration_steps": 6,
        "anomaly_prob": 0.75,
        "modality_bias": "progressive",
    },
    "critical": {
        "name": "Critical Failure",
        "description": "Emergency catastrophic failure threshold triggering shutdown alarm",
        "duration_steps": 4,
        "anomaly_prob": 1.0,
        "modality_bias": "critical",
    },
    "high_risk": {
        "name": "High Risk Splice",
        "description": "Severe defect condition exceeding safety margin",
        "duration_steps": 5,
        "anomaly_prob": 0.90,
        "modality_bias": "critical",
    },
    "intermittent": {
        "name": "Intermittent Fault",
        "description": "Sporadic transient spikes alternating with nominal readings",
        "duration_steps": 6,
        "anomaly_prob": 0.50,
        "modality_bias": "intermittent",
    },
    "resolved": {
        "name": "Resolved Intervention",
        "description": "Defect detection followed by maintenance intervention recovery",
        "duration_steps": 7,
        "anomaly_prob": 0.40,
        "modality_bias": "resolved",
    },
    "demo": {
        "name": "Full Inspection Demo",
        "description": "Complete 10-step multi-stage operational demonstration",
        "duration_steps": 10,
        "anomaly_prob": 0.65,
        "modality_bias": "demo",
    },
}


async def _run_inspection_cycle(
    session: AsyncSession,
    splice_id: int,
    anomaly_prob: float,
    bus: EventBus,
    cycle: int,
    scenario_override: Optional[Dict[str, Any]] = None,
    step_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run one complete inspection cycle for a splice with full multi-modal telemetry."""
    now = datetime.utcnow()
    insp_repo = InspectionRepository(session)
    event_repo = EventRepository(session)
    splice_repo = SpliceRepository(session)
    alert_repo = AlertRepository(session)
    cond_repo = ConditionRepository(session)
    sys_repo = SystemEventRepository(session)

    splice = await splice_repo.get_by_id(splice_id)
    splice_name = splice.name if splice else f"Splice-{splice_id:03d}"

    # Create inspection
    inspection = await insp_repo.create(
        splice_id=splice_id,
        status=InspectionStatus.IN_PROGRESS,
    )
    await bus.publish(EventType.INSPECTION_STARTED, {
        "inspection_id": inspection.id,
        "splice_id": splice_id,
        "splice_name": splice_name,
    }, source="simulation")

    bias = scenario_override.get("modality_bias") if scenario_override else None
    baseline_temp = 35.0
    delta = 0.5
    continuity = True
    rms_val = 0.45
    defect_type = None

    if bias == "normal":
        is_anomaly = False
        vision_score = random.uniform(0.02, 0.08)
        thermal_score = random.uniform(0.02, 0.07)
        conductive_score = 0.0
        mech_score = random.uniform(0.03, 0.10)
        rms_val = random.uniform(0.3, 0.7)
        delta = random.uniform(-1.0, 1.5)
        defect_type = None
    elif bias == "vision":
        is_anomaly = True
        vision_score = random.uniform(0.85, 0.98)
        thermal_score = random.uniform(0.10, 0.22)
        conductive_score = 0.0
        mech_score = random.uniform(0.12, 0.28)
        rms_val = random.uniform(0.8, 1.4)
        delta = random.uniform(1.5, 4.0)
        defect_type = random.choice(["splice_separation", "transverse_tear", "cover_wear", "edge_crack"])
    elif bias == "thermal":
        is_anomaly = True
        thermal_score = random.uniform(0.85, 0.98)
        delta = random.uniform(24.0, 42.0)
        vision_score = random.uniform(0.15, 0.32)
        conductive_score = 0.0
        mech_score = random.uniform(0.18, 0.35)
        rms_val = random.uniform(0.9, 1.6)
        defect_type = "hotspot_friction"
    elif bias == "conductive":
        is_anomaly = True
        continuity = False
        conductive_score = random.uniform(0.92, 1.0)
        vision_score = random.uniform(0.35, 0.55)
        thermal_score = random.uniform(0.15, 0.30)
        mech_score = random.uniform(0.25, 0.45)
        delta = random.uniform(2.0, 6.0)
        rms_val = random.uniform(1.2, 2.2)
        defect_type = "cord_rupture"
    elif bias == "mechanical":
        is_anomaly = True
        mech_score = random.uniform(0.88, 0.99)
        rms_val = random.uniform(5.8, 9.4)
        vision_score = random.uniform(0.20, 0.38)
        thermal_score = random.uniform(0.22, 0.42)
        conductive_score = 0.0
        delta = random.uniform(4.0, 9.0)
        defect_type = "dynamic_imbalance"
    elif bias == "multi":
        is_anomaly = True
        vision_score = random.uniform(0.82, 0.96)
        thermal_score = random.uniform(0.80, 0.94)
        mech_score = random.uniform(0.85, 0.97)
        conductive_score = random.uniform(0.70, 0.95)
        continuity = random.random() > 0.65
        delta = random.uniform(25.0, 39.0)
        rms_val = random.uniform(6.0, 8.8)
        defect_type = "multi_sensor_structural_failure"
    elif bias == "progressive":
        s_idx = step_info.get("step", 1) if step_info else 1
        t_steps = step_info.get("total_steps", 8) if step_info else 8
        prog = s_idx / max(1, t_steps)
        is_anomaly = prog > 0.25
        base = max(0.04, min(0.96, 0.05 + prog * 0.88 + random.uniform(-0.02, 0.02)))
        vision_score = max(0.0, min(1.0, base * random.uniform(0.9, 1.1)))
        thermal_score = max(0.0, min(1.0, base * random.uniform(0.85, 1.05)))
        mech_score = max(0.0, min(1.0, base * random.uniform(0.9, 1.15)))
        conductive_score = 0.0 if prog < 0.7 else round(base * 0.9, 4)
        continuity = conductive_score < 0.5
        delta = base * 32.0
        rms_val = 0.4 + base * 6.5
        defect_type = "surface_wear_fatigue" if prog < 0.6 else "core_delamination"
    elif bias == "critical":
        is_anomaly = True
        vision_score = random.uniform(0.94, 0.99)
        thermal_score = random.uniform(0.90, 0.99)
        mech_score = random.uniform(0.92, 0.99)
        conductive_score = 1.0
        continuity = False
        delta = random.uniform(34.0, 48.0)
        rms_val = random.uniform(7.5, 10.5)
        defect_type = "catastrophic_separation"
    elif bias == "intermittent":
        s_idx = step_info.get("step", 1) if step_info else 1
        is_burst = (s_idx % 2 == 1)
        is_anomaly = is_burst
        vision_score = random.uniform(0.72, 0.90) if is_burst else random.uniform(0.04, 0.12)
        thermal_score = random.uniform(0.65, 0.82) if is_burst else random.uniform(0.04, 0.10)
        mech_score = random.uniform(0.75, 0.93) if is_burst else random.uniform(0.05, 0.15)
        conductive_score = 0.0
        delta = random.uniform(18.0, 28.0) if is_burst else random.uniform(0.5, 2.0)
        rms_val = random.uniform(4.5, 7.0) if is_burst else random.uniform(0.4, 0.9)
        defect_type = "transient_resonance" if is_burst else None
    elif bias == "resolved":
        s_idx = step_info.get("step", 1) if step_info else 1
        t_steps = step_info.get("total_steps", 7) if step_info else 7
        is_repaired = (s_idx > t_steps // 2)
        is_anomaly = not is_repaired
        if is_repaired:
            vision_score = random.uniform(0.02, 0.08)
            thermal_score = random.uniform(0.02, 0.07)
            mech_score = random.uniform(0.03, 0.09)
            conductive_score = 0.0
            continuity = True
            delta = random.uniform(-0.5, 1.5)
            rms_val = random.uniform(0.3, 0.6)
            defect_type = None
        else:
            vision_score = random.uniform(0.72, 0.86)
            thermal_score = random.uniform(0.68, 0.82)
            mech_score = random.uniform(0.62, 0.80)
            conductive_score = 0.0
            continuity = True
            delta = random.uniform(18.0, 26.0)
            rms_val = random.uniform(3.8, 5.6)
            defect_type = "pre_repair_abrasion"
    elif bias == "demo":
        s_idx = step_info.get("step", 1) if step_info else 1
        phases = ["normal", "normal", "vision", "thermal", "mechanical", "multi", "critical", "resolved", "resolved", "normal"]
        ph = phases[min(s_idx - 1, len(phases) - 1)]
        if ph == "normal":
            is_anomaly = False
            vision_score, thermal_score, mech_score, conductive_score = 0.05, 0.04, 0.06, 0.0
            continuity = True
            defect_type = None
            delta, rms_val = 0.8, 0.5
        elif ph == "vision":
            is_anomaly = True
            vision_score, thermal_score, mech_score, conductive_score = 0.91, 0.16, 0.22, 0.0
            continuity = True
            defect_type = "splice_separation"
            delta, rms_val = 2.5, 0.9
        elif ph == "thermal":
            is_anomaly = True
            vision_score, thermal_score, mech_score, conductive_score = 0.24, 0.92, 0.28, 0.0
            continuity = True
            defect_type = "hotspot_friction"
            delta, rms_val = 31.0, 1.1
        elif ph == "mechanical":
            is_anomaly = True
            vision_score, thermal_score, mech_score, conductive_score = 0.20, 0.26, 0.94, 0.0
            continuity = True
            defect_type = "dynamic_imbalance"
            delta, rms_val = 4.0, 7.2
        elif ph == "multi":
            is_anomaly = True
            vision_score, thermal_score, mech_score, conductive_score = 0.86, 0.84, 0.90, 0.78
            continuity = False
            defect_type = "multi_sensor_structural_failure"
            delta, rms_val = 28.0, 6.8
        elif ph == "critical":
            is_anomaly = True
            vision_score, thermal_score, mech_score, conductive_score = 0.98, 0.96, 0.98, 1.0
            continuity = False
            defect_type = "catastrophic_separation"
            delta, rms_val = 42.0, 9.8
        else:
            is_anomaly = False
            vision_score, thermal_score, mech_score, conductive_score = 0.04, 0.03, 0.05, 0.0
            continuity = True
            defect_type = None
            delta, rms_val = 0.5, 0.4
    else:
        is_anomaly = random.random() < anomaly_prob
        base_score = random.uniform(0.55, 0.92) if is_anomaly else random.uniform(0.02, 0.25)
        vision_score = max(0.0, min(1.0, base_score + random.uniform(-0.08, 0.08)))
        thermal_score = max(0.0, min(1.0, base_score + random.uniform(-0.08, 0.08)))
        mech_score = max(0.0, min(1.0, base_score + random.uniform(-0.08, 0.08)))
        continuity = not is_anomaly or random.random() > 0.4
        conductive_score = 0.0 if continuity else random.uniform(0.6, 1.0)
        delta = random.uniform(8.0, 30.0) if is_anomaly else random.uniform(-1.0, 2.5)
        rms_val = random.uniform(2.5, 7.5) if is_anomaly else random.uniform(0.2, 1.2)
        defect_type = random.choice(["crack", "delamination", "wear", "misalignment"]) if is_anomaly else None

    # -- Vision sensor measurement & event --
    await event_repo.create_sensor_measurement(
        inspection_id=inspection.id,
        splice_id=splice_id,
        sensor_type=SensorType.VISION,
        value_json=json.dumps({"score": round(vision_score, 4)}),
        anomaly_score=round(vision_score, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
    )
    await event_repo.create_vision_event(
        inspection_id=inspection.id,
        splice_id=splice_id,
        timestamp=now,
        defect_type=defect_type or "normal",
        defect_confidence=round(vision_score, 4),
        anomaly_score=round(vision_score, 4),
        roi_json=json.dumps({"x": 100, "y": 100, "w": 200, "h": 200}),
        bounding_region_json=json.dumps({"x": 120, "y": 120, "w": 160, "h": 160}) if is_anomaly else None,
    )

    # -- Thermal sensor measurement & event --
    await event_repo.create_sensor_measurement(
        inspection_id=inspection.id,
        splice_id=splice_id,
        sensor_type=SensorType.THERMAL,
        value_json=json.dumps({"temperature": round(baseline_temp + delta, 2)}),
        anomaly_score=round(thermal_score, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
    )
    await event_repo.create_thermal_event(
        inspection_id=inspection.id,
        splice_id=splice_id,
        timestamp=now,
        temperature=round(baseline_temp + delta, 2),
        baseline_temperature=baseline_temp,
        delta_temperature=round(delta, 2),
        rate_of_change=round(random.uniform(0.0, 2.0), 3),
        thermal_anomaly_score=round(thermal_score, 4),
        hotspot_location_json=json.dumps({"x": 150, "y": 150, "radius_mm": 25}) if is_anomaly else None,
    )

    # -- Conductive sensor measurement & event --
    await event_repo.create_sensor_measurement(
        inspection_id=inspection.id,
        splice_id=splice_id,
        sensor_type=SensorType.CONDUCTIVE,
        value_json=json.dumps({"continuity": continuity}),
        anomaly_score=round(conductive_score, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
    )
    await event_repo.create_conductive_event(
        inspection_id=inspection.id,
        splice_id=splice_id,
        timestamp=now,
        continuity=continuity,
        previous_state="CONTINUOUS" if continuity else "BROKEN",
        transition="NONE" if continuity else "BREAK_DETECTED",
        duration_ms=round(random.uniform(15, 30), 1),
        anomaly_score=round(conductive_score, 4),
    )

    # -- Mechanical sensor measurement & event --
    await event_repo.create_sensor_measurement(
        inspection_id=inspection.id,
        splice_id=splice_id,
        sensor_type=SensorType.MECHANICAL,
        value_json=json.dumps({"rms": round(rms_val, 3)}),
        anomaly_score=round(mech_score, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
    )
    await event_repo.create_mechanical_event(
        inspection_id=inspection.id,
        splice_id=splice_id,
        timestamp=now,
        rms=round(rms_val, 3),
        peak=round(rms_val * random.uniform(1.5, 2.8), 3),
        variance=round((rms_val * 0.1) ** 2, 5),
        frequency_features_json=json.dumps({
            "dominant_freq": round(random.choice([12.5, 25.0, 50.0, 100.0]), 1),
            "spectral_centroid": round(random.uniform(50, 300), 1),
        }),
        anomaly_score=round(mech_score, 4),
    )

    # -- Multi-Sensor Fusion --
    overall = (vision_score * 0.35 + thermal_score * 0.25 + conductive_score * 0.20 + mech_score * 0.20)
    overall = round(max(0.0, min(1.0, overall)), 4)

    supporting = []
    contradicting = []
    for name, score in [("VISION", vision_score), ("THERMAL", thermal_score),
                         ("CONDUCTIVE", conductive_score), ("MECHANICAL", mech_score)]:
        if score > 0.35:
            supporting.append(name)
        else:
            contradicting.append(name)

    fusion_status = FusionStatus.COMPLETE
    if len(supporting) > 0 and len(contradicting) > 0:
        fusion_status = FusionStatus.CONFLICT if abs(len(supporting) - len(contradicting)) <= 1 else FusionStatus.PARTIAL

    fusion = await event_repo.create_fusion_result(
        inspection_id=inspection.id,
        splice_id=splice_id,
        timestamp=now,
        vision_score=round(vision_score, 4),
        thermal_score=round(thermal_score, 4),
        mechanical_score=round(mech_score, 4),
        conductive_score=round(conductive_score, 4),
        supporting_sensors=json.dumps(supporting),
        contradicting_sensors=json.dumps(contradicting),
        overall_confidence=round(overall, 4),
        fusion_status=fusion_status,
        evidence_json=json.dumps({"cycle": cycle, "anomaly": is_anomaly, "defect": defect_type}),
    )

    # -- DIVE event --
    if is_anomaly:
        dive_type = DIVEEventType.DETECTION if overall < 0.6 else DIVEEventType.ESCALATION
        dive = await event_repo.create_dive_event(
            fusion_result_id=fusion.id,
            splice_id=splice_id,
            event_type=dive_type,
            evidence_json=json.dumps({"supporting": supporting, "scores": [vision_score, thermal_score, mech_score, conductive_score]}),
            supporting_sensors_json=json.dumps(supporting),
            confidence=round(overall, 4),
            start_time=now,
            persistence_count=random.randint(1, 10),
            status=DIVEStatus.ACTIVE,
        )

        # -- ATCE result --
        trend = ATCETrend.DEGRADING if overall > 0.6 else ATCETrend.STABLE
        if overall > 0.8:
            trend = ATCETrend.RAPID_DEGRADATION

        await event_repo.create_atce_result(
            dive_event_id=dive.id,
            splice_id=splice_id,
            timestamp=now,
            previous_state="GOOD",
            current_state="DEGRADED" if overall < 0.7 else "POOR",
            trend=trend,
            persistence=random.randint(1, 5),
            recurrence=random.random() > 0.6,
            history_json=json.dumps({"cycles": [cycle]}),
        )

    # -- Splice condition update --
    if overall > 0.8:
        new_condition = SpliceCondition.CRITICAL
        new_risk = RiskLevel.CRITICAL
    elif overall > 0.6:
        new_condition = SpliceCondition.POOR
        new_risk = RiskLevel.HIGH
    elif overall > 0.35:
        new_condition = SpliceCondition.DEGRADED
        new_risk = RiskLevel.MODERATE
    elif overall > 0.2:
        new_condition = SpliceCondition.FAIR
        new_risk = RiskLevel.LOW
    else:
        new_condition = SpliceCondition.GOOD
        new_risk = RiskLevel.LOW

    await splice_repo.update(
        splice_id,
        condition=new_condition,
        severity=round(overall, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
        risk_level=new_risk,
    )

    await cond_repo.create(
        splice_id=splice_id,
        condition=new_condition,
        severity=round(overall, 4),
        confidence=round(random.uniform(0.85, 0.99), 4),
        risk_level=new_risk,
        trigger_event_id=inspection.id,
        notes=f"Simulation cycle {cycle} | {defect_type or 'nominal'}",
    )

    # -- Alert if warranted --
    if is_anomaly and overall > 0.45:
        if overall > 0.8:
            sev = AlertSeverity.CRITICAL
        elif overall > 0.6:
            sev = AlertSeverity.HIGH
        else:
            sev = AlertSeverity.WARNING

        alert = await alert_repo.create(
            splice_id=splice_id,
            severity=sev,
            defect_type=defect_type,
            confidence=round(overall, 4),
            risk_score=round(overall, 4),
            reason=f"Simulation alert: {defect_type or 'anomaly'} (score={overall:.3f}) on {splice_name}",
            recommended_action="Emergency shutdown" if sev == AlertSeverity.CRITICAL else "Schedule inspection",
            status=AlertStatus.ACTIVE,
            location=f"Belt {splice.belt_id if splice else 'BELT-01'}:{splice.position if splice else 100:.0f}m",
        )
        await bus.publish(EventType.ALERT_CREATED, {
            "alert_id": alert.id,
            "splice_id": splice_id,
            "severity": sev.value,
        }, source="simulation")

    # Complete inspection
    await insp_repo.update_status(
        inspection.id,
        InspectionStatus.COMPLETED,
        results_json=json.dumps({
            "anomaly": is_anomaly,
            "overall_score": round(overall, 4),
            "cycle": cycle,
            "defect_type": defect_type,
        }),
    )

    s_idx = step_info.get("step", cycle) if step_info else cycle
    tot_s = step_info.get("total_steps", 1) if step_info else 1
    default_label = f"{defect_type.replace('_', ' ').title() if defect_type else 'Nominal'}: overall={overall:.3f}"
    lbl = step_info.get("label", default_label) if step_info else default_label

    cycle_result = {
        "inspection_id": inspection.id,
        "splice_id": splice_id,
        "splice_name": splice_name,
        "cycle": cycle,
        "step": s_idx,
        "total_steps": tot_s,
        "label": lbl,
        "anomaly": is_anomaly,
        "overall_score": round(overall, 4),
        "risk_level": new_risk.value,
        "condition": new_condition.value,
        "defect_type": defect_type or "normal",
        "scores": {
            "vision": round(vision_score, 4),
            "thermal": round(thermal_score, 4),
            "mechanical": round(mech_score, 4),
            "conductive": round(conductive_score, 4),
            "fused": round(overall, 4),
        },
        "timestamp": now.isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "result": {
            "risk_result": {
                "risk_level": new_risk.value,
                "risk_score": round(overall, 4),
            },
            "fusion_result": {
                "overall_confidence": round(overall, 4),
                "fusion_status": fusion_status.value,
            },
        },
    }

    await bus.publish(EventType.INSPECTION_COMPLETED, cycle_result, source="simulation")

    await sys_repo.log(
        event_type="INSPECTION_COMPLETE",
        module="simulation",
        message=f"Cycle {cycle}: {splice_name}, anomaly={is_anomaly}, score={overall:.3f}",
        details={"cycle": cycle, "splice_id": splice_id, "anomaly": is_anomaly},
    )

    return cycle_result


@router.get("/status")
async def get_simulation_status():
    """Return current status of simulation engine and available scenarios."""
    return {
        "running": _simulation_running,
        "available_scenarios": SCENARIO_CONFIGS,
    }


@router.post("/start")
async def start_simulation(
    request: SimulationStartRequest = SimulationStartRequest(),
):
    """Start the background simulation loop."""
    global _simulation_task, _simulation_running

    if _simulation_running:
        raise HTTPException(status_code=409, detail="Simulation is already running")

    _simulation_task = asyncio.create_task(
        _run_simulation(
            splice_count=request.splice_count,
            interval=request.inspection_interval_seconds,
            anomaly_prob=request.anomaly_probability,
        )
    )

    return {
        "status": "started",
        "splice_count": request.splice_count,
        "interval_seconds": request.inspection_interval_seconds,
        "anomaly_probability": request.anomaly_probability,
    }


@router.post("/stop")
async def stop_simulation():
    """Stop the running simulation."""
    global _simulation_task, _simulation_running

    if not _simulation_running:
        raise HTTPException(status_code=409, detail="Simulation is not running")

    _simulation_running = False
    if _simulation_task and not _simulation_task.done():
        _simulation_task.cancel()
        try:
            await _simulation_task
        except asyncio.CancelledError:
            pass

    return {"status": "stopped"}


@router.post("/step")
async def run_single_step(
    request: Optional[Dict[str, Any]] = None,
    session: AsyncSession = Depends(async_session),
):
    """Trigger a single simulation inspection cycle on a splice."""
    splice_repo = SpliceRepository(session)
    splice_id = request.get("splice_id") if request else None

    if splice_id:
        splice = await splice_repo.get_by_id(splice_id)
        if not splice:
            raise HTTPException(status_code=404, detail="Splice not found")
        target_id = splice.id
    else:
        all_splices = await splice_repo.get_all(limit=1)
        if not all_splices:
            raise HTTPException(status_code=404, detail="No splices available.")
        target_id = all_splices[0].id

    bus = EventBus.get_instance()
    prob = float(request.get("anomaly_probability", 0.5)) if request else 0.5
    bias = request.get("modality_bias") if request else None

    override = {"modality_bias": bias} if bias else None
    step_info = {"step": 1, "total_steps": 1, "label": "Single Step Manual Trigger"}

    res = await _run_inspection_cycle(
        session, target_id, prob, bus, 1, scenario_override=override, step_info=step_info
    )
    await session.commit()
    return {"status": "completed", "result": res}


@router.post("/scenario")
async def run_scenario(
    request: SimulationScenarioRequest,
    session: AsyncSession = Depends(async_session),
):
    """Run a specific simulation scenario on a splice."""
    sc_key = request.scenario.lower()
    if sc_key not in SCENARIO_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {request.scenario}. Available: {list(SCENARIO_CONFIGS.keys())}",
        )

    config = SCENARIO_CONFIGS[sc_key]
    splice_repo = SpliceRepository(session)

    # Use specified splice or pick the first one
    if request.splice_id:
        splice = await splice_repo.get_by_id(request.splice_id)
        if splice is None:
            raise HTTPException(status_code=404, detail="Splice not found")
        target_id = splice.id
    else:
        all_splices = await splice_repo.get_all(limit=1)
        if not all_splices:
            raise HTTPException(status_code=404, detail="No splices available. Start simulation first.")
        target_id = all_splices[0].id

    iterations = config.get("duration_steps", 5)
    bus = EventBus.get_instance()

    executed_events = []
    for i in range(iterations):
        step_info = {
            "step": i + 1,
            "total_steps": iterations,
            "label": f"{config['name']} — Stage {i + 1}/{iterations}",
        }
        res = await _run_inspection_cycle(
            session, target_id, config["anomaly_prob"], bus, i + 1,
            scenario_override=config, step_info=step_info
        )
        executed_events.append(res)

    await session.commit()

    return {
        "status": "completed",
        "scenario": sc_key,
        "name": config["name"],
        "description": config["description"],
        "splice_id": target_id,
        "iterations": iterations,
        "events": executed_events,
    }

