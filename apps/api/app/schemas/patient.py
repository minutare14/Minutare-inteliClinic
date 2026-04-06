from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class PatientCreate(BaseModel):
    full_name: str
    cpf: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    telegram_user_id: str | None = None
    telegram_chat_id: str | None = None
    convenio_name: str | None = None
    insurance_card_number: str | None = None
    consented_ai: bool = False
    preferred_channel: str = "telegram"
    operational_notes: str | None = None


class PatientRead(BaseModel):
    id: uuid.UUID
    full_name: str
    cpf: str | None
    birth_date: date | None
    phone: str | None
    email: str | None
    telegram_user_id: str | None
    telegram_chat_id: str | None
    convenio_name: str | None
    insurance_card_number: str | None
    consented_ai: bool
    preferred_channel: str
    operational_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    convenio_name: str | None = None
    insurance_card_number: str | None = None
    consented_ai: bool | None = None
    operational_notes: str | None = None
