from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import verify_telegram_webhook
from app.integrations.telegram.webhook_handler import handle_telegram_update
from app.schemas.telegram import TelegramUpdate
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict:
    """Receive and process Telegram webhook updates."""
    # Validate webhook secret
    if x_telegram_bot_api_secret_token is not None:
        if not verify_telegram_webhook(x_telegram_bot_api_secret_token):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()

    try:
        update = TelegramUpdate.model_validate(body)
    except Exception:
        logger.exception("Failed to parse Telegram update")
        return {"ok": True}  # Return 200 to prevent Telegram retries

    await handle_telegram_update(update, session)
    return {"ok": True}


@router.post("/set-webhook")
async def set_webhook(url: str | None = None) -> dict:
    """Manually set the Telegram webhook URL."""
    svc = TelegramService()
    ok = await svc.set_webhook(url)
    return {"ok": ok}


@router.get("/webhook-info")
async def webhook_info() -> dict:
    """Get current Telegram webhook info."""
    svc = TelegramService()
    info = await svc.get_webhook_info()
    return {"info": info}
