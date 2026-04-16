"""
Google OAuth2 flow — authorization URL + token exchange.

Requirements in .env:
    GOOGLE_CLIENT_ID        — from Google Cloud Console (OAuth 2.0 Client)
    GOOGLE_CLIENT_SECRET    — same credential
    GOOGLE_REDIRECT_URI     — must match the URI registered in Cloud Console
                              e.g. https://api.yourdomain.com/api/v1/google/callback

Scopes granted:
    https://www.googleapis.com/auth/calendar — full calendar read/write
    https://www.googleapis.com/auth/userinfo.email — identify which account

Token storage:
    Tokens are stored in the DB (clinic_settings.google_calendar_token JSON field)
    via AdminService. On refresh, the new token overwrites the old one.

Usage:
    from app.integrations.google.oauth import get_authorization_url, exchange_code

    # 1. Redirect user to:
    url, state = get_authorization_url()

    # 2. Google redirects back to GOOGLE_REDIRECT_URI with ?code=...&state=...
    tokens = await exchange_code(code)
    # tokens = {"access_token": ..., "refresh_token": ..., "expires_in": ..., ...}
"""
from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def is_configured() -> bool:
    """Return True if Google OAuth credentials are set in the environment."""
    return bool(
        getattr(settings, "google_client_id", None)
        and getattr(settings, "google_client_secret", None)
        and getattr(settings, "google_redirect_uri", None)
    )


def get_authorization_url() -> tuple[str, str]:
    """
    Build the Google OAuth2 authorization URL.

    Returns (url, state) — the caller must store `state` in the session and
    verify it on the callback to prevent CSRF.
    """
    if not is_configured():
        raise RuntimeError(
            "Google OAuth not configured — set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI in .env"
        )

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",   # request refresh_token
        "prompt": "consent",        # always show consent to guarantee refresh_token
        "state": state,
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    logger.debug("[GOOGLE_OAUTH] authorization_url built state=%s", state)
    return url, state


async def exchange_code(code: str) -> dict[str, Any]:
    """
    Exchange an authorization code for access + refresh tokens.

    Returns the raw token response from Google:
        {
            "access_token": "...",
            "refresh_token": "...",   # only on first authorization
            "expires_in": 3599,
            "token_type": "Bearer",
            "scope": "...",
        }
    """
    if not is_configured():
        raise RuntimeError("Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

    logger.info("[GOOGLE_OAUTH] token exchange successful")
    return tokens


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """
    Use a stored refresh_token to get a new access_token.

    Returns the token response (same shape as exchange_code, without refresh_token).
    """
    if not is_configured():
        raise RuntimeError("Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

    logger.info("[GOOGLE_OAUTH] access_token refreshed")
    return tokens


async def revoke_token(token: str) -> None:
    """Revoke an access or refresh token (on disconnect)."""
    async with httpx.AsyncClient() as client:
        await client.post(_REVOKE_URL, params={"token": token})
    logger.info("[GOOGLE_OAUTH] token revoked")
