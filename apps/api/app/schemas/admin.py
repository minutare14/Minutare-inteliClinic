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


# ── ServiceCategory ─────────────────────────────────────────────────────────

class ServiceCategoryCreate(BaseModel):
    name: str
    description: str | None = None


class ServiceCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None


class ServiceCategoryRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    name: str
    description: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Service ────────────────────────────────────────────────────────────────────

class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    category_id: uuid.UUID | None = None
    duration_min: int = 30
    requires_specific_doctor: bool = True
    ai_summary: str | None = None
    active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: uuid.UUID | None = None
    duration_min: int | None = None
    requires_specific_doctor: bool | None = None
    ai_summary: str | None = None
    active: bool | None = None


class ServiceDoctorSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    specialty: str


class ServicePriceSummary(BaseModel):
    id: uuid.UUID
    insurance_plan_id: uuid.UUID | None
    price: float
    copay: float | None


class ServiceRuleSummary(BaseModel):
    id: uuid.UUID
    rule_type: str
    rule_text: str
    version: int


class ServiceRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
    name: str
    description: str | None
    category_id: uuid.UUID | None
    category_name: str | None
    duration_min: int
    active: bool
    requires_specific_doctor: bool
    ai_summary: str | None
    version: int
    base_price: float | None
    doctors: list[ServiceDoctorSummary]
    prices: list[ServicePriceSummary] | None = None
    rules: list[ServiceRuleSummary] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── ServicePrice ─────────────────────────────────────────────────────────────

class ServicePriceUpsert(BaseModel):
    insurance_plan_id: uuid.UUID | None = None  # None = particular
    price: float
    copay: float | None = None


# ── ServiceOperationalRule ──────────────────────────────────────────────────

class ServiceRuleCreate(BaseModel):
    rule_type: str  # scheduling | insurance | teleconsult | return_window | general
    rule_text: str


class ServiceRuleUpdate(BaseModel):
    rule_text: str | None = None
    active: bool | None = None


class ServiceRuleRead(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID | None
    rule_type: str
    rule_text: str
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── ProfessionalServiceLink ────────────────────────────────────────────────

class ProfessionalServiceLinkCreate(BaseModel):
    professional_id: uuid.UUID
    notes: str | None = None
    priority_order: int = 0


class ProfessionalServiceLinkRead(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID | None
    service_id: uuid.UUID | None
    notes: str | None
    active: bool
    priority_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
