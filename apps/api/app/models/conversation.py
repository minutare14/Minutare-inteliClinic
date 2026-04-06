from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ConversationStatus(str, Enum):
    active = "active"
    waiting_input = "waiting_input"
    escalated = "escalated"
    closed = "closed"


class MessageDirection(str, Enum):
    inbound = "inbound"
    outbound = "outbound"


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID | None = Field(default=None, foreign_key="patients.id", index=True)
    channel: str = Field(default="telegram", max_length=32)
    status: str = Field(default=ConversationStatus.active, max_length=20)
    current_intent: str | None = Field(default=None, max_length=64)
    confidence_score: float | None = None
    human_assignee: str | None = Field(default=None, max_length=128)
    pending_action: str | None = None  # JSON: tracks multi-turn state (e.g. slot selection)
    last_message_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    direction: str = Field(max_length=10)  # inbound | outbound
    content: str
    raw_payload: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Handoff(SQLModel, table=True):
    __tablename__ = "handoffs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    reason: str = Field(max_length=255)
    priority: str = Field(default="normal", max_length=20)  # low | normal | high | urgent
    context_summary: str | None = None
    status: str = Field(default="open", max_length=20)  # open | assigned | resolved
    created_at: datetime = Field(default_factory=datetime.utcnow)
