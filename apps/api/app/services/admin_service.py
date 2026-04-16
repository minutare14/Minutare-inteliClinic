from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.embedding import (
    ADMIN_EMBEDDING_PROVIDERS,
    default_embedding_dimension,
    default_embedding_model,
    normalize_embedding_provider,
)
from app.models.admin import ClinicSettings
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

logger = logging.getLogger(__name__)


class AdminConfigError(ValueError):
    """Raised when the admin panel attempts to persist an invalid AI/RAG config."""


def _env_provider() -> str:
    return normalize_embedding_provider(settings.embedding_provider or "local")


def _raw_provider(value: str | None) -> str:
    return (value or "").strip().lower()


def _env_model_for(provider: str) -> str:
    explicit_model = settings.embedding_model if _env_provider() == provider else None
    return default_embedding_model(provider, explicit_model)


def _env_defaults() -> dict:
    """Seed clinic_settings from .env values on first access."""
    provider = _env_provider()
    return {
        "name": settings.clinic_name,
        "short_name": settings.clinic_short_name or None,
        "chatbot_name": settings.clinic_chatbot_name or "Assistente",
        "city": settings.clinic_city or None,
        "phone": settings.clinic_phone or None,
        "ai_provider": settings.llm_provider or None,
        "embedding_provider": provider,
        "embedding_model": _env_model_for(provider),
        "rag_confidence_threshold": settings.rag_confidence_threshold,
        "rag_top_k": settings.rag_top_k,
        "rag_chunk_size": settings.rag_chunk_size,
        "rag_chunk_overlap": settings.rag_chunk_overlap,
    }


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AdminRepository(session)
        self.clinic_id = settings.clinic_id

    async def _get_or_seed_clinic_settings(self) -> ClinicSettings:
        obj = await self.repo.get_or_create_clinic_settings(
            clinic_id=self.clinic_id,
            defaults=_env_defaults(),
        )
        return await self._ensure_ai_defaults(obj)

    async def _ensure_ai_defaults(self, obj: ClinicSettings) -> ClinicSettings:
        updates: dict[str, object] = {}
        provider = normalize_embedding_provider(obj.embedding_provider or _env_provider())
        provider_is_persisted = bool(obj.embedding_provider)

        if provider_is_persisted:
            try:
                self._validate_embedding_provider(provider)
            except AdminConfigError as exc:
                fallback_provider = _env_provider()
                updates["embedding_provider"] = fallback_provider
                updates["embedding_model"] = _env_model_for(fallback_provider)
                logger.warning(
                    "[ADMIN:ai] clinic_id=%s invalid persisted embedding config "
                    "provider=%s model=%s reason=%s normalized_provider=%s normalized_model=%s",
                    self.clinic_id,
                    obj.embedding_provider,
                    obj.embedding_model,
                    exc,
                    fallback_provider,
                    updates["embedding_model"],
                )
                provider = fallback_provider

        if not obj.embedding_provider:
            updates["embedding_provider"] = provider
        if not obj.embedding_model and "embedding_model" not in updates:
            updates["embedding_model"] = self._resolve_embedding_model(
                provider=provider,
                current=obj,
                requested=None,
            )

        if not updates:
            return obj

        updated = await self.repo.update_clinic_settings(self.clinic_id, updates)
        return updated or obj

    def _resolve_embedding_model(
        self,
        *,
        provider: str,
        current: ClinicSettings | None,
        requested: str | None,
    ) -> str:
        requested_model = (requested or "").strip() or None
        if requested_model:
            return requested_model

        current_provider = normalize_embedding_provider(current.embedding_provider) if current else None
        if current and current.embedding_model and current_provider == provider:
            return current.embedding_model

        return _env_model_for(provider)

    def _validate_embedding_provider(self, provider: str) -> None:
        normalized = _raw_provider(provider) or "local"
        if normalized not in ADMIN_EMBEDDING_PROVIDERS:
            supported = ", ".join(ADMIN_EMBEDDING_PROVIDERS)
            raise AdminConfigError(
                f"Provider de embedding inválido: '{provider}'. Use um destes: {supported}."
            )

        required_dim = default_embedding_dimension(normalized)
        if settings.embedding_dim != required_dim:
            raise AdminConfigError(
                "O provider de embedding "
                f"'{normalized}' requer dimensão {required_dim}, mas este deploy está com "
                f"EMBEDDING_DIM={settings.embedding_dim}. Ajuste o servidor e rode as "
                "migrations antes de usar esse provider."
            )

        if normalized == "openai" and not settings.openai_api_key:
            raise AdminConfigError(
                "OpenAI para embeddings exige OPENAI_API_KEY configurada no backend."
            )

        if normalized == "gemini" and not settings.gemini_api_key:
            raise AdminConfigError(
                "Gemini para embeddings exige GEMINI_API_KEY configurada no backend."
            )

    async def get_clinic_settings(self) -> ClinicSettingsRead:
        obj = await self._get_or_seed_clinic_settings()
        return ClinicSettingsRead.model_validate(obj)

    async def update_profile(self, data: ClinicProfileUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        obj = await self._ensure_ai_defaults(obj)
        return ClinicSettingsRead.model_validate(obj)

    async def update_branding(self, data: BrandingUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        obj = await self._ensure_ai_defaults(obj)
        return ClinicSettingsRead.model_validate(obj)

    async def update_ai_settings(self, data: AISettingsUpdate) -> ClinicSettingsRead:
        payload = {k: v for k, v in data.model_dump().items() if v is not None}
        current = await self._get_or_seed_clinic_settings()

        provider = _raw_provider(
            payload.get("embedding_provider") or current.embedding_provider or _env_provider()
        ) or "local"
        self._validate_embedding_provider(provider)
        payload["embedding_provider"] = provider
        payload["embedding_model"] = self._resolve_embedding_model(
            provider=provider,
            current=current,
            requested=payload.get("embedding_model"),
        )

        logger.info(
            "[ADMIN:ai] clinic_id=%s embedding_provider=%s embedding_model=%s schema_dimension=%d",
            self.clinic_id,
            payload["embedding_provider"],
            payload["embedding_model"],
            settings.embedding_dim,
        )

        obj = await self.repo.update_clinic_settings(self.clinic_id, payload)
        if not obj:
            defaults = _env_defaults()
            defaults.update(payload)
            obj = await self.repo.get_or_create_clinic_settings(self.clinic_id, defaults)
        obj = await self._ensure_ai_defaults(obj)
        return ClinicSettingsRead.model_validate(obj)

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
        obj = await self.repo.get_active_prompt(self.clinic_id, agent)
        return obj.content if obj else None

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
