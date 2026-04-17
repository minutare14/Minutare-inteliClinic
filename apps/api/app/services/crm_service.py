"""
CRM Service — Lead and patient lifecycle management.

The Patient model already carries CRM fields (stage, tags, crm_notes, source)
added in migration 005. This service provides business logic on top of those
fields plus the new FollowUp and Alert tables.

CRM stages:
  lead → patient → inactive

Typical flow:
  1. Patient contacts via Telegram → created as 'lead'
  2. First appointment booked → promoted to 'patient'
  3. No activity for N days → can be marked 'inactive'
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, col

from app.models.patient import Patient
from app.models.jobs import FollowUp, FollowUpType, Alert, AlertPriority
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class CrmService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Lead / stage management ───────────────────────────────────────────────

    async def list_by_stage(
        self,
        stage: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Patient]:
        """List patients filtered by CRM stage."""
        q = select(Patient)
        if stage:
            q = q.where(Patient.stage == stage)
        q = q.order_by(col(Patient.created_at).desc()).limit(limit).offset(offset)
        result = await self.session.execute(q)
        return result.scalars().all()

    async def promote_to_patient(self, patient_id: uuid.UUID, actor_id: str = "system") -> Patient | None:
        """Promote a lead to patient stage (triggered on first booking)."""
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        if patient.stage != "patient":
            patient.stage = "patient"
            patient.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.session.add(patient)
            await self.session.commit()
            await self.session.refresh(patient)
            await self.audit.log_event(
                actor_type="system",
                actor_id=actor_id,
                action="crm.stage_changed",
                resource_type="patient",
                resource_id=str(patient_id),
                payload={"from": "lead", "to": "patient"},
            )
            logger.info("[CRM] patient_id=%s promoted to 'patient' stage", patient_id)

        return patient

    async def update_stage(
        self,
        patient_id: uuid.UUID,
        stage: str,
        actor_id: str = "operator",
    ) -> Patient | None:
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        old_stage = patient.stage
        patient.stage = stage
        patient.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(patient)
        await self.session.commit()
        await self.session.refresh(patient)

        await self.audit.log_event(
            actor_type="human",
            actor_id=actor_id,
            action="crm.stage_changed",
            resource_type="patient",
            resource_id=str(patient_id),
            payload={"from": old_stage, "to": stage},
        )
        return patient

    async def add_tags(
        self,
        patient_id: uuid.UUID,
        new_tags: list[str],
        actor_id: str = "operator",
    ) -> Patient | None:
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        existing = set(patient.tags.split(",")) if patient.tags else set()
        updated = existing | set(t.strip() for t in new_tags if t.strip())
        patient.tags = ",".join(sorted(updated))
        patient.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(patient)
        await self.session.commit()
        await self.session.refresh(patient)
        return patient

    async def add_note(
        self,
        patient_id: uuid.UUID,
        note: str,
        actor_id: str = "operator",
    ) -> Patient | None:
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
        new_note = f"[{timestamp}] {actor_id}: {note}"
        patient.crm_notes = (
            f"{patient.crm_notes}\n{new_note}" if patient.crm_notes else new_note
        )
        patient.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(patient)
        await self.session.commit()
        await self.session.refresh(patient)
        return patient

    # ── Follow-ups ────────────────────────────────────────────────────────────

    async def schedule_followup(
        self,
        patient_id: uuid.UUID,
        followup_type: FollowUpType,
        scheduled_at: datetime,
        notes: str | None = None,
        created_by: str = "system",
    ) -> FollowUp:
        fu = FollowUp(
            patient_id=patient_id,
            followup_type=followup_type,
            scheduled_at=scheduled_at,
            notes=notes,
            created_by=created_by,
        )
        self.session.add(fu)
        await self.session.commit()
        await self.session.refresh(fu)
        logger.info(
            "[CRM] followup_scheduled patient_id=%s type=%s at=%s",
            patient_id, followup_type.value, scheduled_at.isoformat(),
        )
        return fu

    async def list_pending_followups(
        self,
        due_before: datetime | None = None,
        limit: int = 50,
    ) -> list[FollowUp]:
        q = select(FollowUp).where(FollowUp.completed == False)  # noqa: E712
        if due_before:
            # Strip tzinfo so it can compare with TIMESTAMP WITHOUT TIME ZONE columns
            effective = due_before if due_before.tzinfo is None else due_before.replace(tzinfo=None)
            q = q.where(FollowUp.scheduled_at <= effective)
        q = q.order_by(FollowUp.scheduled_at).limit(limit)
        result = await self.session.execute(q)
        return result.scalars().all()

    async def complete_followup(self, followup_id: uuid.UUID) -> FollowUp | None:
        result = await self.session.execute(
            select(FollowUp).where(FollowUp.id == followup_id)
        )
        fu = result.scalar_one_or_none()
        if not fu:
            return None
        fu.completed = True
        fu.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(fu)
        await self.session.commit()
        await self.session.refresh(fu)
        return fu

    # ── Alerts ────────────────────────────────────────────────────────────────

    async def create_alert(
        self,
        patient_id: uuid.UUID,
        message: str,
        alert_type: str = "general",
        priority: AlertPriority = AlertPriority.normal,
        conversation_id: uuid.UUID | None = None,
    ) -> Alert:
        alert = Alert(
            patient_id=patient_id,
            conversation_id=conversation_id,
            alert_type=alert_type,
            message=message,
            priority=priority,
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def list_open_alerts(
        self,
        priority: AlertPriority | None = None,
        limit: int = 50,
    ) -> list[Alert]:
        q = select(Alert).where(Alert.resolved == False)  # noqa: E712
        if priority:
            q = q.where(Alert.priority == priority)
        q = q.order_by(Alert.created_at.desc()).limit(limit)
        result = await self.session.execute(q)
        return result.scalars().all()

    async def resolve_alert(self, alert_id: uuid.UUID) -> Alert | None:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.resolved = True
        alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Quick CRM overview metrics."""
        from sqlmodel import func

        stages = {"lead": 0, "patient": 0, "inactive": 0}
        result = await self.session.execute(
            select(Patient.stage, func.count(Patient.id)).group_by(Patient.stage)
        )
        for row in result.all():
            if row[0] in stages:
                stages[row[0]] = row[1]

        pending_fu = await self.session.execute(
            select(func.count(FollowUp.id)).where(FollowUp.completed == False)  # noqa: E712
        )
        open_alerts = await self.session.execute(
            select(func.count(Alert.id)).where(Alert.resolved == False)  # noqa: E712
        )

        return {
            "stages": stages,
            "pending_followups": pending_fu.scalar() or 0,
            "open_alerts": open_alerts.scalar() or 0,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_patient(self, patient_id: uuid.UUID) -> Patient | None:
        result = await self.session.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        return result.scalar_one_or_none()
