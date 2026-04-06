"""
Telegram Bot API client — sends messages and manages webhook.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    return f"{BASE_URL.format(token=settings.telegram_bot_token)}/{method}"


async def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> dict | None:
    """Send a text message to a Telegram chat."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _api_url("sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error("Telegram sendMessage failed: %s", data)
                return None
            return data.get("result")
    except Exception:
        logger.exception("Error sending Telegram message to chat %s", chat_id)
        return None


async def set_webhook(url: str | None = None, secret_token: str | None = None) -> bool:
    """Register webhook URL with Telegram."""
    webhook_url = url or settings.telegram_webhook_url
    if not webhook_url:
        logger.warning("No webhook URL configured")
        return False

    payload: dict = {"url": webhook_url}
    if secret_token or settings.telegram_webhook_secret:
        payload["secret_token"] = secret_token or settings.telegram_webhook_secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api_url("setWebhook"), json=payload)
            resp.raise_for_status()
            data = resp.json()
            ok = data.get("ok", False)
            if ok:
                logger.info("Telegram webhook set to %s", webhook_url)
            else:
                logger.error("Failed to set webhook: %s", data)
            return ok
    except Exception:
        logger.exception("Error setting Telegram webhook")
        return False


async def delete_webhook() -> bool:
    """Remove webhook."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api_url("deleteWebhook"))
            resp.raise_for_status()
            return resp.json().get("ok", False)
    except Exception:
        logger.exception("Error deleting Telegram webhook")
        return False


async def get_webhook_info() -> dict | None:
    """Get current webhook info."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_api_url("getWebhookInfo"))
            resp.raise_for_status()
            return resp.json().get("result")
    except Exception:
        logger.exception("Error getting webhook info")
        return None
