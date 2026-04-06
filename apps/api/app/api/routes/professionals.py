from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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


@router.get("", response_model=list[ProfessionalRead])
async def list_professionals(
    specialty: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[ProfessionalRead]:
    repo = ProfessionalRepository(session)
    profs = await repo.list_active(specialty=specialty)
    return [ProfessionalRead.model_validate(p) for p in profs]
