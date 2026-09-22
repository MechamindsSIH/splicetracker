"""System status and health endpoints."""

import os
import time
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventBus, EventType
from ..core.schemas import (
    ComponentStatus,
    PipelineStageStatus,
    PipelineStatusResponse,
    SystemEventResponse,
    SystemHealthResponse,
    SystemStatusResponse,
)
from ..database.database import async_session
from ..database.models import AlertStatus, InspectionStatus
from ..database.repositories import (
    AlertRepository,
    InspectionRepository,
    SpliceRepository,
    SystemEventRepository,
)
from .websocket import ConnectionManager

router = APIRouter(prefix="/api", tags=["system"])

_start_time = time.time()


def _get_memory_usage_mb() -> float:
    """Return current process RSS in MB (best-effort)."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024.0  # Linux reports in KB
    except Exception:
        return 0.0


def _get_cpu_percent() -> float:
    """Return a rough CPU time percentage (best-effort)."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cpu_time = usage.ru_utime + usage.ru_stime
        wall = time.time() - _start_time
        if wall > 0:
            return round((cpu_time / wall) * 100, 2)
    except Exception:
        pass
    return 0.0


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    session: AsyncSession = Depends(async_session),
):
    """Return full system status with all component states."""
    from ..config import get_settings
    settings = get_settings()

    splice_repo = SpliceRepository(session)
    alert_repo = AlertRepository(session)
    insp_repo = InspectionRepository(session)

    active_splices = await splice_repo.count()
    active_alerts = await alert_repo.count(status=AlertStatus.ACTIVE)
    inspection_count = await insp_repo.count()
    latest = await insp_repo.get_latest()

    bus = EventBus.get_instance()
    ws_mgr = ConnectionManager.get_instance()

    components = [
        ComponentStatus(
            name="database",
            status="online",
            details={"url": settings.DATABASE_URL},
        ),
        ComponentStatus(
            name="event_bus",
            status="online",
            details={"subscribers": bus.get_subscriber_count()},
        ),
        ComponentStatus(
            name="websocket",
            status="online",
            details={"connections": ws_mgr.connection_count},
        ),
        ComponentStatus(
            name="vision_sensor",
            status="online" if settings.SIMULATION_MODE else "offline",
            details={"simulation": settings.SIMULATION_MODE},
        ),
        ComponentStatus(
            name="thermal_sensor",
            status="online" if settings.THERMAL_ENABLED else "disabled",
        ),
        ComponentStatus(
            name="conductive_sensor",
            status="online" if settings.CONDUCTIVE_ENABLED else "disabled",
        ),
        ComponentStatus(
            name="mechanical_sensor",
            status="online" if settings.MECHANICAL_ENABLED else "disabled",
        ),
    ]

    return SystemStatusResponse(
        status="healthy",
        uptime_seconds=round(time.time() - _start_time, 2),
        simulation_mode=settings.SIMULATION_MODE,
        components=components,
        active_splices=active_splices,
        active_alerts=active_alerts,
        inspection_count=inspection_count,
        last_inspection_at=latest.started_at if latest else None,
    )


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    session: AsyncSession = Depends(async_session),
):
    """Return detailed system health including DB, event bus, memory, CPU."""
    bus = EventBus.get_instance()
    ws_mgr = ConnectionManager.get_instance()

    # Quick DB check
    db_status = "healthy"
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return SystemHealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        event_bus="online",
        websocket_connections=ws_mgr.connection_count,
        memory_usage_mb=round(_get_memory_usage_mb(), 2),
        cpu_percent=_get_cpu_percent(),
        uptime_seconds=round(time.time() - _start_time, 2),
        components={
            "database": db_status,
            "event_bus": "online",
            "websocket": "online",
        },
    )


@router.get("/events", response_model=list[SystemEventResponse])
async def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    event_type: str | None = None,
    session: AsyncSession = Depends(async_session),
):
    """List recent system events."""
    repo = SystemEventRepository(session)
    events = await repo.get_all(skip=skip, limit=limit, event_type=event_type)
    return [SystemEventResponse.model_validate(e) for e in events]


@router.get("/events/{event_id}", response_model=SystemEventResponse)
async def get_event_detail(
    event_id: int,
    session: AsyncSession = Depends(async_session),
):
    """Get a single system event by ID (event inspector)."""
    repo = SystemEventRepository(session)
    event = await repo.get_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="System event not found")
    return SystemEventResponse.model_validate(event)


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status():
    """Return the data pipeline visualization status showing each processing stage."""
    bus = EventBus.get_instance()
    recent = bus.get_recent_events(limit=100)

    # Count events per type as a proxy for pipeline stage activity
    type_counts: Dict[str, int] = {}
    for evt in recent:
        et = evt.get("event_type", "UNKNOWN")
        type_counts[et] = type_counts.get(et, 0) + 1

    now = datetime.utcnow()

    stages = [
        PipelineStageStatus(
            name="Sensor Ingestion",
            status="active" if type_counts.get("SENSOR_UPDATE", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("SENSOR_UPDATE") else None,
            items_processed=type_counts.get("SENSOR_UPDATE", 0),
        ),
        PipelineStageStatus(
            name="Vision Processing",
            status="active" if type_counts.get("CAMERA_UPDATE", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("CAMERA_UPDATE") else None,
            items_processed=type_counts.get("CAMERA_UPDATE", 0),
        ),
        PipelineStageStatus(
            name="Sensor Fusion",
            status="active" if type_counts.get("FUSION_UPDATED", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("FUSION_UPDATED") else None,
            items_processed=type_counts.get("FUSION_UPDATED", 0),
        ),
        PipelineStageStatus(
            name="DIVE Analysis",
            status="active" if type_counts.get("DEFECT_DETECTED", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("DEFECT_DETECTED") else None,
            items_processed=type_counts.get("DEFECT_DETECTED", 0),
        ),
        PipelineStageStatus(
            name="Condition Assessment",
            status="active" if type_counts.get("CONDITION_UPDATED", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("CONDITION_UPDATED") else None,
            items_processed=type_counts.get("CONDITION_UPDATED", 0),
        ),
        PipelineStageStatus(
            name="Alert Generation",
            status="active" if type_counts.get("ALERT_CREATED", 0) > 0 else "idle",
            last_processed_at=now if type_counts.get("ALERT_CREATED") else None,
            items_processed=type_counts.get("ALERT_CREATED", 0),
        ),
    ]

    total = sum(s.items_processed for s in stages)
    uptime = time.time() - _start_time
    throughput = total / uptime if uptime > 0 else 0.0

    any_active = any(s.status == "active" for s in stages)
    any_error = any(s.status == "error" for s in stages)

    overall = "active" if any_active else ("error" if any_error else "idle")

    return PipelineStatusResponse(
        stages=stages,
        overall_status=overall,
        throughput_per_second=round(throughput, 4),
    )


@router.post("/system/seed")
async def trigger_seed(reset: bool = True):
    """Seed the database with realistic industrial multi-asset data."""
    from ..database.seed_database import seed_database
    await seed_database(reset=reset)
    return {"status": "success", "message": "Database seeded with multi-asset industrial dataset"}
