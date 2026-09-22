"""Aggregated analytics endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.schemas import AnalyticsResponse, RiskResponse, TimelineEntry
from ..database.database import async_session
from ..database.models import AlertStatus
from ..database.repositories import (
    AlertRepository,
    EventRepository,
    InspectionRepository,
    SpliceRepository,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    session: AsyncSession = Depends(async_session),
):
    """Return aggregated analytics: inspection count, anomaly count, alert count,
    risk distribution, condition trends, and per-splice risk summaries."""
    splice_repo = SpliceRepository(session)
    insp_repo = InspectionRepository(session)
    alert_repo = AlertRepository(session)
    event_repo = EventRepository(session)

    total_splices = await splice_repo.count()
    total_inspections = await insp_repo.count()
    total_anomalies = await event_repo.count_anomalies(threshold=0.5)
    total_alerts = await alert_repo.count()
    active_alerts = await alert_repo.count(status=AlertStatus.ACTIVE)
    risk_dist = await splice_repo.get_risk_distribution()
    cond_dist = await splice_repo.get_condition_distribution()

    # Build per-splice risk summaries
    all_splices = await splice_repo.get_all(limit=500)
    splice_risks = []
    for s in all_splices:
        factors = []
        if s.severity > 0.7:
            factors.append("high_severity")
        if s.confidence < 0.5:
            factors.append("low_confidence")
        if s.condition and s.condition.value in ("POOR", "CRITICAL"):
            factors.append("poor_condition")
        splice_risks.append(
            RiskResponse(
                splice_id=s.id,
                splice_name=s.name,
                risk_level=s.risk_level.value if s.risk_level else "LOW",
                risk_score=s.severity,
                condition=s.condition.value if s.condition else "UNKNOWN",
                contributing_factors=factors,
            )
        )

    # Build recent timeline from alerts
    recent_alerts = await alert_repo.get_all(limit=20)
    timeline = [
        TimelineEntry(
            timestamp=a.timestamp,
            event_type="ALERT",
            description=a.reason or f"{a.severity.value} alert on splice {a.splice_id}",
            severity=a.severity.value if a.severity else None,
            splice_id=a.splice_id,
        )
        for a in recent_alerts
    ]

    return AnalyticsResponse(
        total_splices=total_splices,
        total_inspections=total_inspections,
        total_anomalies=total_anomalies,
        total_alerts=total_alerts,
        active_alerts=active_alerts,
        risk_distribution=risk_dist,
        condition_distribution=cond_dist,
        recent_timeline=timeline,
        splice_risks=splice_risks,
    )
