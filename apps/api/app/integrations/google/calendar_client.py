"""
Google Calendar client — create, list, update, delete events.

Uses the Google Calendar REST API v3 directly via httpx.
No Google SDK dependency — only httpx (already in the stack).

Usage:
    client = GoogleCalendarClient(access_token="ya29.xxx")

    # List upcoming events
    events = await client.list_events(calendar_id="primary", max_results=10)

    # Create an appointment slot
    event = await client.create_event(
        calendar_id="primary",
        summary="Consulta Dr. Silva — João Santos",
        start_dt=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_dt=datetime(2026, 5, 1, 9, 30, tzinfo=timezone.utc),
        description="Agendado via IntelliClinic",
        attendees=["paciente@example.com"],
    )

    # Delete an event
    await client.delete_event(calendar_id="primary", event_id=event["id"])

Token refresh:
    The caller is responsible for refreshing the access_token before calling methods.
    Use app.integrations.google.oauth.refresh_access_token() if the token has expired
    (typically expires in 3600 s). The GoogleCalendarService wraps this logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/calendar/v3"


@dataclass
class CalendarEvent:
    """Minimal representation of a Google Calendar event."""
    id: str
    summary: str
    start: str        # ISO 8601 datetime string
    end: str
    description: str | None = None
    attendees: list[str] = field(default_factory=list)
    html_link: str | None = None
    status: str = "confirmed"


class GoogleCalendarClient:
    """
    Async Google Calendar v3 REST client.

    Args:
        access_token: A valid OAuth2 access token. Caller must refresh if expired.
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ── Calendars ─────────────────────────────────────────────────────────────

    async def list_calendars(self) -> list[dict[str, Any]]:
        """List all calendars in the user's calendar list."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_BASE}/users/me/calendarList",
                headers=self._headers,
            )
            self._raise(resp)
        return resp.json().get("items", [])

    # ── Events ────────────────────────────────────────────────────────────────

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 50,
        query: str | None = None,
    ) -> list[CalendarEvent]:
        """
        List events from a calendar.

        Args:
            calendar_id: Google Calendar ID (use "primary" for the main calendar).
            time_min:    Only return events starting at or after this datetime.
            time_max:    Only return events starting before this datetime.
            max_results: Maximum number of events to return (1–2500).
            query:       Free-text search across event fields.
        """
        params: dict[str, Any] = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if time_min:
            params["timeMin"] = _iso(time_min)
        if time_max:
            params["timeMax"] = _iso(time_max)
        if query:
            params["q"] = query

        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_BASE}/calendars/{_enc(calendar_id)}/events",
                headers=self._headers,
                params=params,
            )
            self._raise(resp)

        return [_parse_event(e) for e in resp.json().get("items", [])]

    async def get_event(self, calendar_id: str, event_id: str) -> CalendarEvent:
        """Fetch a single event by ID."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_BASE}/calendars/{_enc(calendar_id)}/events/{event_id}",
                headers=self._headers,
            )
            self._raise(resp)
        return _parse_event(resp.json())

    async def create_event(
        self,
        calendar_id: str = "primary",
        summary: str = "",
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        description: str | None = None,
        attendees: list[str] | None = None,
        send_updates: str = "none",
    ) -> CalendarEvent:
        """
        Create a new calendar event.

        Args:
            calendar_id:   Target calendar (default: "primary").
            summary:       Event title.
            start_dt:      Start time (timezone-aware recommended).
            end_dt:        End time.
            description:   Optional body text.
            attendees:     List of email addresses to invite.
            send_updates:  "all" | "externalOnly" | "none" (default none → no emails).
        """
        if not start_dt or not end_dt:
            raise ValueError("start_dt and end_dt are required")

        body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": _iso(start_dt), "timeZone": "UTC"},
            "end": {"dateTime": _iso(end_dt), "timeZone": "UTC"},
        }
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{_BASE}/calendars/{_enc(calendar_id)}/events",
                headers=self._headers,
                json=body,
                params={"sendUpdates": send_updates},
            )
            self._raise(resp)

        event = _parse_event(resp.json())
        logger.info(
            "[GCAL] event created calendar=%s event_id=%s summary=%r",
            calendar_id, event.id, summary,
        )
        return event

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        description: str | None = None,
        send_updates: str = "none",
    ) -> CalendarEvent:
        """Patch an existing event (only supplied fields are changed)."""
        patch: dict[str, Any] = {}
        if summary is not None:
            patch["summary"] = summary
        if start_dt is not None:
            patch["start"] = {"dateTime": _iso(start_dt), "timeZone": "UTC"}
        if end_dt is not None:
            patch["end"] = {"dateTime": _iso(end_dt), "timeZone": "UTC"}
        if description is not None:
            patch["description"] = description

        async with httpx.AsyncClient() as http:
            resp = await http.patch(
                f"{_BASE}/calendars/{_enc(calendar_id)}/events/{event_id}",
                headers=self._headers,
                json=patch,
                params={"sendUpdates": send_updates},
            )
            self._raise(resp)

        event = _parse_event(resp.json())
        logger.info("[GCAL] event updated event_id=%s", event_id)
        return event

    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        send_updates: str = "none",
    ) -> None:
        """Delete a calendar event by ID."""
        async with httpx.AsyncClient() as http:
            resp = await http.delete(
                f"{_BASE}/calendars/{_enc(calendar_id)}/events/{event_id}",
                headers=self._headers,
                params={"sendUpdates": send_updates},
            )
            if resp.status_code == 404:
                logger.warning("[GCAL] event not found on delete event_id=%s", event_id)
                return
            self._raise(resp)
        logger.info("[GCAL] event deleted event_id=%s", event_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _raise(resp: httpx.Response) -> None:
        if resp.is_success:
            return
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        logger.error("[GCAL] API error %d: %s", resp.status_code, detail)
        resp.raise_for_status()


# ── Module-level helpers ───────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    """Format a datetime as RFC 3339 / ISO 8601 string expected by Google."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _enc(calendar_id: str) -> str:
    """URL-encode a calendar ID (primary stays as-is)."""
    if calendar_id == "primary":
        return "primary"
    from urllib.parse import quote
    return quote(calendar_id, safe="")


def _parse_event(data: dict[str, Any]) -> CalendarEvent:
    """Parse a Google Calendar event dict into a CalendarEvent dataclass."""
    start = data.get("start", {})
    end = data.get("end", {})
    return CalendarEvent(
        id=data.get("id", ""),
        summary=data.get("summary", ""),
        start=start.get("dateTime") or start.get("date", ""),
        end=end.get("dateTime") or end.get("date", ""),
        description=data.get("description"),
        attendees=[a["email"] for a in data.get("attendees", []) if "email" in a],
        html_link=data.get("htmlLink"),
        status=data.get("status", "confirmed"),
    )
