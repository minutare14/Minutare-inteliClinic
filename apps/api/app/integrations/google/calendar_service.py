"""
GoogleCalendarService — token management + calendar operations.

Stores OAuth tokens in ClinicSettings.google_calendar_token (JSON string).
Auto-refreshes expired access tokens using the stored refresh_token.

Usage (from a route or service):
    svc = GoogleCalendarService(session)
    if not svc.is_connected():
        raise HTTPException(400, "Google Calendar not connected")

    events = await svc.list_upcoming_events(days_ahead=7)
    event = await svc.create_appointment(slot)
    await svc.delete_appointment(slot.google_event_id)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.google.calendar_client import CalendarEvent, GoogleCalendarClient
from app.integrations.google.oauth import (
    exchange_code,
    is_configured,
    refresh_access_token,
    revoke_token,
)
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

# Safety margin: refresh the token 5 minutes before actual expiry
_REFRESH_MARGIN_SECONDS = 300


class GoogleCalendarService:
    """High-level calendar operations with token lifecycle management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._admin = AdminService(session)

    # ── Token management ──────────────────────────────────────────────────────

    def google_configured(self) -> bool:
        return is_configured()

    async def get_tokens(self) -> dict[str, Any] | None:
        """Load stored OAuth tokens from ClinicSettings (reads the ORM model directly)."""
        obj = await self._admin._get_or_seed_clinic_settings()
        raw = obj.google_calendar_token
        if not raw:
            return None
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    async def save_tokens(self, tokens: dict[str, Any]) -> None:
        """Persist tokens back into ClinicSettings.google_calendar_token."""
        clinic_obj = await self._admin._get_or_seed_clinic_settings()
        clinic_obj.google_calendar_token = json.dumps(tokens) if tokens else None
        self._admin.repo.session.add(clinic_obj)
        await self._admin.repo.session.commit()
        logger.debug("[GCAL_SVC] tokens saved to ClinicSettings")

    async def is_connected(self) -> bool:
        """Return True if valid tokens are stored."""
        tokens = await self.get_tokens()
        return tokens is not None and bool(tokens.get("refresh_token"))

    async def disconnect(self) -> None:
        """Revoke tokens and clear from ClinicSettings."""
        tokens = await self.get_tokens()
        if tokens:
            token_to_revoke = tokens.get("access_token") or tokens.get("refresh_token")
            if token_to_revoke:
                try:
                    await revoke_token(token_to_revoke)
                except Exception:
                    logger.warning("[GCAL_SVC] revocation failed — clearing locally anyway")
        await self.save_tokens({})
        logger.info("[GCAL_SVC] disconnected")

    # ── OAuth flow ────────────────────────────────────────────────────────────

    async def handle_callback(self, code: str) -> None:
        """Exchange authorization code for tokens and store them."""
        tokens = await exchange_code(code)
        tokens["stored_at"] = time.time()
        await self.save_tokens(tokens)
        logger.info("[GCAL_SVC] OAuth callback handled — connected")

    # ── Token refresh ─────────────────────────────────────────────────────────

    async def _get_valid_access_token(self) -> str:
        """Return a valid access_token, refreshing if necessary."""
        tokens = await self.get_tokens()
        if not tokens:
            raise RuntimeError("Google Calendar not connected")

        stored_at = tokens.get("stored_at", 0)
        expires_in = tokens.get("expires_in", 3600)
        age = time.time() - stored_at

        if age < (expires_in - _REFRESH_MARGIN_SECONDS):
            return tokens["access_token"]

        # Token expired — refresh
        refresh_tok = tokens.get("refresh_token")
        if not refresh_tok:
            raise RuntimeError("No refresh_token stored — user must re-authorize")

        logger.info("[GCAL_SVC] access_token expired — refreshing")
        new_tokens = await refresh_access_token(refresh_tok)
        new_tokens["refresh_token"] = refresh_tok  # preserve refresh token
        new_tokens["stored_at"] = time.time()
        await self.save_tokens(new_tokens)
        return new_tokens["access_token"]

    def _client(self, access_token: str) -> GoogleCalendarClient:
        return GoogleCalendarClient(access_token)

    # ── Calendar operations ───────────────────────────────────────────────────

    async def list_upcoming_events(
        self,
        calendar_id: str = "primary",
        days_ahead: int = 7,
        max_results: int = 50,
    ) -> list[CalendarEvent]:
        token = await self._get_valid_access_token()
        now = datetime.now(timezone.utc)
        return await self._client(token).list_events(
            calendar_id=calendar_id,
            time_min=now,
            time_max=now + timedelta(days=days_ahead),
            max_results=max_results,
        )

    async def create_appointment(
        self,
        summary: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str | None = None,
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        token = await self._get_valid_access_token()
        return await self._client(token).create_event(
            calendar_id=calendar_id,
            summary=summary,
            start_dt=start_dt,
            end_dt=end_dt,
            description=description,
            attendees=attendees or [],
        )

    async def delete_appointment(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> None:
        token = await self._get_valid_access_token()
        await self._client(token).delete_event(calendar_id=calendar_id, event_id=event_id)
