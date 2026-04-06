from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_type: str = Field(max_length=20)  # user | ai | system
    actor_id: str = Field(max_length=128)
    action: str = Field(max_length=128)
    resource_type: str = Field(max_length=64)
    resource_id: str = Field(max_length=128)
    payload: str | None = None  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
