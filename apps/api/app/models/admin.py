from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.embedding import DEFAULT_LOCAL_EMBEDDING_MODEL


class ClinicSettings(SQLModel, table=True):
    """Configuração operacional da clínica — migra dados que antes ficavam só no .env."""

    __tablename__ = "clinic_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Identidade
    clinic_id: str = Field(default="default", max_length=64, index=True)
    name: str = Field(default="Clínica", max_length=255)
    short_name: str | None = Field(default=None, max_length=64)
    chatbot_name: str = Field(default="Assistente", max_length=128)
    cnpj: str | None = Field(default=None, max_length=18)

    # Contato
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=512)
    address: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = Field(default=None, max_length=9)

    # Atendimento
    working_hours: str | None = Field(default=None, max_length=512)
    emergency_phone: str | None = Field(default=None, max_length=20)

    # Branding
    logo_url: str | None = Field(default=None, max_length=1024)
    primary_color: str | None = Field(default="#2563eb", max_length=16)
    secondary_color: str | None = Field(default="#64748b", max_length=16)
    accent_color: str | None = Field(default=None, max_length=16)

    # IA
    ai_provider: str | None = Field(default=None, max_length=64)
    ai_model: str | None = Field(default=None, max_length=128)
    embedding_provider: str | None = Field(default="local", max_length=64)
    embedding_model: str | None = Field(default=DEFAULT_LOCAL_EMBEDDING_MODEL, max_length=255)
    rag_confidence_threshold: float = Field(default=0.75)
    rag_top_k: int = Field(default=5)
    rag_chunk_size: int = Field(default=500)
    rag_chunk_overlap: int = Field(default=100)
    handoff_enabled: bool = Field(default=True)
    handoff_confidence_threshold: float = Field(default=0.55)
    clinical_questions_block: bool = Field(default=True)

    # Persona do bot
    bot_persona: str | None = Field(default=None)  # texto livre de persona

    # Controle
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InsuranceCatalog(SQLModel, table=True):
    """Catálogo de convênios aceitos pela clínica."""

    __tablename__ = "insurance_catalog"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="default", max_length=64, index=True)
    name: str = Field(max_length=255)
    code: str | None = Field(default=None, max_length=64)
    plan_types: str | None = Field(default=None, max_length=512)  # CSV de planos
    notes: str | None = Field(default=None, max_length=512)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClinicSpecialty(SQLModel, table=True):
    """Especialidades médicas oferecidas pela clínica."""

    __tablename__ = "clinic_specialties"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="default", max_length=64, index=True)
    name: str = Field(max_length=128)  # Ex: Cardiologia, Ortopedia
    description: str | None = Field(default=None, max_length=512)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromptRegistry(SQLModel, table=True):
    """Registry de prompts dos agentes — permite edição sem mexer no código."""

    __tablename__ = "prompt_registry"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="default", max_length=64, index=True)
    agent: str = Field(max_length=64, index=True)  # orchestrator | response_builder | guardrails
    scope: str = Field(default="global", max_length=32)  # global | clinic | runtime
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    content: str  # texto do prompt
    version: int = Field(default=1)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
