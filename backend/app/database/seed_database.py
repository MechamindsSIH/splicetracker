"""SpliceTracker Database Seeder — MASSIVE SCALE edition.

Generates a full year of dense industrial operational data:
  - 16 splices across 4 conveyor belt assets
  - 365 days x 3 inspections/day/splice = ~17,520 inspections
  - 4 sensor modalities per inspection = ~70,080 sensor measurements
  - Full fusion, DIVE, ATCE, alerts, and condition history chains
  - 200+ system events and 300+ alerts across all severities
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session_factory, init_db
from .models import (
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

logger = logging.getLogger("splicetracker.seeder")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ─── Asset & Splice Definitions ───────────────────────────────────────────────

CONVEYOR_BELTS = [
    {
        "belt_id": "BELT-01",
        "name": "Overland Main Line 1",
        "length_m": 1200.0,
        "speed_mps": 4.2,
        "splices": [
            {"name": "Splice-001", "position": 120.0,  "age_days": 420, "condition": SpliceCondition.GOOD,     "risk": RiskLevel.LOW,      "severity": 0.06,  "trajectory": "stable"},
            {"name": "Splice-002", "position": 360.0,  "age_days": 380, "condition": SpliceCondition.GOOD,     "risk": RiskLevel.LOW,      "severity": 0.08,  "trajectory": "stable"},
            {"name": "Splice-003", "position": 600.0,  "age_days": 610, "condition": SpliceCondition.FAIR,     "risk": RiskLevel.MODERATE, "severity": 0.28,  "trajectory": "slow_degrade"},
            {"name": "Splice-004", "position": 840.0,  "age_days": 750, "condition": SpliceCondition.DEGRADED, "risk": RiskLevel.HIGH,     "severity": 0.62,  "trajectory": "fast_degrade"},
            {"name": "Splice-005", "position": 1080.0, "age_days": 190, "condition": SpliceCondition.GOOD,     "risk": RiskLevel.LOW,      "severity": 0.04,  "trajectory": "repaired"},
        ],
    },
    {
        "belt_id": "BELT-02",
        "name": "In-Plant Secondary Feeder",
        "length_m": 450.0,
        "speed_mps": 2.5,
        "splices": [
            {"name": "Splice-101", "position": 45.0,  "age_days": 280, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW, "severity": 0.05, "trajectory": "stable"},
            {"name": "Splice-102", "position": 150.0, "age_days": 210, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW, "severity": 0.04, "trajectory": "stable"},
            {"name": "Splice-103", "position": 270.0, "age_days": 540, "condition": SpliceCondition.FAIR, "risk": RiskLevel.LOW, "severity": 0.22, "trajectory": "slow_degrade"},
            {"name": "Splice-104", "position": 390.0, "age_days": 320, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW, "severity": 0.07, "trajectory": "stable"},
        ],
    },
    {
        "belt_id": "BELT-03",
        "name": "Stacker Staging Conveyor",
        "length_m": 320.0,
        "speed_mps": 3.1,
        "splices": [
            {"name": "Splice-201", "position": 60.0,  "age_days": 180, "condition": SpliceCondition.GOOD,    "risk": RiskLevel.LOW,      "severity": 0.05, "trajectory": "stable"},
            {"name": "Splice-202", "position": 180.0, "age_days": 890, "condition": SpliceCondition.CRITICAL, "risk": RiskLevel.CRITICAL, "severity": 0.91, "trajectory": "critical"},
            {"name": "Splice-203", "position": 280.0, "age_days": 140, "condition": SpliceCondition.GOOD,    "risk": RiskLevel.LOW,      "severity": 0.03, "trajectory": "stable"},
        ],
    },
    {
        "belt_id": "BELT-04",
        "name": "Decline Transfer Line",
        "length_m": 680.0,
        "speed_mps": 3.8,
        "splices": [
            {"name": "Splice-301", "position": 90.0,  "age_days": 340, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW,  "severity": 0.06, "trajectory": "stable"},
            {"name": "Splice-302", "position": 260.0, "age_days": 690, "condition": SpliceCondition.POOR, "risk": RiskLevel.HIGH, "severity": 0.74, "trajectory": "fast_degrade"},
            {"name": "Splice-303", "position": 440.0, "age_days": 410, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW,  "severity": 0.08, "trajectory": "repaired"},
            {"name": "Splice-304", "position": 590.0, "age_days": 110, "condition": SpliceCondition.GOOD, "risk": RiskLevel.LOW,  "severity": 0.02, "trajectory": "stable"},
        ],
    },
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def compute_severity(trajectory: str, progression: float, final_severity: float, rng: random.Random) -> tuple[float, SpliceCondition]:
    """Return (severity, condition) for a trajectory at time progression [0..1]."""
    noise = rng.uniform(-0.020, 0.020)

    if trajectory == "stable":
        sev = final_severity + noise * 0.5
        cond = SpliceCondition.GOOD

    elif trajectory == "slow_degrade":
        sev = 0.05 + progression * (final_severity - 0.05) + noise
        cond = SpliceCondition.GOOD if sev < 0.12 else SpliceCondition.FAIR

    elif trajectory == "fast_degrade":
        if progression < 0.25:
            sev = 0.05 + progression * 0.3 + noise;       cond = SpliceCondition.GOOD
        elif progression < 0.45:
            sev = 0.13 + (progression-0.25)*0.6 + noise;  cond = SpliceCondition.FAIR
        elif progression < 0.65:
            sev = 0.25 + (progression-0.45)*0.9 + noise;  cond = SpliceCondition.DEGRADED
        else:
            sev = 0.43 + (progression-0.65)*1.0 + noise;  cond = SpliceCondition.POOR

    elif trajectory == "critical":
        if progression < 0.15:
            sev = 0.04 + progression*0.7 + noise;         cond = SpliceCondition.GOOD
        elif progression < 0.30:
            sev = 0.15 + (progression-0.15)*1.1 + noise;  cond = SpliceCondition.FAIR
        elif progression < 0.50:
            sev = 0.32 + (progression-0.30)*1.3 + noise;  cond = SpliceCondition.DEGRADED
        elif progression < 0.70:
            sev = 0.58 + (progression-0.50)*1.3 + noise;  cond = SpliceCondition.POOR
        else:
            sev = 0.84 + (progression-0.70)*0.5 + noise;  cond = SpliceCondition.CRITICAL

    elif trajectory == "repaired":
        if progression < 0.45:
            sev = 0.03 + progression*0.55 + noise
            cond = SpliceCondition.GOOD if sev < 0.13 else SpliceCondition.FAIR
        elif progression < 0.58:
            sev = 0.25 + rng.uniform(-0.05, 0.10)  # intervention window
            cond = SpliceCondition.FAIR
        else:
            sev = 0.03 + (1.0-progression)*0.08 + abs(noise)
            cond = SpliceCondition.GOOD
    else:
        sev = final_severity + noise
        cond = SpliceCondition.GOOD

    return (max(0.01, min(0.99, sev)), cond)


def to_risk(sev: float) -> RiskLevel:
    if sev >= 0.80: return RiskLevel.CRITICAL
    if sev >= 0.50: return RiskLevel.HIGH
    if sev >= 0.20: return RiskLevel.MODERATE
    return RiskLevel.LOW


def to_alert_severity(sev: float) -> AlertSeverity | None:
    if sev >= 0.80: return AlertSeverity.CRITICAL
    if sev >= 0.55: return AlertSeverity.HIGH
    if sev >= 0.30: return AlertSeverity.WARNING
    return None


# ─── Clear ────────────────────────────────────────────────────────────────────

async def clear_database(session: AsyncSession):
    logger.info("Clearing existing tables...")
    for model in [
        Alert, ConditionHistory, ATCEResult, DIVEEvent,
        FusionResult, MechanicalEvent, ConductiveEvent,
        ThermalEvent, VisionEvent, SensorMeasurement,
        Inspection, Splice, SystemEvent,
    ]:
        await session.execute(delete(model))
    await session.commit()
    logger.info("Database cleared.")


# ─── Main ────────────────────────────────────────────────────────────────────

async def seed_database(reset: bool = True):
    rng = random.Random(42)
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        if reset:
            await clear_database(session)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        HISTORY_DAYS = 365
        history_start = now - timedelta(days=HISTORY_DAYS)

        # ── Splices ──────────────────────────────────────────────────────────
        logger.info("Creating splices...")
        created_splices: list[tuple[Splice, dict]] = []
        for belt_cfg in CONVEYOR_BELTS:
            for s_cfg in belt_cfg["splices"]:
                installed_dt = now - timedelta(days=s_cfg["age_days"])
                splice = Splice(
                    name=s_cfg["name"],
                    belt_id=belt_cfg["belt_id"],
                    position=s_cfg["position"],
                    installed_date=installed_dt,
                    condition=s_cfg["condition"],
                    severity=round(s_cfg["severity"], 4),
                    confidence=round(rng.uniform(0.88, 0.97), 4),
                    risk_level=s_cfg["risk"],
                    created_at=installed_dt,
                    updated_at=now,
                )
                session.add(splice)
                created_splices.append((splice, s_cfg))
        await session.flush()
        logger.info("Created %d splices.", len(created_splices))

        # ── System boot + monthly maintenance events ─────────────────────────
        session.add(SystemEvent(
            timestamp=history_start - timedelta(hours=3), event_type="SYSTEM_BOOT",
            module="CORE", message="SpliceTracker v2.4.1 initialized — 4 assets, 16 splices online",
            severity=SystemEventSeverity.INFO,
            details_json=json.dumps({"firmware": "2.4.1", "belts": 4, "splices": 16}),
        ))
        for mo in range(12):
            mdt = history_start + timedelta(days=30*mo + rng.randint(1,5), hours=rng.randint(2,5))
            session.add(SystemEvent(
                timestamp=mdt, event_type="MAINTENANCE_WINDOW", module="SCHEDULER",
                message=f"Scheduled maintenance M{mo+1:02d} completed across all belt assets",
                severity=SystemEventSeverity.INFO,
                details_json=json.dumps({"month": mo+1, "belts": ["BELT-01","BELT-02","BELT-03","BELT-04"]}),
            ))

        # ── Dense inspection loop: 3/day × 16 splices × 365 days ───────────
        HOUR_SLOTS = [6, 14, 22]
        total_insp = 0; total_meas = 0
        alert_count = 0; dive_count = 0; atce_count = 0; cond_hist_count = 0

        sev_history: dict[int, list[float]] = {}
        last_alert_day: dict[int, int] = {}
        latest_dive_id: dict[int, int] = {}
        BATCH = 300  # flush interval

        for day in range(HISTORY_DAYS):
            prog = day / max(1, HISTORY_DAYS - 1)
            day_dt = history_start + timedelta(days=day)

            for splice, s_cfg in created_splices:
                sid = splice.id
                if sid not in sev_history:
                    sev_history[sid] = []

                curr_sev, curr_cond = compute_severity(s_cfg["trajectory"], prog, s_cfg["severity"], rng)
                curr_risk = to_risk(curr_sev)
                curr_conf = round(rng.uniform(0.83, 0.97), 4)

                for slot_i, hour in enumerate(HOUR_SLOTS):
                    insp_dt = day_dt.replace(
                        hour=hour, minute=rng.randint(0,59),
                        second=rng.randint(0,59), microsecond=0
                    )

                    # Slight per-slot jitter on severity
                    sev = max(0.01, min(0.99, curr_sev + rng.gauss(0, 0.012)))
                    belt_speed = round(rng.uniform(0.93, 1.07) * 4.2, 2)
                    ambient_c  = round(rng.uniform(19.0, 31.5), 1)

                    # ── Inspection ───────────────────────────────────────────
                    dur_s = round(rng.uniform(9.0, 21.0), 1)
                    insp = Inspection(
                        splice_id=sid,
                        started_at=insp_dt,
                        completed_at=insp_dt + timedelta(seconds=dur_s),
                        status=InspectionStatus.COMPLETED,
                        results_json=json.dumps({
                            "duration_s": dur_s,
                            "belt_speed_mps": belt_speed,
                            "ambient_temp_c": ambient_c,
                            "overall_score": round(sev, 4),
                            "shift": ["morning","afternoon","night"][slot_i],
                        }),
                    )
                    session.add(insp)
                    await session.flush()
                    iid = insp.id
                    total_insp += 1

                    # ── VisionEvent ──────────────────────────────────────────
                    v_score = max(0.0, min(1.0, sev * rng.uniform(0.86, 1.14)))
                    if sev > 0.80: dftype = rng.choice(["splice_separation","transverse_tear","delamination","cord_break"])
                    elif sev > 0.50: dftype = rng.choice(["edge_crack","surface_wear","splice_separation","lateral_shift"])
                    elif sev > 0.20: dftype = rng.choice(["surface_wear","minor_abrasion","cover_bulge"])
                    else: dftype = "normal"

                    session.add(VisionEvent(
                        inspection_id=iid, splice_id=sid, timestamp=insp_dt,
                        frame_path=f"/frames/{splice.name.lower()}_{insp_dt.strftime('%Y%m%d_%H%M%S')}.jpg",
                        roi_json=json.dumps({"x": rng.randint(180,220),"y":rng.randint(90,140),
                                             "width":rng.randint(580,720),"height":rng.randint(220,310)}),
                        defect_type=dftype,
                        defect_confidence=round(rng.uniform(0.77, 0.97), 4) if dftype!="normal" else 0.0,
                        bounding_region_json=json.dumps({
                            "boxes": [{"x":rng.randint(200,400),"y":rng.randint(100,200),
                                       "w":rng.randint(50,200),"h":rng.randint(30,80),
                                       "score":round(v_score,3)}] if dftype!="normal" else [],
                        }),
                        optical_flow_json=json.dumps({
                            "mean_displacement_px": round(rng.uniform(0.1, 2.0+sev*8), 3),
                            "max_deformation_mm":   round(rng.uniform(0.05, 1.0+sev*5), 3),
                            "flow_vectors": [round(rng.gauss(0, 0.3+sev*0.8), 3) for _ in range(8)],
                        }),
                        deformation_json=json.dumps({
                            "strain_pct": round(sev*12.0*rng.uniform(0.8,1.2), 3),
                            "warp_index": round(sev*rng.uniform(0.5,1.5), 4),
                        }),
                        anomaly_score=round(v_score, 4),
                    ))

                    # ── ThermalEvent ─────────────────────────────────────────
                    base_t  = 34.0 + sev * 28.0
                    hot_t   = base_t + rng.uniform(0, sev * 40.0)
                    delta_t = round(hot_t - base_t, 2)
                    t_score = round(min(1.0, sev * rng.uniform(0.85, 1.15)), 4)
                    session.add(ThermalEvent(
                        inspection_id=iid, splice_id=sid, timestamp=insp_dt,
                        temperature=round(hot_t, 2),
                        baseline_temperature=round(base_t + rng.uniform(-1.5, 1.5), 2),
                        delta_temperature=delta_t,
                        rate_of_change=round(delta_t / dur_s, 4),
                        thermal_anomaly_score=t_score,
                        hotspot_location_json=json.dumps({
                            "x_pct": round(rng.uniform(20,80), 1),
                            "y_pct": round(rng.uniform(20,80), 1),
                            "radius_mm": round(rng.uniform(5, 25+sev*40), 1),
                            "temp_c": round(hot_t, 2),
                        }),
                    ))

                    # ── ConductiveEvent ──────────────────────────────────────
                    continuity = sev < 0.85 or rng.random() > 0.55
                    c_score = round(min(1.0, (1.0-int(continuity))*0.75 + sev*0.25), 4)
                    session.add(ConductiveEvent(
                        inspection_id=iid, splice_id=sid, timestamp=insp_dt,
                        continuity=continuity,
                        previous_state=True,
                        transition=not continuity,
                        duration_ms=round(rng.uniform(18.0, 32.0), 2),
                        anomaly_score=c_score,
                    ))

                    # ── MechanicalEvent ──────────────────────────────────────
                    base_rms = 0.4 + sev * 4.2
                    m_score  = round(min(1.0, sev * rng.uniform(0.80, 1.20)), 4)
                    session.add(MechanicalEvent(
                        inspection_id=iid, splice_id=sid, timestamp=insp_dt,
                        rms=round(base_rms * rng.uniform(0.85, 1.15), 4),
                        peak=round(base_rms * rng.uniform(2.0, 3.5), 4),
                        variance=round((base_rms * 0.1)**2, 6),
                        frequency_features_json=json.dumps({
                            "dominant_hz": round(rng.choice([12.5,25.0,33.3,50.0,66.7,100.0])+rng.gauss(0,0.5), 2),
                            "kurtosis": round(3.0 + sev*6.0 + rng.gauss(0, 0.3), 2),
                            "amplitudes": [round(base_rms*rng.uniform(0.1,1.0),3) for _ in range(6)],
                        }),
                        anomaly_score=m_score,
                    ))

                    # ── SensorMeasurements ───────────────────────────────────
                    for stype, score in [(SensorType.VISION,v_score),(SensorType.THERMAL,t_score),
                                         (SensorType.CONDUCTIVE,c_score),(SensorType.MECHANICAL,m_score)]:
                        session.add(SensorMeasurement(
                            inspection_id=iid, splice_id=sid, sensor_type=stype,
                            timestamp=insp_dt,
                            value_json=json.dumps({"score": round(score,4), "sev": round(sev,4)}),
                            anomaly_score=round(score, 4),
                            confidence=curr_conf,
                            raw_value_json=json.dumps({"raw": round(score*rng.uniform(0.98,1.02),5)}),
                        ))
                    total_meas += 4

                    # ── FusionResult ─────────────────────────────────────────
                    fused = round(max(0.0, min(1.0,
                        v_score*0.35 + t_score*0.25 + c_score*0.20 + m_score*0.20 + rng.gauss(0,0.008)
                    )), 4)
                    if fused >= 0.80: fstat = FusionStatus.CONFLICT
                    elif fused >= 0.50: fstat = FusionStatus.PARTIAL
                    else: fstat = FusionStatus.COMPLETE

                    conf_sensors = sum(1 for s in [v_score,t_score,c_score,m_score] if s >= 0.30)
                    cont_sensors = sum(1 for s in [v_score,t_score,c_score,m_score] if s < 0.20)
                    fusion = FusionResult(
                        inspection_id=iid, splice_id=sid, timestamp=insp_dt,
                        vision_score=round(v_score,4), thermal_score=round(t_score,4),
                        mechanical_score=round(m_score,4), conductive_score=round(c_score,4),
                        supporting_sensors=conf_sensors, contradicting_sensors=cont_sensors,
                        overall_confidence=curr_conf, fusion_status=fstat,
                        evidence_json=json.dumps({
                            "fused": fused, "weights": {"v":0.35,"t":0.25,"c":0.20,"m":0.20},
                            "conflict": abs(v_score-m_score) > 0.35,
                        }),
                    )
                    session.add(fusion)

                    # ── Rolling severity history ──────────────────────────────
                    sev_history[sid].append(sev)
                    if len(sev_history[sid]) > 42:
                        sev_history[sid].pop(0)

                    # ── DIVE Events: every 7 days, slot 0 ────────────────────
                    current_dive_id = None
                    if slot_i == 0 and day % 7 == 0 and len(sev_history[sid]) >= 3:
                        await session.flush()
                        window = sev_history[sid]
                        avg_sev = sum(window)/len(window)
                        trend   = window[-1] - window[0]
                        if avg_sev > 0.70:
                            etype  = DIVEEventType.ESCALATION; estat = DIVEStatus.CONFIRMED
                        elif avg_sev > 0.35 or trend > 0.15:
                            etype  = DIVEEventType.VALIDATION;  estat = DIVEStatus.ACTIVE
                        else:
                            etype  = DIVEEventType.DETECTION;   estat = DIVEStatus.ACTIVE

                        dive_ev = DIVEEvent(
                            fusion_result_id=fusion.id,
                            splice_id=sid,
                            start_time=insp_dt - timedelta(days=7),
                            end_time=insp_dt,
                            event_type=etype,
                            status=estat,
                            confidence=round(rng.uniform(0.80, 0.97), 4),
                            persistence_count=len(window),
                            evidence_json=json.dumps({
                                "window_days": 7,
                                "peak_sev": round(max(window),4),
                                "avg_sev": round(avg_sev,4),
                                "trend": round(trend,4),
                                "history": [round(v,3) for v in window[-7:]],
                            }),
                            supporting_sensors_json=json.dumps(["vision","thermal","mechanical"]),
                        )
                        session.add(dive_ev)
                        await session.flush()
                        current_dive_id = dive_ev.id
                        latest_dive_id[sid] = dive_ev.id
                        dive_count += 1

                    # ── ATCE Results: every 14 days, slot 0 ─────────────────
                    target_dive_id = current_dive_id or latest_dive_id.get(sid)
                    if slot_i == 0 and day % 14 == 0 and day > 0 and len(sev_history[sid]) >= 5 and target_dive_id:
                        window  = sev_history[sid]
                        delta   = window[-1] - window[0]
                        avg_sev = sum(window)/len(window)

                        if delta > 0.30:   atrend = ATCETrend.RAPID_DEGRADATION; aconf = round(rng.uniform(0.88,0.97),4)
                        elif delta > 0.12: atrend = ATCETrend.DEGRADING;          aconf = round(rng.uniform(0.82,0.93),4)
                        elif delta < -0.10:atrend = ATCETrend.IMPROVING;          aconf = round(rng.uniform(0.80,0.92),4)
                        else:              atrend = ATCETrend.STABLE;              aconf = round(rng.uniform(0.88,0.97),4)

                        session.add(ATCEResult(
                            dive_event_id=target_dive_id,
                            splice_id=sid, timestamp=insp_dt,
                            previous_state=curr_cond.value,
                            current_state=curr_cond.value,
                            trend=atrend,
                            persistence=len(window),
                            recurrence=sum(1 for v in window if v > 0.30) > 1,
                            history_json=json.dumps({
                                "window": len(window),
                                "delta": round(delta,4),
                                "avg": round(avg_sev,4),
                                "severity_series": [round(v,3) for v in window[-14:]],
                            }),
                        ))
                        atce_count += 1

                    # ── Update splice final state on last day ─────────────────
                    if day == HISTORY_DAYS - 1 and slot_i == len(HOUR_SLOTS) - 1:
                        splice.condition = curr_cond
                        splice.severity = round(sev, 4)
                        splice.confidence = curr_conf
                        splice.risk_level = curr_risk
                        splice.updated_at = insp_dt

                    # ── Condition History: every 3rd day, slot 0 ─────────────
                    if slot_i == 0 and day % 3 == 0:
                        session.add(ConditionHistory(
                            splice_id=sid, timestamp=insp_dt,
                            condition=curr_cond, severity=round(sev,4),
                            risk_level=curr_risk, confidence=curr_conf,
                            trigger_event_id=iid,
                            notes=f"Day {day} | {curr_cond.value} | sev={sev:.3f} | traj={s_cfg['trajectory']}",
                        ))
                        cond_hist_count += 1

                    # ── Alerts (throttled) ────────────────────────────────────
                    alert_sev = to_alert_severity(sev)
                    cooldown  = {AlertSeverity.CRITICAL:1, AlertSeverity.HIGH:3, AlertSeverity.WARNING:7}.get(alert_sev, 999)
                    if alert_sev and slot_i == 0 and (day - last_alert_day.get(sid, -999)) >= cooldown:
                        last_alert_day[sid] = day
                        resolved_after = rng.randint(1, 5) if alert_sev != AlertSeverity.CRITICAL else rng.randint(3, 12)
                        is_resolved = rng.random() > 0.15
                        resolved_at = insp_dt + timedelta(days=resolved_after) if is_resolved else None

                        reasons = {
                            AlertSeverity.WARNING:  f"Anomaly score {sev:.3f} exceeded WARNING threshold on {splice.name}",
                            AlertSeverity.HIGH:     f"Fused anomaly {sev:.3f} exceeds HIGH threshold — multi-sensor confirmed on {splice.name}",
                            AlertSeverity.CRITICAL: f"CRITICAL degradation {sev:.3f} on {splice.name} — immediate action required",
                        }
                        actions = {
                            AlertSeverity.WARNING:  "Schedule inspection within 7 days. Monitor thermal and vibration trends closely.",
                            AlertSeverity.HIGH:     "Expedite maintenance. Reduce belt loading. Notify maintenance supervisor immediately.",
                            AlertSeverity.CRITICAL: "IMMEDIATE SHUTDOWN RECOMMENDED. Emergency maintenance required. Do not operate.",
                        }
                        session.add(Alert(
                            splice_id=sid, timestamp=insp_dt, severity=alert_sev,
                            defect_type=dftype,
                            confidence=curr_conf,
                            risk_score=round(sev, 4),
                            reason=reasons[alert_sev],
                            recommended_action=actions[alert_sev],
                            status=AlertStatus.RESOLVED if is_resolved else AlertStatus.ACTIVE,
                            acknowledged_at=resolved_at,
                            acknowledged_by="AUTO-SYSTEM" if is_resolved else None,
                            location=f"{splice.belt_id}:{splice.position:.0f}m",
                        ))
                        alert_count += 1

                    # ── Occasional system events ──────────────────────────────
                    if rng.random() < 0.003:
                        evt_templates = [
                            ("EDGE_INFERENCE", "INFO",  f"Edge AI inference complete — {splice.belt_id}"),
                            ("DAQ_SYNC",       "INFO",  f"DAQ checkpoint sync — {splice.belt_id} nominal"),
                            ("CALIBRATION",    "INFO",  f"Position sensor auto-calibration on {splice.name}"),
                            ("NETWORK_RETRY",  "WARN",  f"Cloud gateway timeout — data queued locally"),
                            ("SENSOR_FAULT",   "WARN",  f"Transient fault on {splice.name} — auto-recovered"),
                        ]
                        etype, elevel, emsg = rng.choice(evt_templates)
                        session.add(SystemEvent(
                            timestamp=insp_dt, event_type=etype,
                            module=f"EDGE-{splice.belt_id}",
                            message=emsg,
                            severity=SystemEventSeverity.WARNING if elevel=="WARN" else SystemEventSeverity.INFO,
                            details_json=json.dumps({"splice": splice.name, "sev": round(sev,4)}),
                        ))

                    # Batch flush
                    if total_insp % BATCH == 0:
                        await session.flush()
                        logger.info(
                            "Day %3d/%d | inspections=%6d | meas=%6d | alerts=%4d | DIVE=%4d | ATCE=%4d",
                            day, HISTORY_DAYS, total_insp, total_meas, alert_count, dive_count, atce_count,
                        )

        await session.flush()
        await session.commit()

        logger.info("=" * 65)
        logger.info("SEEDING COMPLETE:")
        logger.info("  Splices:             %d", len(created_splices))
        logger.info("  Inspections:         %d", total_insp)
        logger.info("  Sensor Measurements: %d", total_meas)
        logger.info("  Alerts:              %d", alert_count)
        logger.info("  DIVE Events:         %d", dive_count)
        logger.info("  ATCE Results:        %d", atce_count)
        logger.info("  Condition History:   %d", cond_hist_count)
        logger.info("=" * 65)


if __name__ == "__main__":
    asyncio.run(seed_database(reset=True))
