"""
Operational Reconciliation Service

Detects and handles conflicts between professional status changes and
active bookings / in-progress conversations.

Entry points:
  reconcile_professional_deactivation(professional_id)
    — called automatically by DELETE /api/v1/professionals/{id}

What it does when a professional is deactivated:
  1. Find all future booked slots for this professional → cancel them
  2. Scan active conversations with a pending select_slot action that
     references one of those slots → clear pending + create high-priority handoff
  3. Log all events with structured audit payload

Audit event actions emitted:
  operational.slot_cancelled_professional_deactivated
  operational.handoff_created_professional_deactivated
  operational.reconciliation_completed
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Handoff
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    professional_id: str
    professional_name: str
    affected_slots: int = 0
    cancelled_slots: int = 0
    handoffs_created: int = 0
    pending_actions_cleared: int = 0
    audit_events: int = 0
    errors: list[str] = field(default_factory=list)


class ReconciliationService:
    """
    Detects and resolves conflicts in operational data after status changes.

    Instantiate with the current async session — do not cache across requests.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.schedule_repo = ScheduleRepository(session)
        self.prof_repo = ProfessionalRepository(session)
        self.conv_repo = ConversationRepository(session)
        self.audit_svc = AuditService(session)

    async def reconcile_professional_deactivation(
        self, professional_id: uuid.UUID
    ) -> ReconciliationResult:
        """
        Full reconciliation after a professional is deactivated.

        Steps:
          1. Resolve professional metadata (name, specialty).
          2. Find all future booked slots for this professional.
          3. Cancel each slot + log audit event.
          4. Scan active conversations with pending select_slot / awaiting_schedule_date
             that overlap with this professional's slots → clear pending + create handoff.
          5. Log global reconciliation event.

        Returns ReconciliationResult with counts and any errors encountered.
        All steps that can be retried are caught individually; one failure
        does not abort the rest.
        """
        prof = await self.prof_repo.get_by_id(professional_id)
        prof_name = prof.full_name if prof else str(professional_id)
        specialty = prof.specialty if prof else None

        result = ReconciliationResult(
            professional_id=str(professional_id),
            professional_name=prof_name,
        )

        logger.info(
            "[RECONCILIATION] Starting reconciliation for deactivated professional "
            "prof='%s' id=%s specialty='%s'",
            prof_name, professional_id, specialty,
        )

        # ── Step 1: Find and cancel future booked slots ─────────────────────
        future_slots = await self.schedule_repo.find_future_booked_by_professional(
            professional_id
        )
        result.affected_slots = len(future_slots)

        logger.info(
            "[RECONCILIATION] affected_slots=%d for prof='%s'",
            len(future_slots), prof_name,
        )

        affected_slot_ids: set[str] = set()
        for slot in future_slots:
            affected_slot_ids.add(str(slot.id))
            try:
                await self.schedule_repo.cancel_slot(slot.id)
                result.cancelled_slots += 1

                await self.audit_svc.log_event(
                    actor_type="system",
                    actor_id="reconciliation_service",
                    action="operational.slot_cancelled_professional_deactivated",
                    resource_type="schedule_slot",
                    resource_id=str(slot.id),
                    payload={
                        "professional_id": str(professional_id),
                        "professional_name": prof_name,
                        "specialty": specialty,
                        "patient_id": str(slot.patient_id) if slot.patient_id else None,
                        "start_at": slot.start_at.isoformat(),
                        "invalidated_schedule_detected": True,
                        "contingency_flow_triggered": True,
                        "patient_notification_required": True,
                    },
                )
                result.audit_events += 1
                logger.warning(
                    "[RECONCILIATION] slot_cancelled slot_id=%s patient_id=%s start_at=%s "
                    "invalidated_schedule_detected=True patient_notification_required=True",
                    slot.id, slot.patient_id, slot.start_at.isoformat(),
                )
            except Exception as exc:
                msg = f"Failed to cancel slot {slot.id}: {exc}"
                result.errors.append(msg)
                logger.exception("[RECONCILIATION] %s", msg)

        # ── Step 2: Scan active conversations with pending slot selection ─────
        try:
            active_convs = await self.conv_repo.find_active_with_pending_action()
        except Exception as exc:
            msg = f"Failed to list active conversations: {exc}"
            result.errors.append(msg)
            logger.exception("[RECONCILIATION] %s", msg)
            active_convs = []

        for conv in active_convs:
            try:
                pending = json.loads(conv.pending_action or "{}")
            except (json.JSONDecodeError, TypeError):
                continue

            pending_type = pending.get("type")
            if pending_type not in ("select_slot", "awaiting_schedule_date"):
                continue

            # Check if any slot_id in pending overlaps with affected slots
            conv_slot_ids = set(pending.get("slot_ids", []))
            if pending_type == "select_slot" and not conv_slot_ids.intersection(affected_slot_ids):
                continue

            # awaiting_schedule_date stores doctor_name or specialty, not slot_ids.
            # Only clear if the stored specialty/doctor matches this professional.
            if pending_type == "awaiting_schedule_date":
                stored_doctor = (pending.get("doctor_name") or "").lower()
                stored_specialty = (pending.get("specialty") or "").lower()
                match_doctor = prof_name and stored_doctor and stored_doctor in prof_name.lower()
                match_specialty = specialty and stored_specialty and stored_specialty in specialty.lower()
                if not (match_doctor or match_specialty):
                    continue

            # Clear pending action
            try:
                conv.pending_action = None
                self.session.add(conv)
                await self.session.commit()
                result.pending_actions_cleared += 1
                logger.warning(
                    "[RECONCILIATION] pending_action_cleared conv_id=%s type=%s",
                    conv.id, pending_type,
                )
            except Exception as exc:
                msg = f"Failed to clear pending action for conversation {conv.id}: {exc}"
                result.errors.append(msg)
                logger.exception("[RECONCILIATION] %s", msg)
                continue

            # Create high-priority handoff for affected conversation
            if not conv.patient_id:
                continue
            try:
                handoff = Handoff(
                    conversation_id=conv.id,
                    reason="professional_deactivated_mid_conversation",
                    priority="high",
                    context_summary=(
                        f"Profissional {prof_name} desativado durante fluxo ativo de agendamento. "
                        f"Especialidade: {specialty or 'desconhecida'}. "
                        f"Paciente precisa ser reagendado manualmente."
                    ),
                )
                self.session.add(handoff)
                await self.session.commit()
                result.handoffs_created += 1

                await self.audit_svc.log_event(
                    actor_type="system",
                    actor_id="reconciliation_service",
                    action="operational.handoff_created_professional_deactivated",
                    resource_type="conversation",
                    resource_id=str(conv.id),
                    payload={
                        "professional_id": str(professional_id),
                        "professional_name": prof_name,
                        "specialty": specialty,
                        "patient_id": str(conv.patient_id),
                        "pending_type": pending_type,
                        "invalidated_schedule_detected": True,
                        "contingency_flow_triggered": True,
                        "patient_notification_required": True,
                        "alternative_offered": False,
                    },
                )
                result.audit_events += 1
                logger.warning(
                    "[RECONCILIATION] handoff_created conv_id=%s patient_id=%s "
                    "reason=professional_deactivated_mid_conversation priority=high",
                    conv.id, conv.patient_id,
                )
            except Exception as exc:
                msg = f"Failed to create handoff for conversation {conv.id}: {exc}"
                result.errors.append(msg)
                logger.exception("[RECONCILIATION] %s", msg)

        # ── Step 3: Global reconciliation audit event ─────────────────────────
        try:
            await self.audit_svc.log_event(
                actor_type="system",
                actor_id="reconciliation_service",
                action="operational.reconciliation_completed",
                resource_type="professional",
                resource_id=str(professional_id),
                payload={
                    "professional_name": prof_name,
                    "specialty": specialty,
                    "affected_slots": result.affected_slots,
                    "cancelled_slots": result.cancelled_slots,
                    "handoffs_created": result.handoffs_created,
                    "pending_actions_cleared": result.pending_actions_cleared,
                    "audit_events": result.audit_events,
                    "errors": result.errors,
                },
            )
            result.audit_events += 1
        except Exception as exc:
            logger.exception("[RECONCILIATION] Failed to log global event: %s", exc)

        logger.info(
            "[RECONCILIATION] Completed prof='%s' "
            "affected_slots=%d cancelled=%d handoffs=%d pending_cleared=%d errors=%d",
            prof_name, result.affected_slots, result.cancelled_slots,
            result.handoffs_created, result.pending_actions_cleared, len(result.errors),
        )
        return result
