"""
Telegram Service — thin wrapper for webhook management operations.
"""
from __future__ import annotations

from app.integrations.telegram import client as telegram_client


class TelegramService:
    async def set_webhook(self, url: str | None = None) -> bool:
        return await telegram_client.set_webhook(url)

    async def delete_webhook(self) -> bool:
        return await telegram_client.delete_webhook()

    async def get_webhook_info(self) -> dict | None:
        return await telegram_client.get_webhook_info()
