from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


# ── ClinicSettings ──────────────────────────────────────────────────────────

class ClinicProfileUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    chatbot_name: str | None = None
    cnpj: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    working_hours: str | None = None
    emergency_phone: str | None = None


class BrandingUpdate(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None


class AISettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ai_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    rag_confidence_threshold: float | None = None
    rag_top_k: int | None = None
    rag_chunk_size: int | None = None
    rag_chunk_overlap: int | None = None
    handoff_enabled: bool | None = None
    handoff_confidence_threshold: float | None = None
    clinical_questions_block: bool | None = None
    bot_persona: str | None = None


class ClinicSettingsRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    name: str
    short_name: str | None
    chatbot_name: str
    cnpj: str | None
    phone: str | None
    email: str | None
    website: str | None
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    working_hours: str | None
    emergency_phone: str | None
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    ai_provider: str | None
    ai_model: str | None
    embedding_provider: str | None
    embedding_model: str | None
    rag_confidence_threshold: float
    rag_top_k: int
    rag_chunk_size: int
    rag_chunk_overlap: int
    handoff_enabled: bool
    handoff_confidence_threshold: float
    clinical_questions_block: bool
    bot_persona: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── InsuranceCatalog ────────────────────────────────────────────────────────

class InsuranceCreate(BaseModel):
    name: str
    code: str | None = None
    plan_types: str | None = None
    notes: str | None = None


class InsuranceUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    plan_types: str | None = None
    notes: str | None = None
    active: bool | None = None


class InsuranceRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    name: str
    code: str | None
    plan_types: str | None
    notes: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ClinicSpecialty ─────────────────────────────────────────────────────────

class SpecialtyCreate(BaseModel):
    name: str
    description: str | None = None


class SpecialtyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None


class SpecialtyRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    name: str
    description: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── PromptRegistry ──────────────────────────────────────────────────────────

class PromptCreate(BaseModel):
    agent: str
    prompt_type: str | None = None  # system_base | persona | behavior_rules | safety_rules | query_rewrite | document_grading
    scope: str = "global"
    name: str
    description: str | None = None
    content: str


class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    active: bool | None = None


class PromptRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    agent: str
    prompt_type: str | None = None
    scope: str
    name: str
    description: str | None
    content: str
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
