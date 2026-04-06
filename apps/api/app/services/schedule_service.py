from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import ScheduleSlot
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleSlotCreate
from app.services.audit_service import AuditService


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ScheduleRepository(session)
        self.audit = AuditService(session)

    async def create_slot(self, data: ScheduleSlotCreate) -> ScheduleSlot:
        slot = await self.repo.create(data)
        await self.audit.log_event(
            actor_type="system",
            actor_id="schedule_service",
            action="slot.created",
            resource_type="schedule_slot",
            resource_id=str(slot.id),
        )
        return slot

    async def find_available(
        self,
        professional_id: uuid.UUID,
        date_from: datetime,
        date_to: datetime,
    ) -> list[ScheduleSlot]:
        return await self.repo.find_available(professional_id, date_from, date_to)

    async def list_slots(
        self,
        professional_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: str | None = None,
    ) -> list[ScheduleSlot]:
        return await self.repo.list_slots(
            professional_id=professional_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )

    async def book_slot(
        self, slot_id: uuid.UUID, patient_id: uuid.UUID, source: str = "telegram"
    ) -> ScheduleSlot | None:
        slot = await self.repo.book_slot(slot_id, patient_id, source)
        if slot:
            await self.audit.log_event(
                actor_type="ai",
                actor_id="schedule_service",
                action="slot.booked",
                resource_type="schedule_slot",
                resource_id=str(slot.id),
                payload={"patient_id": str(patient_id), "source": source},
            )
        return slot

    async def cancel_slot(self, slot_id: uuid.UUID) -> ScheduleSlot | None:
        slot = await self.repo.cancel_slot(slot_id)
        if slot:
            await self.audit.log_event(
                actor_type="system",
                actor_id="schedule_service",
                action="slot.cancelled",
                resource_type="schedule_slot",
                resource_id=str(slot.id),
            )
        return slot
