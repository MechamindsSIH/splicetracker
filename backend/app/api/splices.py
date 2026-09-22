"""Splice CRUD and query endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.schemas import (
    ConditionHistoryResponse,
    SpliceListResponse,
    SpliceResponse,
)
from ..database.database import async_session
from ..database.repositories import ConditionRepository, SpliceRepository

router = APIRouter(prefix="/api/splices", tags=["splices"])


@router.get("", response_model=SpliceListResponse)
async def list_splices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    belt_id: Optional[str] = None,
    condition: Optional[str] = None,
    risk_level: Optional[str] = None,
    session: AsyncSession = Depends(async_session),
):
    """List all splices with current condition, with optional filters."""
    repo = SpliceRepository(session)

    if belt_id:
        splices = await repo.get_by_belt(belt_id)
    elif condition:
        from ..database.models import SpliceCondition
        try:
            cond = SpliceCondition(condition)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid condition: {condition}")
        splices = await repo.get_by_condition(cond)
    elif risk_level:
        from ..database.models import RiskLevel
        try:
            rl = RiskLevel(risk_level)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid risk_level: {risk_level}")
        splices = await repo.get_by_risk_level(rl)
    else:
        splices = await repo.get_all(skip=skip, limit=limit)

    total = await repo.count()
    return SpliceListResponse(
        splices=[SpliceResponse.model_validate(s) for s in splices],
        total=total,
    )


@router.get("/{splice_id}", response_model=SpliceResponse)
async def get_splice(
    splice_id: int,
    session: AsyncSession = Depends(async_session),
):
    """Get a single splice by ID."""
    repo = SpliceRepository(session)
    splice = await repo.get_by_id(splice_id)
    if splice is None:
        raise HTTPException(status_code=404, detail="Splice not found")
    return SpliceResponse.model_validate(splice)


@router.get("/{splice_id}/history", response_model=list[ConditionHistoryResponse])
async def get_splice_history(
    splice_id: int,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(async_session),
):
    """Get condition history for a specific splice."""
    # Verify splice exists
    splice_repo = SpliceRepository(session)
    splice = await splice_repo.get_by_id(splice_id)
    if splice is None:
        raise HTTPException(status_code=404, detail="Splice not found")

    cond_repo = ConditionRepository(session)
    history = await cond_repo.get_by_splice(splice_id, limit=limit)
    return [ConditionHistoryResponse.model_validate(h) for h in history]
