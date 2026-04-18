from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_session
from app.models.auth import User
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead])
async def list_patients(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[PatientRead]:
    svc = PatientService(session)
    patients = await svc.list_patients(limit=limit, offset=offset)
    return [PatientRead.model_validate(p) for p in patients]


@router.post("", response_model=PatientRead, status_code=201)
async def create_patient(
    data: PatientCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> PatientRead:
    svc = PatientService(session)
    patient = await svc.create_patient(data)
    return PatientRead.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> PatientRead:
    svc = PatientService(session)
    patient = await svc.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PatientRead.model_validate(patient)


@router.get("/by-telegram/{telegram_user_id}", response_model=PatientRead)
async def get_patient_by_telegram(
    telegram_user_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> PatientRead:
    svc = PatientService(session)
    patient = await svc.get_by_telegram(telegram_user_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PatientRead.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> PatientRead:
    svc = PatientService(session)
    patient = await svc.update_patient(patient_id, data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PatientRead.model_validate(patient)
