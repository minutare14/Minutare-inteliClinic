from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ServiceCategory(SQLModel, table=True):
    __tablename__ = "service_categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    name: str = Field(max_length=128)
    description: str | None = None
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Service(SQLModel, table=True):
    __tablename__ = "services"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="service_categories.id", index=True)
    name: str = Field(max_length=255)
    description: str | None = None
    duration_min: int = Field(default=30)
    active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServicePrice(SQLModel, table=True):
    __tablename__ = "service_prices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", index=True)
    insurance_plan_id: uuid.UUID | None = Field(default=None, index=True)
    price: float = Field(default=0.0)
    copay: float | None = None
    active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)