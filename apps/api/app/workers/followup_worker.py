"""
FollowUp Worker — asyncio background task that processes overdue follow-ups.

Runs inside the FastAPI lifespan as a persistent background task.
Checks for overdue follow-ups every FOLLOWUP_WORKER_INTERVAL_MINUTES and:

  1. Escalates overdue items to alerts (so operators can see them in CRM).
  2. Logs the event for audit trail.

Not a replacement for a full job queue (ARQ/Celery) — intentionally minimal.
The architecture slot is already reserved in models/jobs.py and crm_service.py.
When the system needs real async dispatch (SMS, email, webhook), swap the body
of _process_overdue() with actual transport calls.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.db import async_session_factory
from app.services.crm_service import CrmService

logger = logging.getLogger(__name__)

# How often to poll for overdue items (seconds). Configurable via env.
_POLL_INTERVAL: int = getattr(settings, "followup_worker_interval_seconds", 300)  # 5 min


async def _process_overdue() -> None:
    """Check for overdue follow-ups and escalate each one to an alert."""
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        svc = CrmService(session)

        # Fetch all follow-ups due strictly before now (i.e. already overdue)
        overdue = await svc.list_pending_followups(due_before=now, limit=100)

        if not overdue:
            return

        logger.info("[WORKER] %d overdue follow-up(s) found — escalating to alerts", len(overdue))

        for fu in overdue:
            try:
                # Create an alert so the operator sees it in the CRM Alerts tab
                await svc.create_alert(
                    patient_id=fu.patient_id,
                    message=(
                        f"Follow-up '{fu.followup_type.value}' vencido em "
                        f"{fu.scheduled_at.strftime('%d/%m %H:%M')}. "
                        f"Notas: {fu.notes or 'nenhuma'}"
                    ),
                    alert_type="followup_overdue",
                    # Use the enum value from AlertPriority
                )
                logger.info(
                    "[WORKER] alert created for overdue follow-up id=%s patient_id=%s",
                    fu.id, fu.patient_id,
                )
            except Exception:
                logger.exception(
                    "[WORKER] failed to escalate follow-up id=%s", fu.id
                )


async def run_followup_worker() -> None:
    """
    Long-running background task. Call once from the FastAPI lifespan.
    Polls every _POLL_INTERVAL seconds. Exits cleanly on CancelledError.
    """
    logger.info(
        "[WORKER] FollowupWorker started — poll interval=%ds", _POLL_INTERVAL
    )
    while True:
        try:
            await _process_overdue()
        except asyncio.CancelledError:
            logger.info("[WORKER] FollowupWorker cancelled — shutting down")
            return
        except Exception:
            logger.exception("[WORKER] Unexpected error in follow-up worker — continuing")

        try:
            await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            logger.info("[WORKER] FollowupWorker cancelled during sleep — shutting down")
            return
