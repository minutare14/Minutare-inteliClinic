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
            # Search in main specialty AND secondary specialties
            stmt = stmt.where(
                (Professional.specialty.ilike(f"%{specialty}%"))
                | (Professional.specialties_secondary.ilike(f"%{specialty}%"))
            )
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

    async def create(self, full_name: str, specialty: str, crm: str) -> Professional:
        prof = Professional(full_name=full_name, specialty=specialty, crm=crm)
        self.session.add(prof)
        await self.session.commit()
        await self.session.refresh(prof)
        return prof

    async def update(self, professional_id: uuid.UUID, **kwargs) -> Professional | None:
        prof = await self.get_by_id(professional_id)
        if not prof:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(prof, key, value)
        await self.session.commit()
        await self.session.refresh(prof)
        return prof

    async def deactivate(self, professional_id: uuid.UUID) -> Professional | None:
        prof = await self.get_by_id(professional_id)
        if not prof:
            return None
        prof.active = False
        await self.session.commit()
        await self.session.refresh(prof)
        return prof

    async def list_all(self, specialty: str | None = None) -> list[Professional]:
        """List all professionals including inactive (for admin view)."""
        stmt = select(Professional)
        if specialty:
            stmt = stmt.where(
                (Professional.specialty.ilike(f"%{specialty}%"))
                | (Professional.specialties_secondary.ilike(f"%{specialty}%"))
            )
        stmt = stmt.order_by(Professional.full_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_insurance(self, insurance_name: str) -> list[Professional]:
        """List active professionals who accept a given insurance plan."""
        stmt = (
            select(Professional)
            .where(Professional.active.is_(True))
            .where(Professional.accepts_insurance.is_(True))
            .where(Professional.insurance_plans.ilike(f"%{insurance_name}%"))
        )
        stmt = stmt.order_by(Professional.full_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
