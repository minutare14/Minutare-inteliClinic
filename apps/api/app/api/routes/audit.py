from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventRead]:
    repo = AuditRepository(session)
    events = await repo.list_events(limit=limit, offset=offset)
    return [AuditEventRead.model_validate(e) for e in events]
