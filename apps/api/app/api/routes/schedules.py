from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.schedule import ScheduleSlotCreate, ScheduleSlotRead
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleSlotRead, status_code=201)
async def create_slot(
    data: ScheduleSlotCreate,
    session: AsyncSession = Depends(get_session),
) -> ScheduleSlotRead:
    svc = ScheduleService(session)
    slot = await svc.create_slot(data)
    return ScheduleSlotRead.model_validate(slot)


@router.get("", response_model=list[ScheduleSlotRead])
async def list_slots(
    professional_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[ScheduleSlotRead]:
    svc = ScheduleService(session)
    slots = await svc.list_slots(
        professional_id=professional_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return [ScheduleSlotRead.model_validate(s) for s in slots]


@router.post("/{slot_id}/book", response_model=ScheduleSlotRead)
async def book_slot(
    slot_id: uuid.UUID,
    patient_id: uuid.UUID = Query(...),
    source: str = Query("manual"),
    session: AsyncSession = Depends(get_session),
) -> ScheduleSlotRead:
    svc = ScheduleService(session)
    slot = await svc.book_slot(slot_id, patient_id, source)
    if not slot:
        raise HTTPException(status_code=400, detail="Slot not available")
    return ScheduleSlotRead.model_validate(slot)


@router.post("/{slot_id}/cancel", response_model=ScheduleSlotRead)
async def cancel_slot(
    slot_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ScheduleSlotRead:
    svc = ScheduleService(session)
    slot = await svc.cancel_slot(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return ScheduleSlotRead.model_validate(slot)
