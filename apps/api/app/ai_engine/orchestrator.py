"""
AI Engine Orchestrator — Main pipeline that ties all components together.

Pipeline: FARO → context → guardrails → actions/RAG → respond → persist.
Supports multi-turn flows via conversation.pending_action (JSON state).
Entry point: process_message() called from Telegram webhook handler.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine import intent_router
from app.ai_engine.actions import ScheduleActions
from app.ai_engine.context_manager import ContextManager, ConversationContext
from app.ai_engine.guardrails import (
    GuardrailAction,
    evaluate as evaluate_guardrails,
    detect_urgency,
)
from app.ai_engine.intent_router import FaroBrief, Intent
from app.ai_engine.response_builder import generate_response
from app.models.conversation import Conversation
from app.models.patient import Patient
from app.services.conversation_service import ConversationService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


@dataclass
class EngineResponse:
    """Final output from the AI engine."""
    text: str
    intent: Intent
    confidence: float
    handoff_created: bool = False
    urgency_detected: bool = False
    guardrail_action: str = "allow"
    faro_brief: dict | None = None


class AIOrchestrator:
    """
    Main AI pipeline orchestrator.

    Steps:
    1. Check for pending multi-turn action (e.g. slot selection)
    2. FARO analysis (intent + entities)
    3. Build conversation context
    4. Pre-response guardrails (block injection, check consent)
    5. Execute real actions (schedule) or RAG query
    6. Generate response (LLM or template)
    7. Post-response guardrails (urgency, clinical, confidence)
    8. Handle handoff if needed
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.context_mgr = ContextManager(session)
        self.conv_svc = ConversationService(session)
        self.rag_svc = RagService(session)
        self.schedule_actions = ScheduleActions(session)

    async def process_message(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
    ) -> EngineResponse:
        # ── Step 0: Check pending multi-turn action ────────────
        pending = self._load_pending_action(conversation)
        if pending:
            result = await self._handle_pending_action(
                patient, conversation, user_text, pending
            )
            if result is not None:
                return result
            # If pending handler returned None, fall through to normal flow

        # ── Step 1: FARO analysis ──────────────────────────────
        faro = intent_router.analyze(user_text)
        logger.info(
            "FARO: intent=%s confidence=%.2f entities=%s",
            faro.intent.value, faro.confidence, faro.entities,
        )

        await self.conv_svc.update_intent(
            conversation.id, faro.intent.value, faro.confidence
        )

        # ── Step 2: Build context ──────────────────────────────
        context = await self.context_mgr.build_context(
            patient=patient,
            conversation=conversation,
            faro_brief=faro.to_dict(),
        )

        # ── Step 3: Pre-response guardrails ────────────────────
        pre_guard = evaluate_guardrails(
            user_text=user_text,
            ai_response="",
            confidence=faro.confidence,
            consented_ai=patient.consented_ai,
        )

        if pre_guard.action == GuardrailAction.BLOCK:
            return EngineResponse(
                text=pre_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                guardrail_action="block",
                faro_brief=faro.to_dict(),
            )

        if pre_guard.action == GuardrailAction.FORCE_HANDOFF and pre_guard.reason == "no_ai_consent":
            await self._create_handoff(
                conversation.id, user_text, faro, reason="no_ai_consent"
            )
            return EngineResponse(
                text=pre_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                handoff_created=True,
                guardrail_action="force_handoff",
                faro_brief=faro.to_dict(),
            )

        # ── Step 4: Execute real actions ───────────────────────
        action_response = await self._execute_action(patient, conversation, faro)
        if action_response is not None:
            post_guard = evaluate_guardrails(
                user_text=user_text,
                ai_response=action_response,
                confidence=1.0,  # action responses bypass confidence check
                consented_ai=patient.consented_ai,
            )
            return EngineResponse(
                text=post_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                urgency_detected=post_guard.urgency_detected,
                guardrail_action=post_guard.action.value,
                faro_brief=faro.to_dict(),
            )

        # ── Step 5: RAG query (operational questions) ──────────
        rag_results = None
        if faro.intent in (Intent.DUVIDA_OPERACIONAL, Intent.POLITICAS):
            rag_results = await self._query_rag(user_text)

        # ── Step 6: Generate response ──────────────────────────
        raw_response = await generate_response(
            context=context,
            user_text=user_text,
            faro=faro,
            rag_results=rag_results,
        )

        # ── Step 7: Post-response guardrails ───────────────────
        effective_confidence = (
            faro.confidence if faro.intent == Intent.DESCONHECIDA
            else max(faro.confidence, 0.80)
        )
        post_guard = evaluate_guardrails(
            user_text=user_text,
            ai_response=raw_response,
            confidence=effective_confidence,
            consented_ai=patient.consented_ai,
        )

        final_text = post_guard.modified_response
        handoff_created = False

        if post_guard.action == GuardrailAction.FORCE_HANDOFF:
            await self._create_handoff(
                conversation.id, user_text, faro, reason=post_guard.reason or "low_confidence"
            )
            handoff_created = True
            final_text = post_guard.modified_response

        # Explicit handoff request
        if faro.intent == Intent.FALAR_COM_HUMANO and not handoff_created:
            priority = "urgent" if detect_urgency(user_text) else "normal"
            await self._create_handoff(
                conversation.id, user_text, faro, reason="patient_request", priority=priority
            )
            handoff_created = True

        return EngineResponse(
            text=final_text,
            intent=faro.intent,
            confidence=faro.confidence,
            handoff_created=handoff_created,
            urgency_detected=post_guard.urgency_detected,
            guardrail_action=post_guard.action.value,
            faro_brief=faro.to_dict(),
        )

    # ─── Multi-turn state management ──────────────────────────

    def _load_pending_action(self, conversation: Conversation) -> dict | None:
        """Load pending action from conversation state."""
        if not conversation.pending_action:
            return None
        try:
            return json.loads(conversation.pending_action)
        except (json.JSONDecodeError, TypeError):
            return None

    async def _save_pending_action(
        self, conversation: Conversation, action: dict | None
    ) -> None:
        """Save or clear pending action state."""
        conversation.pending_action = json.dumps(action) if action else None
        self.session.add(conversation)
        await self.session.commit()

    async def _handle_pending_action(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        """Handle a user response to a pending multi-turn action."""
        action_type = pending.get("type")

        if action_type == "select_slot":
            return await self._handle_slot_selection(
                patient, conversation, user_text, pending
            )

        if action_type == "confirm_cancel":
            return await self._handle_cancel_confirmation(
                patient, conversation, user_text, pending
            )

        # Unknown pending action — clear it and fall through
        await self._save_pending_action(conversation, None)
        return None

    async def _handle_slot_selection(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        """Handle user picking a slot number (1, 2, 3, etc.)."""
        text = user_text.strip()

        # Detect explicit cancellation of the flow
        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in text.lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! O agendamento foi cancelado. Posso ajudar com algo mais?",
                intent=Intent.AGENDAR,
                confidence=1.0,
                guardrail_action="allow",
            )

        # Extract number from response
        slot_number = self._extract_number(text)
        slot_ids = pending.get("slot_ids", [])

        if slot_number is None or slot_number < 1 or slot_number > len(slot_ids):
            return EngineResponse(
                text=f"Por favor, responda com um número de 1 a {len(slot_ids)}, "
                     f"ou diga 'cancelar' para desistir.",
                intent=Intent.CONFIRMACAO,
                confidence=1.0,
                guardrail_action="allow",
            )

        # Book the selected slot
        selected_id = uuid.UUID(slot_ids[slot_number - 1])
        result = await self.schedule_actions.book_slot(
            selected_id, patient.id, source="telegram"
        )

        # Clear pending action regardless of result
        await self._save_pending_action(conversation, None)

        return EngineResponse(
            text=result.message,
            intent=Intent.AGENDAR,
            confidence=1.0,
            guardrail_action="allow",
        )

    async def _handle_cancel_confirmation(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        """Handle user confirming a cancellation."""
        text = user_text.strip().lower()
        faro = intent_router.analyze(user_text)

        # If user confirms
        if faro.confirmation_detected or text in ("sim", "s", "confirmo", "pode"):
            slot_id = pending.get("slot_id")
            if slot_id:
                result = await self.schedule_actions.cancel_slot(
                    patient.id, slot_id=uuid.UUID(slot_id)
                )
                await self._save_pending_action(conversation, None)
                return EngineResponse(
                    text=result.message,
                    intent=Intent.CANCELAR,
                    confidence=1.0,
                    guardrail_action="allow",
                )

        # If user declines
        if any(w in text for w in ["nao", "não", "cancelar", "desistir"]):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Ok, a consulta foi mantida. Posso ajudar com algo mais?",
                intent=Intent.CANCELAR,
                confidence=1.0,
                guardrail_action="allow",
            )

        return EngineResponse(
            text="Por favor, confirme com 'sim' ou 'não'.",
            intent=Intent.CONFIRMACAO,
            confidence=1.0,
            guardrail_action="allow",
        )

    def _extract_number(self, text: str) -> int | None:
        """Extract a number from user text (handles '1', 'opção 1', 'primeiro', etc.)."""
        # Direct number
        match = re.search(r"\b(\d+)\b", text)
        if match:
            return int(match.group(1))

        # Ordinals
        ordinals = {
            "primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2,
            "terceiro": 3, "terceira": 3, "quarto": 4, "quarta": 4,
            "quinto": 5, "quinta": 5,
        }
        text_lower = text.lower()
        for word, num in ordinals.items():
            if word in text_lower:
                return num

        return None

    # ─── Action execution ─────────────────────────────────────

    async def _execute_action(
        self, patient: Patient, conversation: Conversation, faro: FaroBrief
    ) -> str | None:
        """Execute real schedule actions based on FARO intent + entities."""
        entities = faro.entities

        if faro.intent == Intent.AGENDAR:
            if entities.get("doctor_name") or entities.get("date"):
                result = await self.schedule_actions.search_slots(
                    specialty=None,
                    doctor_name=entities.get("doctor_name"),
                    date_str=entities.get("date"),
                    time_str=entities.get("time"),
                )
                # If slots found, save them as pending action for selection
                if result.success and result.slots:
                    await self._save_pending_action(conversation, {
                        "type": "select_slot",
                        "slot_ids": [str(s.slot_id) for s in result.slots],
                    })
                return result.message
            return None

        if faro.intent == Intent.CANCELAR:
            # First try to find the appointment
            appointments = await self.schedule_actions.list_patient_appointments(patient.id)
            if appointments.slots and len(appointments.slots) == 1:
                # Single appointment — ask for confirmation
                slot = appointments.slots[0]
                await self._save_pending_action(conversation, {
                    "type": "confirm_cancel",
                    "slot_id": str(slot.slot_id),
                })
                return (
                    f"Encontrei sua consulta:\n\n"
                    f"📅 {slot.display()}\n\n"
                    f"Deseja realmente cancelar? Responda 'sim' ou 'não'."
                )
            if appointments.slots and len(appointments.slots) > 1:
                # Multiple — ask which one
                lines = ["Você tem mais de uma consulta agendada:\n"]
                slot_ids = []
                for i, s in enumerate(appointments.slots, 1):
                    lines.append(f"{i}️⃣ {s.display()}")
                    slot_ids.append(str(s.slot_id))
                lines.append("\nQual deseja cancelar? Responda com o número.")
                await self._save_pending_action(conversation, {
                    "type": "select_slot_to_cancel",
                    "slot_ids": slot_ids,
                })
                return "\n".join(lines)
            # No appointments found
            result = await self.schedule_actions.cancel_slot(
                patient_id=patient.id,
                date_str=entities.get("date"),
            )
            return result.message

        if faro.intent == Intent.REMARCAR:
            result = await self.schedule_actions.reschedule_slot(
                patient_id=patient.id,
                old_date_str=entities.get("date"),
                new_date_str=entities.get("date"),
            )
            if result.success and result.slots:
                await self._save_pending_action(conversation, {
                    "type": "select_slot",
                    "slot_ids": [str(s.slot_id) for s in result.slots],
                })
            return result.message

        if faro.intent == Intent.CONFIRMACAO:
            # Generic confirmation without pending action — no-op
            return None

        if faro.intent == Intent.LISTAR_ESPECIALIDADES:
            profs = await self.schedule_actions._find_professionals(None, None)
            if profs:
                specialties = sorted(set(p.specialty for p in profs))
                lines = ["Temos as seguintes especialidades disponíveis:\n"]
                for s in specialties:
                    lines.append(f"  • {s}")
                lines.append("\nQual especialidade deseja?")
                return "\n".join(lines)
            return "No momento não há especialidades cadastradas no sistema."

        return None

    async def _query_rag(self, text: str) -> list[dict] | None:
        """Query RAG for operational information. Falls back to text search."""
        try:
            results = await self.rag_svc.query(text)
            if results:
                return [
                    {
                        "content": r.content,
                        "document_title": r.document_title,
                        "score": r.score,
                    }
                    for r in results
                ]
        except Exception:
            logger.debug("Vector RAG query failed, trying text search")

        try:
            results = await self.rag_svc.text_search(text)
            if results:
                return results
        except Exception:
            logger.exception("RAG text search also failed for: %s", text[:80])

        return None

    async def _create_handoff(
        self,
        conversation_id: uuid.UUID,
        user_text: str,
        faro: FaroBrief,
        *,
        reason: str = "low_confidence",
        priority: str = "normal",
    ) -> None:
        if detect_urgency(user_text):
            priority = "urgent"

        context_summary = (
            f"Intent: {faro.intent.value} (conf: {faro.confidence})\n"
            f"Entities: {json.dumps(faro.entities, ensure_ascii=False)}\n"
            f"Last message: {user_text[:500]}"
        )

        try:
            await self.conv_svc.create_handoff(
                conversation_id=conversation_id,
                reason=reason,
                priority=priority,
                context_summary=context_summary,
            )
        except Exception:
            logger.exception("Failed to create handoff for conversation %s", conversation_id)
