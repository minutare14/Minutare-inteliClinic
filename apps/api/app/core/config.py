from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = False
    app_log_level: str = "INFO"
    app_secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/inteliclinic"

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""  # explicit wins; otherwise derived from api_domain
    telegram_webhook_secret: str = ""

    # ── Public API domain (used to derive webhook URL) ────────────────────────
    api_domain: str = ""  # ex: "api.clinica.example.com"

    # ── Clinic identity ───────────────────────────────────────────────────────
    # Each deploy serves exactly one clinic. Set via .env — never hardcode.
    clinic_id: str = "clinic01"
    clinic_name: str = ""       # configure via Admin or CLINIC_NAME
    clinic_short_name: str = ""
    clinic_chatbot_name: str = ""  # configure via Admin or CLINIC_CHATBOT_NAME
    clinic_phone: str = ""
    clinic_city: str = ""

    @property
    def telegram_webhook_computed_url(self) -> str:
        """Webhook URL: explicit value wins; otherwise derive from api_domain."""
        if self.telegram_webhook_url:
            return self.telegram_webhook_url
        if self.api_domain:
            return f"https://{self.api_domain}/api/v1/telegram/webhook"
        return ""

    @property
    def telegram_token_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_bot_token not in ("", "[PREENCHER]"))

    # ── AI / LLM ──────────────────────────────────────────────────────────────
    llm_provider: str = ""  # groq | openai | anthropic | gemini (empty = auto-detect)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_model: str = ""  # override model name (empty = provider default)

    # ── Embeddings (independent from LLM provider) ───────────────────────────
    # Groq does NOT support embeddings — keep this config separate from LLM_PROVIDER.
    # Options: openai | gemini | local | auto
    #   openai → text-embedding-3-small (1536 dims)
    #   gemini → text-embedding-004 (768 dims)
    #   local  → sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dims)
    #   auto   → openai → gemini → local (first available)
    embedding_provider: str = "local"
    embedding_model: str = ""
    embedding_dim: int = 384

    # ── Qdrant (reserved for future vector store migration) ───────────────────
    qdrant_url: str = "http://localhost:6333"

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_confidence_threshold: float = 0.75
    rag_top_k: int = 5
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 100

    # ── RAG Reranker ──────────────────────────────────────────────────────────
    # Two-stage retrieval: pgvector (top_k_initial) → cross-encoder → LLM (top_k_final)
    #
    # Default model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
    #   - Multilingual, trained on mMARCO (includes PT-BR)
    #   - Reference: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
    #   - Qdrant FastEmbed reranker reference: https://qdrant.github.io/fastembed/examples/Reranking/
    #
    # Set RAG_RERANKER_ENABLED=true in .env to activate.
    # Requires sentence-transformers (already in deps).
    # Falls back to vector ordering if model fails to load.
    rag_reranker_enabled: bool = False
    rag_reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    rag_reranker_top_k_initial: int = 20   # candidates retrieved from pgvector
    rag_reranker_top_k_final: int = 5      # chunks sent to LLM after reranking

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    # JWT secret — MUST be set to a strong random value in production.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str = "change-me-generate-strong-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480  # 8 hours

    # Default admin user seeded on first startup (change via Admin UI after login)
    admin_default_email: str = "admin@clinic.local"
    admin_default_password: str = "change-me-on-first-login"

    # ── Google Calendar OAuth2 ─────────────────────────────────────────────────
    # Obtain from Google Cloud Console → APIs & Services → Credentials
    # Redirect URI must match exactly what's registered there.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""  # e.g. https://api.yourdomain.com/api/v1/google/callback

    # ── Background workers ────────────────────────────────────────────────────
    # How often the follow-up worker polls for overdue items (seconds)
    followup_worker_interval_seconds: int = 300  # 5 minutes

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
