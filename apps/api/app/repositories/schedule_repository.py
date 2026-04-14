from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import ScheduleSlot, SlotStatus
from app.schemas.schedule import ScheduleSlotCreate


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ScheduleSlotCreate) -> ScheduleSlot:
        slot = ScheduleSlot(**data.model_dump())
        self.session.add(slot)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    async def get_by_id(self, slot_id: uuid.UUID) -> ScheduleSlot | None:
        return await self.session.get(ScheduleSlot, slot_id)

    async def find_available(
        self,
        professional_id: uuid.UUID,
        date_from: datetime,
        date_to: datetime,
    ) -> list[ScheduleSlot]:
        stmt = (
            select(ScheduleSlot)
            .where(
                and_(
                    ScheduleSlot.professional_id == professional_id,
                    ScheduleSlot.status == SlotStatus.available,
                    ScheduleSlot.start_at >= date_from,
                    ScheduleSlot.start_at <= date_to,
                )
            )
            .order_by(ScheduleSlot.start_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_slots(
        self,
        professional_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ScheduleSlot]:
        stmt = select(ScheduleSlot)
        conditions = []
        if professional_id:
            conditions.append(ScheduleSlot.professional_id == professional_id)
        if patient_id:
            conditions.append(ScheduleSlot.patient_id == patient_id)
        if date_from:
            conditions.append(ScheduleSlot.start_at >= date_from)
        if date_to:
            conditions.append(ScheduleSlot.start_at <= date_to)
        if status:
            conditions.append(ScheduleSlot.status == status)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(ScheduleSlot.start_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def book_slot(
        self, slot_id: uuid.UUID, patient_id: uuid.UUID, source: str = "telegram"
    ) -> ScheduleSlot | None:
        slot = await self.get_by_id(slot_id)
        if not slot or slot.status != SlotStatus.available:
            return None
        slot.patient_id = patient_id
        slot.status = SlotStatus.booked
        slot.source = source
        slot.updated_at = datetime.utcnow()
        self.session.add(slot)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    async def cancel_slot(self, slot_id: uuid.UUID) -> ScheduleSlot | None:
        slot = await self.get_by_id(slot_id)
        if not slot:
            return None
        slot.status = SlotStatus.cancelled
        slot.updated_at = datetime.utcnow()
        self.session.add(slot)
        await self.session.commit()
        await self.session.refresh(slot)
        return slot
