"""
Jobs models — FollowUp and Alert.

These are the foundational models for:
  - Async follow-up tasks (post-appointment, lead nurturing, reactivation)
  - Operational alerts (no-shows, urgent handoffs, system notifications)

Future worker integration:
  - A background job runner (Celery, ARQ, or simple asyncio scheduler)
    will query FollowUp WHERE completed=false AND scheduled_at <= NOW()
    and dispatch each follow-up action.

Reference for future async worker design:
  - ARQ (async job queue): https://arq-docs.helpmanual.io/
  - LangGraph background tasks: https://langchain-ai.github.io/langgraph/
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class FollowUpType(str, Enum):
    post_appointment = "post_appointment"   # satisfaction / no-show recovery
    lead_nurture = "lead_nurture"           # re-engage unbooked lead
    reactivation = "reactivation"           # patient inactive > N days
    appointment_reminder = "appointment_reminder"  # pre-appointment reminder
    manual = "manual"                       # manually created by operator


class AlertPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class FollowUp(SQLModel, table=True):
    """
    Scheduled follow-up task for a patient.

    The worker picks up rows where:
        completed = false AND scheduled_at <= NOW()
    """
    __tablename__ = "follow_ups"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(index=True)
    conversation_id: Optional[uuid.UUID] = Field(default=None)
    followup_type: FollowUpType = Field(default=FollowUpType.manual)
    scheduled_at: datetime
    completed: bool = Field(default=False)
    completed_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    created_by: str = Field(default="system", max_length=128)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Alert(SQLModel, table=True):
    """
    Operational alert requiring human attention.

    Examples:
      - Handoff not resolved in X minutes
      - Patient no-show
      - Urgent clinical keyword detected in conversation
      - System error requiring intervention
    """
    __tablename__ = "alerts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: Optional[uuid.UUID] = Field(default=None, index=True)
    conversation_id: Optional[uuid.UUID] = Field(default=None)
    alert_type: str = Field(default="general", max_length=64)
    message: str
    priority: AlertPriority = Field(default=AlertPriority.normal)
    resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
