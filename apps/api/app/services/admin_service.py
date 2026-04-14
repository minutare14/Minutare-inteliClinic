from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin import ClinicSettings, InsuranceCatalog, PromptRegistry
from app.repositories.admin_repository import AdminRepository
from app.schemas.admin import (
    AISettingsUpdate,
    BrandingUpdate,
    ClinicProfileUpdate,
    ClinicSettingsRead,
    InsuranceCreate,
    InsuranceRead,
    InsuranceUpdate,
    PromptCreate,
    PromptRead,
    PromptUpdate,
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
)


def _env_defaults() -> dict:
    """Seed clinic_settings from .env values on first access."""
    return {
        "name": settings.clinic_name,
        "short_name": settings.clinic_short_name or None,
        "chatbot_name": settings.clinic_chatbot_name or "Assistente",
        "city": settings.clinic_city or None,
        "phone": settings.clinic_phone or None,
        "ai_provider": settings.llm_provider or None,
        "embedding_provider": settings.embedding_provider or "openai",
        "rag_confidence_threshold": settings.rag_confidence_threshold,
        "rag_top_k": settings.rag_top_k,
        "rag_chunk_size": settings.rag_chunk_size,
        "rag_chunk_overlap": settings.rag_chunk_overlap,
    }


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AdminRepository(session)
        self.clinic_id = settings.clinic_id

    # ── Clinic Settings ─────────────────────────────────────────────────────

    async def get_clinic_settings(self) -> ClinicSettingsRead:
        obj = await self.repo.get_or_create_clinic_settings(
            clinic_id=self.clinic_id,
            defaults=_env_defaults(),
        )
        return ClinicSettingsRead.model_validate(obj)

    async def update_profile(self, data: ClinicProfileUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            # Create on first PATCH
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        return ClinicSettingsRead.model_validate(obj)

    async def update_branding(self, data: BrandingUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        return ClinicSettingsRead.model_validate(obj)

    async def update_ai_settings(self, data: AISettingsUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        return ClinicSettingsRead.model_validate(obj)

    # ── Insurance Catalog ───────────────────────────────────────────────────

    async def list_insurance(self, active_only: bool = False) -> list[InsuranceRead]:
        items = await self.repo.list_insurance(self.clinic_id, active_only=active_only)
        return [InsuranceRead.model_validate(i) for i in items]

    async def create_insurance(self, data: InsuranceCreate) -> InsuranceRead:
        obj = await self.repo.create_insurance(self.clinic_id, data.model_dump())
        return InsuranceRead.model_validate(obj)

    async def update_insurance(self, insurance_id: uuid.UUID, data: InsuranceUpdate) -> InsuranceRead | None:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_insurance(insurance_id, payload)
        if not obj:
            return None
        return InsuranceRead.model_validate(obj)

    async def delete_insurance(self, insurance_id: uuid.UUID) -> bool:
        return await self.repo.delete_insurance(insurance_id)

    # ── Prompt Registry ─────────────────────────────────────────────────────

    async def list_prompts(self, agent: str | None = None) -> list[PromptRead]:
        items = await self.repo.list_prompts(self.clinic_id, agent=agent)
        return [PromptRead.model_validate(p) for p in items]

    async def create_prompt(self, data: PromptCreate) -> PromptRead:
        obj = await self.repo.create_prompt(self.clinic_id, data.model_dump())
        return PromptRead.model_validate(obj)

    async def get_prompt(self, prompt_id: uuid.UUID) -> PromptRead | None:
        obj = await self.repo.get_prompt(prompt_id)
        if not obj:
            return None
        return PromptRead.model_validate(obj)

    async def update_prompt(self, prompt_id: uuid.UUID, data: PromptUpdate) -> PromptRead | None:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_prompt(prompt_id, payload)
        if not obj:
            return None
        return PromptRead.model_validate(obj)

    async def get_active_prompt_content(self, agent: str) -> str | None:
        """Return content of the active prompt for an agent, or None."""
        obj = await self.repo.get_active_prompt(self.clinic_id, agent)
        return obj.content if obj else None

    # ── Specialties ─────────────────────────────────────────────────────────

    async def list_specialties(self, active_only: bool = False) -> list[SpecialtyRead]:
        items = await self.repo.list_specialties(self.clinic_id, active_only=active_only)
        return [SpecialtyRead.model_validate(i) for i in items]

    async def create_specialty(self, data: SpecialtyCreate) -> SpecialtyRead:
        obj = await self.repo.create_specialty(self.clinic_id, data.model_dump())
        return SpecialtyRead.model_validate(obj)

    async def update_specialty(self, specialty_id: uuid.UUID, data: SpecialtyUpdate) -> SpecialtyRead | None:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_specialty(specialty_id, payload)
        return SpecialtyRead.model_validate(obj) if obj else None

    async def delete_specialty(self, specialty_id: uuid.UUID) -> bool:
        return await self.repo.delete_specialty(specialty_id)
