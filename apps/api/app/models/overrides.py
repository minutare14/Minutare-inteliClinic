"""HumanOverride — audit trail for manual corrections that supersede extracted/RAG data."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class HumanOverride(SQLModel, table=True):
    """
    Records manual corrections that override what was previously extracted
    from documents or stored in Pinecone.

    When a human changes a structured value (price, doctor, rule, etc.),
    this record tracks the old vs new value so the AI can:
      1. Prefer the new value immediately (source-of-truth priority)
      2. Explain the correction if asked ("o valor foi atualizado de X para Y")
      3. Audit trail of human interventions
    """
    __tablename__ = "human_overrides"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)

    # Which entity type was overridden: "service", "professional", "service_price", etc.
    entity_type: str = Field(max_length=64)

    # UUID of the specific entity (service_id, professional_id, etc.)
    entity_id: uuid.UUID | None = Field(default=None, index=True)

    # Field that was changed (e.g. "base_price", "name", "doctor_id")
    field_name: str = Field(max_length=128)

    # Previous value before override
    old_value: str | None = Field(default=None, max_length=2048)

    # New value after override
    new_value: str | None = Field(default=None, max_length=2048)

    # Why it was changed (optional reason)
    reason: str | None = Field(default=None, max_length=512)

    # Who made the change
    changed_by: str = Field(max_length=255)

    # When it was changed
    changed_at: datetime = Field(default_factory=datetime.utcnow)

    # If True, this override is active and should be preferred over RAG/structured data
    active: bool = Field(default=True)
