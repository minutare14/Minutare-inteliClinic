"""
Google Calendar routes — OAuth2 connect/disconnect + event listing.

Endpoints:
    GET  /google/auth        — get the authorization URL (admin only)
    GET  /google/callback    — OAuth2 callback (exchange code → store tokens)
    GET  /google/status      — connection status + upcoming events
    POST /google/disconnect  — revoke + clear stored tokens
    GET  /google/events      — list upcoming events

Flow:
    1. Admin clicks "Connect Google Calendar" → frontend calls GET /google/auth
    2. Redirect user to auth_url
    3. Google redirects to GOOGLE_REDIRECT_URI → GET /google/callback?code=...
    4. Tokens stored in ClinicSettings
    5. All subsequent calendar operations use stored tokens
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.db import get_session
from app.integrations.google.calendar_service import GoogleCalendarService
from app.integrations.google.oauth import get_authorization_url, is_configured
from app.models.auth import User, UserRole

router = APIRouter(prefix="/google", tags=["google"])

logger = logging.getLogger(__name__)

_ADMIN_ROLES = (UserRole.admin,)


@router.get("/auth")
async def get_auth_url(
    current_user: Annotated[User, Depends(require_roles(*_ADMIN_ROLES))],
):
    """Return the Google OAuth2 authorization URL. Admin only."""
    if not is_configured():
        raise HTTPException(
            status_code=400,
            detail=(
                "Google OAuth não configurado — defina GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET e GOOGLE_REDIRECT_URI no .env"
            ),
        )
    url, state = get_authorization_url()
    return {"auth_url": url, "state": state}


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(default=""),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """
    Google OAuth2 callback — exchanges the authorization code for tokens.

    Google redirects here after the user grants consent. The `code` param
    is exchanged for access + refresh tokens which are stored in ClinicSettings.

    On success, redirects the browser to the frontend /admin page.
    """
    if error:
        logger.warning("[GOOGLE_CALLBACK] OAuth error: %s", error)
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    try:
        svc = GoogleCalendarService(session)
        await svc.handle_callback(code)
    except Exception as exc:
        logger.exception("[GOOGLE_CALLBACK] token exchange failed")
        raise HTTPException(status_code=502, detail=f"Falha na autenticação: {exc}") from exc

    # Redirect browser back to the admin integrations page
    return RedirectResponse(url="/admin?google=connected", status_code=302)


@router.get("/status")
async def get_status(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Return Google Calendar connection status."""
    svc = GoogleCalendarService(session)
    connected = await svc.is_connected()
    return {
        "configured": is_configured(),
        "connected": connected,
    }


@router.post("/disconnect")
async def disconnect(
    current_user: Annotated[User, Depends(require_roles(*_ADMIN_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Revoke Google OAuth tokens and disconnect. Admin only."""
    svc = GoogleCalendarService(session)
    await svc.disconnect()
    return {"disconnected": True}


@router.get("/events")
async def list_events(
    days_ahead: int = 7,
    max_results: int = 20,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    """List upcoming Google Calendar events. Any authenticated user."""
    svc = GoogleCalendarService(session)
    if not await svc.is_connected():
        raise HTTPException(
            status_code=400,
            detail="Google Calendar não conectado — faça a autorização em Admin > Integrações",
        )
    try:
        events = await svc.list_upcoming_events(days_ahead=days_ahead, max_results=max_results)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[GOOGLE_EVENTS] list failed")
        raise HTTPException(status_code=502, detail=f"Erro ao listar eventos: {exc}") from exc

    return [
        {
            "id": e.id,
            "summary": e.summary,
            "start": e.start,
            "end": e.end,
            "description": e.description,
            "attendees": e.attendees,
            "html_link": e.html_link,
        }
        for e in events
    ]
