from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlmodel import Field, SQLModel


class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str = Field(max_length=255)
    cpf: str | None = Field(default=None, max_length=14, unique=True, index=True)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    telegram_user_id: str | None = Field(default=None, max_length=64, unique=True, index=True)
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    convenio_name: str | None = Field(default=None, max_length=128)
    insurance_card_number: str | None = Field(default=None, max_length=64)
    consented_ai: bool = Field(default=False)
    preferred_channel: str = Field(default="telegram", max_length=32)
    operational_notes: str | None = None
    # CRM fields
    tags: str | None = Field(default=None, max_length=512)   # CSV: "urgente,vip,convenio_pendente"
    crm_notes: str | None = Field(default=None)               # Notas internas do operador
    stage: str | None = Field(default="lead", max_length=32)  # lead | patient | inactive
    source: str | None = Field(default=None, max_length=64)   # telegram | whatsapp | indicacao | etc
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
