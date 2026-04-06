"""
Schedule Actions — Real database operations for agenda management.

Executes actual CRUD on schedule_slots from the AI pipeline.
Called by the orchestrator when FARO detects scheduling intents.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.professional import Professional
from app.models.schedule import ScheduleSlot, SlotStatus
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


@dataclass
class SlotOption:
    """A slot option to present to the user."""
    slot_id: uuid.UUID
    professional_name: str
    specialty: str
    start_at: datetime
    end_at: datetime

    def display(self) -> str:
        day = self.start_at.strftime("%d/%m/%Y")
        hour = self.start_at.strftime("%H:%M")
        end_h = self.end_at.strftime("%H:%M")
        return f"{day} {hour}-{end_h} — {self.professional_name} ({self.specialty})"


@dataclass
class ActionResult:
    """Result of a schedule action."""
    success: bool
    message: str
    slots: list[SlotOption] | None = None
    booked_slot: SlotOption | None = None


class ScheduleActions:
    """Real schedule actions operating on the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.schedule_repo = ScheduleRepository(session)
        self.professional_repo = ProfessionalRepository(session)
        self.audit = AuditService(session)

    async def search_slots(
        self,
        specialty: str | None = None,
        doctor_name: str | None = None,
        date_str: str | None = None,
        time_str: str | None = None,
    ) -> ActionResult:
        """
        Search available slots by specialty, doctor, date, time.

        Returns up to 5 matching available slots.
        """
        # 1. Find matching professionals
        professionals = await self._find_professionals(specialty, doctor_name)

        if not professionals:
            if doctor_name:
                return ActionResult(
                    success=False,
                    message=f"Não encontrei profissionais com o nome '{doctor_name}'. "
                            "Posso listar as especialidades disponíveis se preferir.",
                )
            if specialty:
                return ActionResult(
                    success=False,
                    message=f"Não encontrei profissionais na especialidade '{specialty}'. "
                            "Posso listar as especialidades disponíveis se preferir.",
                )
            return ActionResult(
                success=False,
                message="Por favor, informe a especialidade ou o nome do médico desejado.",
            )

        # 2. Build date range
        date_from, date_to = self._build_date_range(date_str, time_str)

        # 3. Query slots for each professional
        all_slots: list[SlotOption] = []
        for prof in professionals:
            slots = await self.schedule_repo.find_available(prof.id, date_from, date_to)
            for s in slots:
                all_slots.append(SlotOption(
                    slot_id=s.id,
                    professional_name=prof.full_name,
                    specialty=prof.specialty,
                    start_at=s.start_at,
                    end_at=s.end_at,
                ))

        # Filter by time preference
        if time_str and all_slots:
            all_slots = self._filter_by_time(all_slots, time_str)

        if not all_slots:
            return ActionResult(
                success=False,
                message="Não encontrei horários disponíveis para os critérios informados. "
                        "Quer tentar outra data ou outro profissional?",
            )

        # Limit to 5
        all_slots = sorted(all_slots, key=lambda s: s.start_at)[:5]

        # Format response
        lines = ["Encontrei os seguintes horários disponíveis:\n"]
        for i, slot in enumerate(all_slots, 1):
            lines.append(f"{i}️⃣ {slot.display()}")
        lines.append("\nQual horário prefere? Responda com o número.")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            slots=all_slots,
        )

    async def book_slot(
        self,
        slot_id: uuid.UUID,
        patient_id: uuid.UUID,
        source: str = "telegram",
    ) -> ActionResult:
        """Book a specific slot for a patient."""
        slot = await self.schedule_repo.book_slot(slot_id, patient_id, source)

        if not slot:
            return ActionResult(
                success=False,
                message="Desculpe, esse horário não está mais disponível. "
                        "Quer que eu busque outras opções?",
            )

        # Get professional info
        prof = await self.professional_repo.get_by_id(slot.professional_id)
        prof_name = prof.full_name if prof else "Profissional"
        specialty = prof.specialty if prof else ""

        await self.audit.log_event(
            actor_type="ai",
            actor_id="schedule_actions",
            action="slot.booked_via_ai",
            resource_type="schedule_slot",
            resource_id=str(slot.id),
            payload={
                "patient_id": str(patient_id),
                "professional": prof_name,
                "start_at": slot.start_at.isoformat(),
            },
        )

        booked = SlotOption(
            slot_id=slot.id,
            professional_name=prof_name,
            specialty=specialty,
            start_at=slot.start_at,
            end_at=slot.end_at,
        )

        day = slot.start_at.strftime("%d/%m/%Y")
        hour = slot.start_at.strftime("%H:%M")

        return ActionResult(
            success=True,
            message=(
                f"Consulta agendada com sucesso! ✅\n\n"
                f"📅 Data: {day}\n"
                f"🕐 Horário: {hour}\n"
                f"👨‍⚕️ Profissional: {prof_name}\n"
                f"📋 Especialidade: {specialty}\n\n"
                f"Lembre-se de chegar 15 minutos antes. "
                f"Caso precise cancelar, avise com pelo menos 24h de antecedência."
            ),
            booked_slot=booked,
        )

    async def cancel_slot(
        self,
        patient_id: uuid.UUID,
        slot_id: uuid.UUID | None = None,
        date_str: str | None = None,
    ) -> ActionResult:
        """Cancel a booked slot for a patient."""
        # Find the slot to cancel
        if slot_id:
            slot = await self.schedule_repo.get_by_id(slot_id)
        else:
            slot = await self._find_patient_slot(patient_id, date_str)

        if not slot:
            return ActionResult(
                success=False,
                message="Não encontrei nenhuma consulta agendada para cancelar. "
                        "Pode confirmar a data da consulta?",
            )

        if slot.patient_id != patient_id:
            return ActionResult(
                success=False,
                message="Essa consulta não está vinculada ao seu cadastro.",
            )

        if slot.status not in (SlotStatus.booked, SlotStatus.confirmed):
            return ActionResult(
                success=False,
                message=f"Essa consulta está com status '{slot.status}' e não pode ser cancelada.",
            )

        cancelled = await self.schedule_repo.cancel_slot(slot.id)
        if not cancelled:
            return ActionResult(success=False, message="Erro ao cancelar a consulta.")

        prof = await self.professional_repo.get_by_id(slot.professional_id)
        prof_name = prof.full_name if prof else "Profissional"

        await self.audit.log_event(
            actor_type="ai",
            actor_id="schedule_actions",
            action="slot.cancelled_via_ai",
            resource_type="schedule_slot",
            resource_id=str(slot.id),
            payload={"patient_id": str(patient_id)},
        )

        day = slot.start_at.strftime("%d/%m/%Y")
        hour = slot.start_at.strftime("%H:%M")

        return ActionResult(
            success=True,
            message=(
                f"Consulta cancelada com sucesso ❌\n\n"
                f"📅 Data: {day} às {hour}\n"
                f"👨‍⚕️ Profissional: {prof_name}\n\n"
                f"Se quiser reagendar, é só me avisar!"
            ),
        )

    async def reschedule_slot(
        self,
        patient_id: uuid.UUID,
        old_slot_id: uuid.UUID | None = None,
        old_date_str: str | None = None,
        new_date_str: str | None = None,
        new_time_str: str | None = None,
    ) -> ActionResult:
        """Cancel old slot and search for new ones."""
        # Find the old slot
        if old_slot_id:
            old_slot = await self.schedule_repo.get_by_id(old_slot_id)
        else:
            old_slot = await self._find_patient_slot(patient_id, old_date_str)

        if not old_slot:
            return ActionResult(
                success=False,
                message="Não encontrei a consulta a ser remarcada. "
                        "Pode me informar a data da consulta atual?",
            )

        if old_slot.patient_id != patient_id:
            return ActionResult(
                success=False,
                message="Essa consulta não está vinculada ao seu cadastro.",
            )

        # Get professional for the new search
        prof = await self.professional_repo.get_by_id(old_slot.professional_id)
        specialty = prof.specialty if prof else None

        # Search new slots
        result = await self.search_slots(
            specialty=specialty,
            date_str=new_date_str,
            time_str=new_time_str,
        )

        if not result.success:
            return ActionResult(
                success=False,
                message=(
                    "Não encontrei novos horários disponíveis para remarcação. "
                    "Quer tentar outra data?"
                ),
            )

        # Prepend context about rescheduling
        old_day = old_slot.start_at.strftime("%d/%m/%Y %H:%M")
        result.message = (
            f"Remarcação da consulta de {old_day}:\n\n" + result.message +
            "\n\nApós escolher, cancelarei a consulta anterior automaticamente."
        )

        return result

    async def list_patient_appointments(self, patient_id: uuid.UUID) -> ActionResult:
        """List all booked/confirmed appointments for a patient."""
        stmt = (
            select(ScheduleSlot)
            .where(
                and_(
                    ScheduleSlot.patient_id == patient_id,
                    ScheduleSlot.status.in_([SlotStatus.booked, SlotStatus.confirmed]),
                    ScheduleSlot.start_at >= datetime.utcnow(),
                )
            )
            .order_by(ScheduleSlot.start_at)
        )
        result = await self.session.execute(stmt)
        slots = list(result.scalars().all())

        if not slots:
            return ActionResult(
                success=True,
                message="Você não tem consultas agendadas no momento.",
            )

        lines = ["Suas consultas agendadas:\n"]
        options = []
        for i, s in enumerate(slots, 1):
            prof = await self.professional_repo.get_by_id(s.professional_id)
            prof_name = prof.full_name if prof else "Profissional"
            specialty = prof.specialty if prof else ""
            opt = SlotOption(
                slot_id=s.id,
                professional_name=prof_name,
                specialty=specialty,
                start_at=s.start_at,
                end_at=s.end_at,
            )
            options.append(opt)
            lines.append(f"{i}️⃣ {opt.display()}")

        return ActionResult(success=True, message="\n".join(lines), slots=options)

    # ─── Private helpers ───────────────────────────────────────

    async def _find_professionals(
        self, specialty: str | None, doctor_name: str | None
    ) -> list[Professional]:
        """Find professionals by name or specialty."""
        if doctor_name:
            profs = await self.professional_repo.search_by_name(doctor_name)
            if profs:
                return profs

        if specialty:
            return await self.professional_repo.list_active(specialty)

        # Return all active professionals
        return await self.professional_repo.list_active()

    def _build_date_range(
        self, date_str: str | None, time_str: str | None
    ) -> tuple[datetime, datetime]:
        """Build search date range from FARO entities."""
        now = datetime.utcnow()

        if date_str:
            try:
                target = datetime.strptime(date_str, "%Y-%m-%d")
                date_from = target.replace(hour=7, minute=0)
                date_to = target.replace(hour=20, minute=0)
            except ValueError:
                date_from = now
                date_to = now + timedelta(days=14)
        else:
            # Default: next 14 days
            date_from = now
            date_to = now + timedelta(days=14)

        return date_from, date_to

    def _filter_by_time(
        self, slots: list[SlotOption], time_str: str
    ) -> list[SlotOption]:
        """Filter slots by time preference (within 2 hour window)."""
        try:
            parts = time_str.split(":")
            target_hour = int(parts[0])
            filtered = [
                s for s in slots
                if abs(s.start_at.hour - target_hour) <= 2
            ]
            return filtered if filtered else slots
        except (ValueError, IndexError):
            return slots

    async def _find_patient_slot(
        self, patient_id: uuid.UUID, date_str: str | None
    ) -> ScheduleSlot | None:
        """Find a patient's booked slot, optionally by date."""
        conditions = [
            ScheduleSlot.patient_id == patient_id,
            ScheduleSlot.status.in_([SlotStatus.booked, SlotStatus.confirmed]),
        ]

        if date_str:
            try:
                target = datetime.strptime(date_str, "%Y-%m-%d")
                conditions.append(ScheduleSlot.start_at >= target)
                conditions.append(ScheduleSlot.start_at < target + timedelta(days=1))
            except ValueError:
                pass

        stmt = (
            select(ScheduleSlot)
            .where(and_(*conditions))
            .order_by(ScheduleSlot.start_at)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
