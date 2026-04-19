"""
Telegram Webhook Handler — processes incoming Telegram updates.

Full flow:
1. Receive update from Telegram
2. Extract message, user_id, chat_id
3. Locate or create patient
4. Get or create conversation
5. Record inbound message
6. Run AI engine pipeline (FARO → context → guardrails → respond)
7. Send response back via Telegram
8. Record outbound message
9. Log audit events
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.orchestrator import AIOrchestrator
from app.integrations.telegram.client import send_message
from app.schemas.telegram import TelegramUpdate
from app.services.audit_service import AuditService
from app.services.conversation_service import ConversationService
from app.services.patient_service import PatientService

logger = logging.getLogger(__name__)


async def handle_telegram_update(update: TelegramUpdate, session: AsyncSession) -> None:
    """Process a single Telegram update end-to-end."""

    if not update.has_text:
        logger.debug("Ignoring non-text update %d", update.update_id)
        return

    user_id = update.user_id
    chat_id = update.chat_id
    text = update.text
    first_name = update.user_first_name or "Paciente"

    if not user_id or not chat_id or not text:
        logger.warning("Incomplete update: %d", update.update_id)
        return

    logger.info(
        "[TELEGRAM:INBOUND] update_id=%d user=%s chat=%s text=%r",
        update.update_id, user_id, chat_id, text[:120],
    )

    # 1. Get or create patient
    patient_svc = PatientService(session)
    patient = await patient_svc.get_or_create_from_telegram(user_id, chat_id, first_name)

    # 2. Get or create conversation
    conv_svc = ConversationService(session)
    conversation = await conv_svc.get_or_create(patient.id, channel="telegram")

    # 3. Record inbound message
    await conv_svc.add_message(
        conversation_id=conversation.id,
        direction="inbound",
        content=text,
        raw_payload=json.dumps(update.model_dump(), default=str),
    )

    # 4. Run AI engine pipeline
    orchestrator = AIOrchestrator(session)
    result = await orchestrator.process_message(
        patient=patient,
        conversation=conversation,
        user_text=text,
    )

    logger.info(
        "[TELEGRAM] Resultado do engine | intent=%s confidence=%.2f guardrail=%s handoff=%s resposta=%r",
        result.intent.value, result.confidence,
        result.guardrail_action, result.handoff_created,
        result.text[:120],
    )

    # 5. Send response back to Telegram
    await send_message(chat_id, result.text)

    # 6. Record outbound message
    await conv_svc.add_message(
        conversation_id=conversation.id,
        direction="outbound",
        content=result.text,
    )

    # 7. Audit
    audit = AuditService(session)
    await audit.log_event(
        actor_type="ai",
        actor_id="telegram_webhook",
        action="message.processed",
        resource_type="conversation",
        resource_id=str(conversation.id),
        payload={
            "intent": result.intent.value,
            "confidence": result.confidence,
            "handoff": result.handoff_created,
            "urgency": result.urgency_detected,
            "guardrail": result.guardrail_action,
            "telegram_user_id": user_id,
            "faro_brief": result.faro_brief,
        },
    )
