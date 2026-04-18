from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import ClinicSettings, ClinicSpecialty, InsuranceCatalog, PromptRegistry


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── ClinicSettings ──────────────────────────────────────────────────────

    async def get_clinic_settings(self, clinic_id: str) -> ClinicSettings | None:
        result = await self.session.execute(
            select(ClinicSettings).where(ClinicSettings.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_clinic_settings(self, clinic_id: str, defaults: dict) -> ClinicSettings:
        existing = await self.get_clinic_settings(clinic_id)
        if existing:
            return existing
        obj = ClinicSettings(clinic_id=clinic_id, **defaults)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update_clinic_settings(self, clinic_id: str, data: dict) -> ClinicSettings | None:
        obj = await self.get_clinic_settings(clinic_id)
        if not obj:
            return None
        data["updated_at"] = datetime.utcnow()
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    # ── InsuranceCatalog ────────────────────────────────────────────────────

    async def list_insurance(self, clinic_id: str, active_only: bool = False) -> list[InsuranceCatalog]:
        stmt = select(InsuranceCatalog).where(InsuranceCatalog.clinic_id == clinic_id)
        if active_only:
            stmt = stmt.where(InsuranceCatalog.active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_insurance(self, clinic_id: str, data: dict) -> InsuranceCatalog:
        obj = InsuranceCatalog(clinic_id=clinic_id, **data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_insurance(self, insurance_id: uuid.UUID) -> InsuranceCatalog | None:
        result = await self.session.execute(
            select(InsuranceCatalog).where(InsuranceCatalog.id == insurance_id)
        )
        return result.scalar_one_or_none()

    async def update_insurance(self, insurance_id: uuid.UUID, data: dict) -> InsuranceCatalog | None:
        obj = await self.get_insurance(insurance_id)
        if not obj:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete_insurance(self, insurance_id: uuid.UUID) -> bool:
        obj = await self.get_insurance(insurance_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.commit()
        return True

    # ── PromptRegistry ──────────────────────────────────────────────────────

    async def list_prompts(self, clinic_id: str, agent: str | None = None) -> list[PromptRegistry]:
        stmt = select(PromptRegistry).where(PromptRegistry.clinic_id == clinic_id)
        if agent:
            stmt = stmt.where(PromptRegistry.agent == agent)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_prompt(self, prompt_id: uuid.UUID) -> PromptRegistry | None:
        result = await self.session.execute(
            select(PromptRegistry).where(PromptRegistry.id == prompt_id)
        )
        return result.scalar_one_or_none()

    async def create_prompt(self, clinic_id: str, data: dict) -> PromptRegistry:
        # Increment version if a prompt with same agent+name exists
        existing = await self.session.execute(
            select(PromptRegistry).where(
                PromptRegistry.clinic_id == clinic_id,
                PromptRegistry.agent == data.get("agent"),
                PromptRegistry.name == data.get("name"),
            )
        )
        latest = existing.scalar_one_or_none()
        version = (latest.version + 1) if latest else 1

        # Deactivate previous version
        if latest:
            latest.active = False
            self.session.add(latest)

        obj = PromptRegistry(clinic_id=clinic_id, version=version, **data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_active_prompt(
        self, clinic_id: str, agent: str, prompt_type: str | None = None
    ) -> PromptRegistry | None:
        """Return the active prompt matching agent or prompt_type, or None if not found.

        prompt_type takes precedence when provided (per-layer governance).
        agent is kept for backward compatibility with orchestrator/response_builder/guardrails.
        """
        stmt = select(PromptRegistry).where(
            PromptRegistry.clinic_id == clinic_id,
            PromptRegistry.active == True,  # noqa: E712
        )
        if prompt_type:
            stmt = stmt.where(PromptRegistry.prompt_type == prompt_type)
        elif agent:
            stmt = stmt.where(PromptRegistry.agent == agent)
        else:
            return None
        stmt = stmt.order_by(PromptRegistry.version.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_prompt(self, prompt_id: uuid.UUID, data: dict) -> PromptRegistry | None:
        obj = await self.get_prompt(prompt_id)
        if not obj:
            return None
        data["updated_at"] = datetime.utcnow()
        if "content" in data and data["content"] is not None:
            # Content edit bumps version
            data["version"] = obj.version + 1
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    # ── ClinicSpecialty ─────────────────────────────────────────────────────

    async def list_specialties(self, clinic_id: str, active_only: bool = False) -> list[ClinicSpecialty]:
        stmt = select(ClinicSpecialty).where(ClinicSpecialty.clinic_id == clinic_id)
        if active_only:
            stmt = stmt.where(ClinicSpecialty.active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_specialty(self, specialty_id: uuid.UUID) -> ClinicSpecialty | None:
        result = await self.session.execute(
            select(ClinicSpecialty).where(ClinicSpecialty.id == specialty_id)
        )
        return result.scalar_one_or_none()

    async def create_specialty(self, clinic_id: str, data: dict) -> ClinicSpecialty:
        obj = ClinicSpecialty(clinic_id=clinic_id, **data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update_specialty(self, specialty_id: uuid.UUID, data: dict) -> ClinicSpecialty | None:
        obj = await self.get_specialty(specialty_id)
        if not obj:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete_specialty(self, specialty_id: uuid.UUID) -> bool:
        obj = await self.get_specialty(specialty_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.commit()
        return True
