from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    app_debug: bool = False
    app_log_level: str = "INFO"
    app_secret_key: str = "change-me"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # --- Database ---
    database_url: str = "postgresql+asyncpg://minutare:minutare@localhost:5432/minutare_med"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""  # explícita; se vazia, derivada de api_domain
    telegram_webhook_secret: str = ""

    # --- Domínio público da API (usado para derivar URL do webhook) ---
    api_domain: str = ""  # ex: "api.inteliclinic.minutarecore.space"

    # --- Identidade da Clínica ---
    clinic_id: str = "minutare"
    clinic_name: str = "Minutare Med"
    clinic_short_name: str = ""
    clinic_chatbot_name: str = "Assistente"
    clinic_phone: str = ""
    clinic_city: str = ""

    @property
    def telegram_webhook_computed_url(self) -> str:
        """URL do webhook: valor explícito tem prioridade; senão, deriva de api_domain."""
        if self.telegram_webhook_url:
            return self.telegram_webhook_url
        if self.api_domain:
            return f"https://{self.api_domain}/api/v1/telegram/webhook"
        return ""

    @property
    def telegram_token_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_bot_token not in ("", "[PREENCHER]"))

    # --- AI / LLM ---
    llm_provider: str = ""  # groq | openai | anthropic | gemini (empty = auto-detect from keys)
    embedding_provider: str = "openai"  # openai | anthropic | local
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_model: str = ""  # override model name (empty = provider default)

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"

    # --- RAG ---
    rag_confidence_threshold: float = 0.75
    rag_top_k: int = 5
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 100

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
