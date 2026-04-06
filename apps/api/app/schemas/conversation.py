from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ConversationRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None
    channel: str
    status: str
    current_intent: str | None
    confidence_score: float | None
    human_assignee: str | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HandoffCreate(BaseModel):
    conversation_id: uuid.UUID
    reason: str
    priority: str = "normal"
    context_summary: str | None = None


class HandoffRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    reason: str
    priority: str
    context_summary: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
