"""Inspection listing and detail endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.schemas import (
    ATCEResultResponse,
    ConductiveEventResponse,
    DIVEEventResponse,
    FusionResultResponse,
    InspectionDetailResponse,
    InspectionResponse,
    MechanicalEventResponse,
    SensorDataResponse,
    ThermalEventResponse,
    VisionEventResponse,
)
from ..database.database import async_session
from ..database.repositories import EventRepository, InspectionRepository

router = APIRouter(prefix="/api/inspections", tags=["inspections"])


@router.get("", response_model=list[InspectionResponse])
async def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    splice_id: Optional[int] = None,
    session: AsyncSession = Depends(async_session),
):
    """List inspections, optionally filtered by splice_id."""
    repo = InspectionRepository(session)
    if splice_id is not None:
        inspections = await repo.get_by_splice(splice_id, limit=limit)
    else:
        inspections = await repo.get_all(skip=skip, limit=limit)
    return [InspectionResponse.model_validate(i) for i in inspections]


@router.get("/{inspection_id}", response_model=InspectionDetailResponse)
async def get_inspection_detail(
    inspection_id: int,
    session: AsyncSession = Depends(async_session),
):
    """Get full inspection detail including all sensor data, fusion, DIVE, and ATCE results."""
    insp_repo = InspectionRepository(session)
    inspection = await insp_repo.get_by_id_with_details(inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Collect DIVE events and ATCE results from the nested fusion results
    dive_events = []
    atce_results = []
    for fusion in inspection.fusion_results:
        for dive in fusion.dive_events:
            dive_events.append(dive)
            for atce in dive.atce_results:
                atce_results.append(atce)

    return InspectionDetailResponse(
        inspection=InspectionResponse.model_validate(inspection),
        sensor_data=[SensorDataResponse.model_validate(s) for s in inspection.sensor_measurements],
        vision_events=[VisionEventResponse.model_validate(v) for v in inspection.vision_events],
        thermal_events=[ThermalEventResponse.model_validate(t) for t in inspection.thermal_events],
        conductive_events=[ConductiveEventResponse.model_validate(c) for c in inspection.conductive_events],
        mechanical_events=[MechanicalEventResponse.model_validate(m) for m in inspection.mechanical_events],
        fusion_results=[FusionResultResponse.model_validate(f) for f in inspection.fusion_results],
        dive_events=[DIVEEventResponse.model_validate(d) for d in dive_events],
        atce_results=[ATCEResultResponse.model_validate(a) for a in atce_results],
    )
