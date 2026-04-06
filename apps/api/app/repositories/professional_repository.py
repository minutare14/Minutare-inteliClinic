"""Professional repository — DB operations for professionals."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.professional import Professional


class ProfessionalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, professional_id: uuid.UUID) -> Professional | None:
        return await self.session.get(Professional, professional_id)

    async def list_active(self, specialty: str | None = None) -> list[Professional]:
        stmt = select(Professional).where(Professional.active.is_(True))
        if specialty:
            stmt = stmt.where(Professional.specialty.ilike(f"%{specialty}%"))
        stmt = stmt.order_by(Professional.full_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_name(self, name: str) -> list[Professional]:
        stmt = (
            select(Professional)
            .where(Professional.active.is_(True))
            .where(Professional.full_name.ilike(f"%{name}%"))
            .order_by(Professional.full_name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
