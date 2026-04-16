from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.admin import ClinicSettings
from app.schemas.admin import AISettingsUpdate
from app.services.admin_service import AdminConfigError, AdminService


@pytest.mark.asyncio
class TestAdminAISettings:
    async def test_get_clinic_settings_seeds_local_embedding_defaults(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.admin_service.settings.embedding_provider", "local")
        monkeypatch.setattr(
            "app.services.admin_service.settings.embedding_model",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        monkeypatch.setattr("app.services.admin_service.settings.embedding_dim", 384)

        svc = AdminService(session)
        settings = await svc.get_clinic_settings()

        assert settings.embedding_provider == "local"
        assert settings.embedding_model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    async def test_update_ai_settings_rejects_missing_openai_key(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.admin_service.settings.embedding_dim", 1536)
        monkeypatch.setattr("app.services.admin_service.settings.openai_api_key", "")

        svc = AdminService(session)

        with pytest.raises(AdminConfigError, match="OPENAI_API_KEY"):
            await svc.update_ai_settings(AISettingsUpdate(embedding_provider="openai"))

    async def test_update_ai_settings_persists_local_model(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.admin_service.settings.embedding_dim", 384)
        monkeypatch.setattr("app.services.admin_service.settings.embedding_provider", "local")
        monkeypatch.setattr(
            "app.services.admin_service.settings.embedding_model",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )

        svc = AdminService(session)
        updated = await svc.update_ai_settings(
            AISettingsUpdate(
                embedding_provider="local",
                embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            )
        )

        assert updated.embedding_provider == "local"
        assert updated.embedding_model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    async def test_get_clinic_settings_normalizes_invalid_persisted_provider(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.admin_service.settings.embedding_dim", 384)
        monkeypatch.setattr("app.services.admin_service.settings.embedding_provider", "local")
        monkeypatch.setattr(
            "app.services.admin_service.settings.embedding_model",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        monkeypatch.setattr("app.services.admin_service.settings.openai_api_key", "")
        monkeypatch.setattr("app.services.admin_service.settings.clinic_id", "minutare")

        clinic = ClinicSettings(
            clinic_id="minutare",
            name="Clinica Teste",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
        )
        session.add(clinic)
        await session.commit()

        svc = AdminService(session)
        settings = await svc.get_clinic_settings()

        assert settings.embedding_provider == "local"
        assert settings.embedding_model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
