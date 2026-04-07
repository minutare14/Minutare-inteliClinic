"""Per-clinic settings loaded at deploy startup.

All values come from environment variables or a clinic.yaml config file.
NEVER hardcode clinic-specific values in this file or anywhere in core/.

How to configure a new clinic deploy:
    1. Copy config/examples/clinic.example.yaml → clinic.yaml
    2. Fill in all required fields
    3. Set environment variables (or use .env file)
    4. Run: python scripts/validate_config.py

Environment variable prefix: CLINIC_
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClinicSettings(BaseSettings):
    """Pydantic settings model for per-clinic configuration.

    Values are loaded from environment variables (CLINIC_ prefix) and
    optionally overridden by a clinic.yaml file.

    See config/examples/clinic.example.yaml for all available options.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLINIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    id: str = Field(..., description="Unique identifier for this clinic deploy (e.g. 'clinica_saude_sp')")
    name: str = Field(..., description="Full legal name of the clinic")
    short_name: str = Field(..., description="Short display name (e.g. 'Clínica Saúde')")
    cnpj: str = Field("", description="CNPJ of the clinic (for billing/compliance)")
    domain: str = Field("", description="Public domain for this deploy (e.g. 'bot.clinicasaude.com.br')")
    timezone: str = Field("America/Sao_Paulo", description="IANA timezone")
    language: str = Field("pt-BR", description="Primary language")

    # ------------------------------------------------------------------
    # Contact
    # ------------------------------------------------------------------
    phone: str = Field("", description="Main contact phone")
    address: str = Field("", description="Physical address")
    city: str = Field("", description="City")
    state: str = Field("SP", description="State (UF)")

    # ------------------------------------------------------------------
    # Features (enable/disable per deploy)
    # ------------------------------------------------------------------
    feature_scheduling: bool = Field(True, description="Enable scheduling via chatbot")
    feature_insurance_query: bool = Field(True, description="Enable insurance coverage queries")
    feature_financial: bool = Field(False, description="Enable financial queries")
    feature_glosa_detection: bool = Field(False, description="Enable internal glosa detection")
    feature_voice: bool = Field(False, description="Enable voice/phone channel (LiveKit, Phase 2)")
    feature_graphrag: bool = Field(False, description="Enable GraphRAG (Phase 2)")

    # ------------------------------------------------------------------
    # AI / LLM
    # ------------------------------------------------------------------
    llm_provider: str = Field("openai", description="LLM provider: openai | anthropic | gemini")
    llm_model: str = Field("gpt-4o-mini", description="Model name override")
    min_confidence: float = Field(0.65, description="Minimum confidence before fallback/escalation")
    max_turns: int = Field(20, description="Max conversation turns before forcing handoff")

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------
    qdrant_url: str = Field("http://localhost:6333", description="Qdrant server URL for this deploy")
    rag_top_k: int = Field(5, description="Number of RAG results to retrieve")
    rag_min_score: float = Field(0.70, description="Minimum similarity score for RAG results")
    rag_chunk_size: int = Field(800, description="Target chunk size in characters")
    rag_chunker_strategy: str = Field("semantic", description="Chunker strategy: semantic | fixed")

    # ------------------------------------------------------------------
    # Business hours
    # ------------------------------------------------------------------
    business_hours_start: str = Field("08:00", description="Opening time (HH:MM)")
    business_hours_end: str = Field("18:00", description="Closing time (HH:MM)")
    business_days: list[int] = Field(
        default=[1, 2, 3, 4, 5],  # Mon-Fri
        description="Working days (0=Sun, 1=Mon, ..., 6=Sat)",
    )
    after_hours_message: str = Field(
        "Nosso atendimento funciona de segunda a sexta, das 08h às 18h. "
        "Deixe sua mensagem e retornaremos em breve.",
        description="Message sent outside business hours",
    )

    # ------------------------------------------------------------------
    # Insurance / Convênios
    # ------------------------------------------------------------------
    accepted_insurances: list[str] = Field(
        default_factory=list,
        description="List of accepted insurance plan names",
    )
    accepts_private: bool = Field(True, description="Accept private (particular) patients")

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------
    logo_path: str = Field("", description="Path to clinic logo file")
    primary_color: str = Field("#0066CC", description="Primary brand color (hex)")
    chatbot_name: str = Field("Assistente", description="Name of the chatbot assistant")
    chatbot_greeting: str = Field(
        "Olá! Sou o assistente virtual da {clinic_name}. Como posso ajudá-lo?",
        description="Greeting message template. Use {clinic_name} as placeholder.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9_]{3,64}$", v):
            raise ValueError(
                "clinic_id must be 3-64 lowercase alphanumeric characters or underscores"
            )
        return v

    def get_greeting(self) -> str:
        """Return the formatted greeting message."""
        return self.chatbot_greeting.format(clinic_name=self.short_name)

    def to_rag_config(self) -> dict:
        """Return the subset of settings relevant to RAG configuration."""
        return {
            "clinic_id": self.id,
            "qdrant_url": self.qdrant_url,
            "top_k": self.rag_top_k,
            "min_score": self.rag_min_score,
            "chunk_size": self.rag_chunk_size,
            "chunker_strategy": self.rag_chunker_strategy,
        }

    def to_graph_config(self) -> dict:
        """Return settings for LangGraph GraphConfig."""
        return {
            "confidence_threshold": self.min_confidence,
            "max_turns": self.max_turns,
        }


@lru_cache(maxsize=1)
def get_clinic_settings() -> ClinicSettings:
    """Return the singleton clinic settings for this deploy.

    Cached after first load. Call with get_clinic_settings.cache_clear()
    to reload (e.g. in tests).
    """
    return ClinicSettings()
