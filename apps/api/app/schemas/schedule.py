from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ScheduleSlotCreate(BaseModel):
    professional_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime
    status: str = "available"
    slot_type: str = "first_visit"
    source: str = "manual"
    notes: str | None = None


class ScheduleSlotRead(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    patient_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    status: str
    slot_type: str
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleQuery(BaseModel):
    professional_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    status: str | None = None
