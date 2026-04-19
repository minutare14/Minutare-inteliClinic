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
    service_code: str | None = Field(default=None, max_length=32, index=True)
    name: str = Field(max_length=255)
    description: str | None = None
    duration_min: int = Field(default=30)
    active: bool = Field(default=True)
    requires_specific_doctor: bool = Field(default=True)
    ai_summary: str | None = Field(default=None, max_length=500)
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
    price_changed_at: datetime | None = None
    changed_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProfessionalServiceLink(SQLModel, table=True):
    """Junction table linking professionals to services they are allowed to perform."""
    __tablename__ = "professional_service_links"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    professional_id: uuid.UUID | None = Field(default=None, foreign_key="professionals.id", index=True)
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", index=True)
    notes: str | None = None
    active: bool = Field(default=True)
    priority_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceOperationalRule(SQLModel, table=True):
    """Operational rules per service (scheduling, insurance, teleconsult, return_window)."""
    __tablename__ = "service_operational_rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", index=True)
    rule_type: str = Field(max_length=64)  # scheduling | insurance | teleconsult | return_window | general
    rule_text: str = Field(default="")
    active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceInsuranceRule(SQLModel, table=True):
    """Per-service insurance acceptance rules — which convênios a service accepts."""
    __tablename__ = "service_insurance_rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", index=True)
    insurance_name: str = Field(max_length=255)
    allowed: bool = Field(default=True)
    notes: str | None = Field(default=None, max_length=512)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
