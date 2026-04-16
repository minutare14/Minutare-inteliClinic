from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LOCAL_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_EMBEDDING_MODEL = "text-embedding-004"

DEFAULT_EMBEDDING_DIMENSIONS = {
    "local": 384,
    "gemini": 768,
    "openai": 1536,
}

ADMIN_EMBEDDING_PROVIDERS = ("local", "openai", "gemini")
RUNTIME_EMBEDDING_PROVIDERS = (*ADMIN_EMBEDDING_PROVIDERS, "auto")


@dataclass(frozen=True)
class EmbeddingRuntimeConfig:
    provider: str
    model: str
    schema_dimension: int
    source: str


def normalize_embedding_provider(value: str | None, *, fallback: str = "local") -> str:
    provider = (value or "").strip().lower()
    if not provider:
        return fallback
    if provider == "groq":
        return "local"
    return provider


def is_supported_embedding_provider(provider: str | None, *, admin: bool = False) -> bool:
    normalized = normalize_embedding_provider(provider, fallback="")
    supported = ADMIN_EMBEDDING_PROVIDERS if admin else RUNTIME_EMBEDDING_PROVIDERS
    return normalized in supported


def default_embedding_model(provider: str, explicit_model: str | None = None) -> str:
    model = (explicit_model or "").strip()
    if model:
        return model

    normalized = normalize_embedding_provider(provider)
    if normalized == "openai":
        return DEFAULT_OPENAI_EMBEDDING_MODEL
    if normalized == "gemini":
        return DEFAULT_GEMINI_EMBEDDING_MODEL
    return DEFAULT_LOCAL_EMBEDDING_MODEL


def default_embedding_dimension(provider: str) -> int:
    normalized = normalize_embedding_provider(provider)
    return DEFAULT_EMBEDDING_DIMENSIONS.get(normalized, DEFAULT_EMBEDDING_DIMENSIONS["local"])
