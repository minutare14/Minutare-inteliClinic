from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Professional(SQLModel, table=True):
    __tablename__ = "professionals"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str = Field(max_length=255)
    specialty: str = Field(max_length=128)
    crm: str = Field(max_length=20, unique=True, index=True)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
