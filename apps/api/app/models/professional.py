from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Professional(SQLModel, table=True):
    __tablename__ = "professionals"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str = Field(max_length=255)
    specialty: str = Field(max_length=128)
    # Secondary specialties as comma-separated string (e.g. "Cefaleia, Distúrbios do Sono")
    specialties_secondary: str | None = Field(default=None, max_length=512)
    crm: str = Field(max_length=20, unique=True, index=True)
    active: bool = Field(default=True)
    allows_teleconsultation: bool = Field(default=False)
    accepts_insurance: bool = Field(default=True)
    # Convênios aceitos como CSV (e.g. "Unimed, Bradesco Saúde, SulAmérica, Particular")
    insurance_plans: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
