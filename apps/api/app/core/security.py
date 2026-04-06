from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings


def verify_telegram_webhook(token: str) -> bool:
    """Validate incoming Telegram webhook secret header."""
    if not settings.telegram_webhook_secret:
        return True  # skip in dev if not set
    return hmac.compare_digest(token, settings.telegram_webhook_secret)


def hash_sensitive(value: str) -> str:
    """One-way hash for logging sensitive values (e.g. CPF last digits)."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]
