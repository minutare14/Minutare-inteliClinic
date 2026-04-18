from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_session
from app.models.auth import User
from app.schemas.conversation import ConversationRead, ConversationStatusUpdate, MessageRead
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    status: str | None = Query(None),
    patient_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[ConversationRead]:
    svc = ConversationService(session)
    convs = await svc.list_conversations(
        status=status, patient_id=patient_id, limit=limit, offset=offset
    )
    return [ConversationRead.model_validate(c) for c in convs]


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> ConversationRead:
    svc = ConversationService(session)
    conv = await svc.get_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conv)


@router.patch("/{conversation_id}/status", response_model=ConversationRead)
async def update_conversation_status(
    conversation_id: uuid.UUID,
    data: ConversationStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> ConversationRead:
    svc = ConversationService(session)
    conv = await svc.update_status(conversation_id, data.status)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conv)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[MessageRead]:
    svc = ConversationService(session)
    messages = await svc.get_messages(conversation_id)
    return [MessageRead.model_validate(m) for m in messages]
