"""
Telegram Service — thin wrapper for webhook management operations.
"""
from __future__ import annotations

from app.core.config import settings
from app.integrations.telegram import client as telegram_client


class TelegramService:
    async def set_webhook(self, url: str | None = None) -> bool:
        return await telegram_client.set_webhook(url)

    async def delete_webhook(self) -> bool:
        return await telegram_client.delete_webhook()

    async def get_webhook_info(self) -> dict | None:
        return await telegram_client.get_webhook_info()

    async def reconfigure_webhook(self) -> dict:
        """Registra (ou revalida) o webhook usando a URL derivada do env."""
        computed_url = settings.telegram_webhook_computed_url
        if not computed_url:
            return {
                "ok": False,
                "detail": "URL do webhook não pôde ser determinada. Defina API_DOMAIN ou TELEGRAM_WEBHOOK_URL.",
            }
        ok = await telegram_client.set_webhook(computed_url)
        return {"ok": ok, "url": computed_url}

    async def get_status(self) -> dict:
        """Retorna status consolidado da integração Telegram."""
        token_configured = settings.telegram_token_configured
        computed_url = settings.telegram_webhook_computed_url

        webhook_info: dict | None = None
        if token_configured:
            webhook_info = await telegram_client.get_webhook_info()

        return {
            "token_configured": token_configured,
            "computed_webhook_url": computed_url,
            "webhook_info": webhook_info,
        }
