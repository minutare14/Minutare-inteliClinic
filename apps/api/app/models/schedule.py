from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class SlotStatus(str, Enum):
    available = "available"
    booked = "booked"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class SlotType(str, Enum):
    first_visit = "first_visit"
    follow_up = "follow_up"
    exam = "exam"
    procedure = "procedure"


class SlotSource(str, Enum):
    manual = "manual"
    telegram = "telegram"
    whatsapp = "whatsapp"
    web = "web"
    phone = "phone"


class ScheduleSlot(SQLModel, table=True):
    __tablename__ = "schedule_slots"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    professional_id: uuid.UUID = Field(foreign_key="professionals.id", index=True)
    patient_id: uuid.UUID | None = Field(default=None, foreign_key="patients.id", index=True)
    start_at: datetime
    end_at: datetime
    status: str = Field(default=SlotStatus.available, max_length=20)
    slot_type: str = Field(default=SlotType.first_visit, max_length=32)
    source: str = Field(default=SlotSource.manual, max_length=20)
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
