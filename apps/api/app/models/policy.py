from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


class ClinicPolicy(SQLModel, table=True):
    __tablename__ = "clinic_policies"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    category: str = Field(max_length=64)  # cancellation|privacy|terms|general
    title: str = Field(max_length=255)
    content: str
    version: int = Field(default=1)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentExtraction(SQLModel, table=True):
    __tablename__ = "document_extractions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID | None = Field(default=None, index=True)
    chunk_id: uuid.UUID | None = None
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    entity_type: str = Field(max_length=32)  # doctor|service|price|insurance|policy|schedule
    extracted_data: dict = Field(default_factory=dict, sa_type=JSON)
    raw_text: str | None = None
    extraction_method: str = Field(max_length=32)  # deterministic|llm
    confidence: float = 0.0
    requires_review: bool = False
    status: str = Field(default="pending")  # pending|approved|rejected|revised|orphaned|cancelled
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    published_to: str | None = None  # professionals|services|service_prices|insurance_catalog|clinic_policies
    published_entity_id: uuid.UUID | None = None
    superseded_by: uuid.UUID | None = None
    source_extraction_id: uuid.UUID | None = None
    orphaned_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)