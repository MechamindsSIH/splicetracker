"""Alert listing and acknowledgement endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.schemas import AlertAcknowledgeRequest, AlertResponse
from ..database.database import async_session
from ..database.models import AlertSeverity, AlertStatus
from ..database.repositories import AlertRepository

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    splice_id: Optional[int] = None,
    session: AsyncSession = Depends(async_session),
):
    """List alerts with optional filtering by status, severity, and splice_id."""
    repo = AlertRepository(session)

    status_enum = None
    if status is not None:
        try:
            status_enum = AlertStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    severity_enum = None
    if severity is not None:
        try:
            severity_enum = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    alerts = await repo.get_all(
        skip=skip,
        limit=limit,
        status=status_enum,
        severity=severity_enum,
        splice_id=splice_id,
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    request: AlertAcknowledgeRequest,
    session: AsyncSession = Depends(async_session),
):
    """Acknowledge an active alert."""
    repo = AlertRepository(session)
    alert = await repo.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Alert is not active (current status: {alert.status.value})",
        )

    updated = await repo.acknowledge(alert_id, request.acknowledged_by)
    return AlertResponse.model_validate(updated)
