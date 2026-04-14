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
from app.ai_engine.response_composer import ResponseComposer
from app.core.config import settings
from app.models.conversation import Conversation
from app.models.patient import Patient
from app.repositories.admin_repository import AdminRepository
from app.services.audit_service import AuditService
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
        self.admin_repo = AdminRepository(session)
        self.audit_svc = AuditService(session)
        self.composer = ResponseComposer(self.rag_svc)

    async def process_message(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
    ) -> EngineResponse:
        # ── Step 0a: Load clinic settings from DB (with .env fallback) ────
        clinic_name: str | None = None
        chatbot_name: str | None = None
        custom_system_prompt: str | None = None
        rag_top_k_override: int | None = None
        insurance_context: str | None = None
        insurance_items: list = []
        specialties_override: list[str] | None = None

        handoff_enabled: bool = True
        handoff_confidence_threshold: float | None = None
        clinical_questions_block: bool = True

        try:
            clinic_cfg = await self.admin_repo.get_clinic_settings(settings.clinic_id)
            if clinic_cfg:
                clinic_name = clinic_cfg.name or None
                chatbot_name = clinic_cfg.chatbot_name or None
                rag_top_k_override = clinic_cfg.rag_top_k or None
                handoff_enabled = clinic_cfg.handoff_enabled
                handoff_confidence_threshold = clinic_cfg.handoff_confidence_threshold
                clinical_questions_block = clinic_cfg.clinical_questions_block
                logger.info(
                    "[ADMIN] ClinicSettings do banco: clinic='%s' bot='%s' handoff=%s",
                    clinic_name or "(vazio)", chatbot_name or "(vazio)", handoff_enabled,
                )
            else:
                logger.info(
                    "[ADMIN] ClinicSettings não encontrado no banco (clinic_id='%s') — usando .env",
                    settings.clinic_id,
                )

            # Load insurance catalog for LLM context
            insurance_items = await self.admin_repo.list_insurance(settings.clinic_id, active_only=True)
            if insurance_items:
                insurance_context = "Convênios aceitos: " + ", ".join(i.name for i in insurance_items)
                logger.info("[ADMIN] Insurance catalog: %d convênios ativos", len(insurance_items))

            # Load clinic specialties (DB override for FARO entity extraction)
            db_specialties = await self.admin_repo.list_specialties(settings.clinic_id, active_only=True)
            if db_specialties:
                specialties_override = [s.name for s in db_specialties]
                logger.info("[ADMIN] Specialties do banco: %d especialidades", len(db_specialties))

            # Load active prompt for response_builder agent
            active_prompt = await self.admin_repo.get_active_prompt(settings.clinic_id, "response_builder")
            if active_prompt:
                custom_system_prompt = active_prompt.content
                logger.info(
                    "[PROMPT] PromptRegistry ativo: '%s' v%d (agent=%s)",
                    active_prompt.name, active_prompt.version, active_prompt.agent,
                )
            else:
                logger.info("[PROMPT] Sem prompt ativo no PromptRegistry para agent='response_builder' — usando padrão")
        except Exception:
            logger.exception("[ADMIN] Falha ao carregar ClinicSettings/Prompts — usando defaults do .env")

        # ── Step 0b: Check pending multi-turn action ────────────
        pending = self._load_pending_action(conversation)
        if pending:
            result = await self._handle_pending_action(
                patient, conversation, user_text, pending
            )
            if result is not None:
                return result
            # If pending handler returned None, fall through to normal flow

        # ── Step 1: FARO analysis ──────────────────────────────
        faro = intent_router.analyze(user_text, specialties_override=specialties_override)
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
            handoff_enabled=handoff_enabled,
            handoff_confidence_threshold=handoff_confidence_threshold,
            clinical_questions_block=clinical_questions_block,
        )
        logger.info(
            "[GUARDRAIL-PRE] action=%s reason=%s consented_ai=%s confidence=%.2f",
            pre_guard.action.value, pre_guard.reason, patient.consented_ai, faro.confidence,
        )

        if pre_guard.action == GuardrailAction.BLOCK:
            logger.warning("[GUARDRAIL-PRE] BLOQUEADO — prompt injection detectado")
            return EngineResponse(
                text=pre_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                guardrail_action="block",
                faro_brief=faro.to_dict(),
            )

        if pre_guard.action == GuardrailAction.FORCE_HANDOFF and pre_guard.reason == "no_ai_consent":
            logger.warning(
                "[GUARDRAIL-PRE] HANDOFF por falta de consentimento — patient_id=%s",
                patient.id,
            )
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
        logger.info("[ACTION] action_response=%s", "sim" if action_response is not None else "nenhuma")
        if action_response is not None:
            post_guard = evaluate_guardrails(
                user_text=user_text,
                ai_response=action_response,
                confidence=1.0,  # action responses bypass confidence check
                consented_ai=patient.consented_ai,
                handoff_enabled=handoff_enabled,
                handoff_confidence_threshold=handoff_confidence_threshold,
                clinical_questions_block=clinical_questions_block,
            )
            return EngineResponse(
                text=post_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                urgency_detected=post_guard.urgency_detected,
                guardrail_action=post_guard.action.value,
                faro_brief=faro.to_dict(),
            )

        # ── Steps 5-6: RAG + Response via ResponseComposer ─────
        logger.info(
            "[COMPOSER] Compondo resposta — intent=%s custom_prompt=%s insurance=%s",
            faro.intent.value, bool(custom_system_prompt), bool(insurance_context),
        )
        composed = await self.composer.compose(
            context=context,
            faro=faro,
            user_text=user_text,
            clinic_name=clinic_name,
            chatbot_name=chatbot_name,
            custom_system_prompt=custom_system_prompt,
            insurance_context=insurance_context,
            rag_top_k=rag_top_k_override,
        )
        raw_response = composed.text
        rag_results = composed.rag_result_count > 0  # bool for audit payload
        logger.info("[COMPOSER] mode=%s rag=%s text=%r", composed.mode, composed.rag_used, raw_response[:120])

        # ── Step 7: Post-response guardrails ───────────────────
        effective_confidence = (
            faro.confidence if faro.intent == Intent.DESCONHECIDA
            else max(faro.confidence, 0.80)
        )
        logger.info(
            "[GUARDRAIL-POST] effective_confidence=%.2f (faro=%.2f intent=%s)",
            effective_confidence, faro.confidence, faro.intent.value,
        )
        post_guard = evaluate_guardrails(
            user_text=user_text,
            ai_response=raw_response,
            confidence=effective_confidence,
            consented_ai=patient.consented_ai,
            handoff_enabled=handoff_enabled,
            handoff_confidence_threshold=handoff_confidence_threshold,
            clinical_questions_block=clinical_questions_block,
        )

        final_text = post_guard.modified_response
        handoff_created = False

        if post_guard.action == GuardrailAction.FORCE_HANDOFF:
            if post_guard.reason == "low_confidence":
                # Não fazer handoff automático por baixa confiança — usar resposta de clarificação.
                # Handoff automático por confiança cria experiência ruim: o usuário fica sem resposta
                # em qualquer mensagem não reconhecida, incluindo continuações multi-turn.
                logger.info(
                    "[GUARDRAIL-POST] low_confidence (%.2f) — usando resposta de clarificação, sem handoff",
                    effective_confidence,
                )
                final_text = raw_response  # LLM ou template DESCONHECIDA já lida corretamente
            else:
                logger.warning(
                    "[GUARDRAIL-POST] HANDOFF — reason=%s confidence=%.2f",
                    post_guard.reason, effective_confidence,
                )
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

        # ── Step 8: Structured pipeline audit log ─────────────
        await self.audit_svc.log_event(
            actor_type="ai",
            actor_id="orchestrator",
            action="pipeline.completed",
            resource_type="conversation",
            resource_id=str(conversation.id),
            payload={
                "intent": faro.intent.value,
                "confidence": round(faro.confidence, 3),
                "guardrail": post_guard.action.value,
                "handoff_created": handoff_created,
                "rag_used": rag_results,
                "custom_prompt": bool(custom_system_prompt),
                "prompt_source": "db_registry" if custom_system_prompt else "env_default",
                "clinic_name_source": "db" if clinic_name else "env",
                "insurance_catalog_size": len(insurance_items),
                "specialties_source": "db" if specialties_override else "hardcoded",
                "response_mode": composed.mode,
            },
        )

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

        if action_type == "select_slot_to_cancel":
            return await self._handle_slot_to_cancel_selection(
                patient, conversation, user_text, pending
            )

        if action_type == "confirm_cancel":
            return await self._handle_cancel_confirmation(
                patient, conversation, user_text, pending
            )

        if action_type == "awaiting_schedule_date":
            return await self._handle_awaiting_schedule_date(
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

    async def _handle_slot_to_cancel_selection(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        """Handle user picking which appointment to cancel (multi-appointment flow)."""
        text = user_text.strip()

        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in text.lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! Nenhuma consulta foi cancelada. Posso ajudar com algo mais?",
                intent=Intent.CANCELAR,
                confidence=1.0,
                guardrail_action="allow",
            )

        slot_number = self._extract_number(text)
        slot_ids = pending.get("slot_ids", [])
        slot_displays = pending.get("slot_displays", [])

        if slot_number is None or slot_number < 1 or slot_number > len(slot_ids):
            return EngineResponse(
                text=f"Por favor, responda com um número de 1 a {len(slot_ids)}, "
                     f"ou diga 'cancelar' para desistir.",
                intent=Intent.CONFIRMACAO,
                confidence=1.0,
                guardrail_action="allow",
            )

        selected_id = slot_ids[slot_number - 1]
        display = (
            slot_displays[slot_number - 1]
            if slot_displays and slot_number <= len(slot_displays)
            else selected_id
        )

        await self._save_pending_action(conversation, {
            "type": "confirm_cancel",
            "slot_id": selected_id,
        })
        return EngineResponse(
            text=f"Você selecionou:\n\n📅 {display}\n\nDeseja realmente cancelar? Responda 'sim' ou 'não'.",
            intent=Intent.CANCELAR,
            confidence=1.0,
            guardrail_action="allow",
        )

    async def _handle_awaiting_schedule_date(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        """
        Handle follow-up message providing date/time for a pending scheduling request.
        Preserves specialty/doctor from previous turn.
        """
        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in user_text.strip().lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! Agendamento cancelado. Posso ajudar com algo mais?",
                intent=Intent.AGENDAR,
                confidence=1.0,
                guardrail_action="allow",
            )

        # Re-analyze the follow-up message to extract date/time
        faro = intent_router.analyze(user_text)
        date_str = faro.entities.get("date")
        time_str = faro.entities.get("time")

        # If still no date, prompt again
        if not date_str:
            return EngineResponse(
                text="Por favor, informe uma data. Exemplo: 'amanhã', 'segunda-feira' ou '20/04'.",
                intent=Intent.AGENDAR,
                confidence=1.0,
                guardrail_action="allow",
            )

        # Recover specialty/doctor from pending context
        specialty = pending.get("specialty")
        doctor_name = pending.get("doctor_name")

        logger.info(
            "[MULTI-TURN] Continuando agendamento — specialty=%s doctor=%s date=%s",
            specialty, doctor_name, date_str,
        )

        result = await self.schedule_actions.search_slots(
            specialty=specialty,
            doctor_name=doctor_name,
            date_str=date_str,
            time_str=time_str,
        )

        if result.success and result.slots:
            await self._save_pending_action(conversation, {
                "type": "select_slot",
                "slot_ids": [str(s.slot_id) for s in result.slots],
            })
        else:
            await self._save_pending_action(conversation, None)

        return EngineResponse(
            text=result.message,
            intent=Intent.AGENDAR,
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
            specialty = entities.get("specialty")
            doctor_name = entities.get("doctor_name")
            date_str = entities.get("date")
            time_str = entities.get("time")

            has_target = specialty or doctor_name

            if has_target and date_str:
                # Has both target (specialty/doctor) and date → search slots immediately
                result = await self.schedule_actions.search_slots(
                    specialty=specialty,
                    doctor_name=doctor_name,
                    date_str=date_str,
                    time_str=time_str,
                )
                if result.success and result.slots:
                    await self._save_pending_action(conversation, {
                        "type": "select_slot",
                        "slot_ids": [str(s.slot_id) for s in result.slots],
                    })
                return result.message

            if has_target and not date_str:
                # Has specialty/doctor but no date → ask for date and save context
                target_label = specialty or doctor_name
                await self._save_pending_action(conversation, {
                    "type": "awaiting_schedule_date",
                    "specialty": specialty,
                    "doctor_name": doctor_name,
                })
                logger.info("[ACTION] Aguardando data para agendar com %s", target_label)
                return (
                    f"Ótimo! Para agendar em {target_label}, qual data e horário você prefere? "
                    "Pode dizer 'amanhã', 'segunda às 10h', ou uma data específica."
                )

            if date_str and not has_target:
                # Has date but no specialty/doctor → ask for specialty
                return (
                    "Para qual especialidade ou médico você gostaria de agendar? "
                    "Por favor, informe a especialidade (ex: Ortopedia, Cardiologia)."
                )

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
                    "slot_displays": [s.display() for s in appointments.slots],
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
                new_date_str=entities.get("new_date", entities.get("date")),
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
