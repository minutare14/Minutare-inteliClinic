from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.professional_repository import ProfessionalRepository

router = APIRouter(prefix="/professionals", tags=["professionals"])


class ProfessionalRead(BaseModel):
    id: uuid.UUID
    full_name: str
    specialty: str
    crm: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfessionalCreate(BaseModel):
    full_name: str
    specialty: str
    crm: str


class ProfessionalUpdate(BaseModel):
    full_name: str | None = None
    specialty: str | None = None
    active: bool | None = None


@router.get("", response_model=list[ProfessionalRead])
async def list_professionals(
    specialty: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[ProfessionalRead]:
    repo = ProfessionalRepository(session)
    profs = await repo.list_active(specialty=specialty)
    return [ProfessionalRead.model_validate(p) for p in profs]


@router.get("/all", response_model=list[ProfessionalRead])
async def list_all_professionals(
    specialty: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[ProfessionalRead]:
    repo = ProfessionalRepository(session)
    profs = await repo.list_all(specialty=specialty)
    return [ProfessionalRead.model_validate(p) for p in profs]


@router.post("", response_model=ProfessionalRead, status_code=201)
async def create_professional(
    body: ProfessionalCreate,
    session: AsyncSession = Depends(get_session),
) -> ProfessionalRead:
    repo = ProfessionalRepository(session)
    try:
        prof = await repo.create(
            full_name=body.full_name,
            specialty=body.specialty,
            crm=body.crm,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="CRM already exists.")
    return ProfessionalRead.model_validate(prof)


@router.patch("/{professional_id}", response_model=ProfessionalRead)
async def update_professional(
    professional_id: uuid.UUID,
    body: ProfessionalUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProfessionalRead:
    repo = ProfessionalRepository(session)
    prof = await repo.update(
        professional_id,
        full_name=body.full_name,
        specialty=body.specialty,
        active=body.active,
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found.")
    return ProfessionalRead.model_validate(prof)


@router.delete("/{professional_id}", response_model=ProfessionalRead)
async def deactivate_professional(
    professional_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProfessionalRead:
    repo = ProfessionalRepository(session)
    prof = await repo.deactivate(professional_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found.")
    return ProfessionalRead.model_validate(prof)
