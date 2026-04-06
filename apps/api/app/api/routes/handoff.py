from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.conversation import HandoffCreate, HandoffRead
from app.services.handoff_service import HandoffService
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/handoff", tags=["handoff"])


class HandoffStatusUpdate(BaseModel):
    status: str


@router.get("", response_model=list[HandoffRead])
async def list_handoffs(
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[HandoffRead]:
    svc = ConversationService(session)
    handoffs = await svc.list_handoffs(status=status, limit=limit, offset=offset)
    return [HandoffRead.model_validate(h) for h in handoffs]


@router.post("", response_model=HandoffRead, status_code=201)
async def create_handoff(
    data: HandoffCreate,
    session: AsyncSession = Depends(get_session),
) -> HandoffRead:
    svc = HandoffService(session)
    handoff = await svc.create(
        conversation_id=data.conversation_id,
        reason=data.reason,
        priority=data.priority,
        context_summary=data.context_summary,
    )
    return HandoffRead.model_validate(handoff)


@router.patch("/{handoff_id}", response_model=HandoffRead)
async def update_handoff_status(
    handoff_id: uuid.UUID,
    data: HandoffStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> HandoffRead:
    svc = ConversationService(session)
    handoff = await svc.update_handoff_status(handoff_id, data.status)
    if not handoff:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return HandoffRead.model_validate(handoff)
