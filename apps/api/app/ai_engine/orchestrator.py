"""
AI Engine Orchestrator — Stage 3 pipeline with structured data lookup.

Pipeline nodes (in order):
  1.  ingest_message          — receives user_text, patient, conversation
  2.  load_runtime_context    — ClinicSettings + PromptRegistry + Insurance + Specialties
  3.  resolve_conversation_state — check pending multi-turn action
  4.  analyze_intent_and_entities — FARO (deterministic + entity extraction)
  5.  policy_guardrails        — pre-response: injection, consent
  6.  decision_router          — decides the route taken
  7.  route handlers:
        structured_data_lookup → direct answer from DB records (Priority 1)
        schedule_flow          → AGENDAR / CANCELAR / REMARCAR
        rag_retrieval + llm    → DUVIDA_OPERACIONAL / POLITICAS
        clarification_flow     → DESCONHECIDA / missing fields
        handoff_flow           → FALAR_COM_HUMANO / urgency / clinical
  8.  response_composer        — unified response assembly
  9.  post_guardrails          — urgency, clinical, confidence
  10. persist_and_audit        — structured log with full decision trace
  11. emit_response            — EngineResponse returned to webhook

Multi-turn state managed via conversation.pending_action (JSON).
Entry point: process_message() called from Telegram webhook handler.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field

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
from app.ai_engine.structured_lookup import StructuredLookup, LookupResult
from app.core.config import settings
from app.models.conversation import Conversation
from app.models.patient import Patient
from app.repositories.admin_repository import AdminRepository
from app.services.audit_service import AuditService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


# ─── Conversation State ───────────────────────────────────────────────────────

@dataclass
class ConversationState:
    """
    Explicit state tracking for the full pipeline run.
    Passed to audit log at the end.
    """
    # Runtime context sources
    clinic_name_source: str = "env"        # "db" | "env"
    prompt_source: str = "env_default"     # "db_registry" | "env_default"
    specialties_source: str = "hardcoded"  # "db" | "hardcoded"
    insurance_catalog_size: int = 0

    # FARO output
    intent: str = Intent.DESCONHECIDA.value
    confidence: float = 0.0
    entities: dict = field(default_factory=dict)

    # Route taken
    route: str = "unknown"                 # "structured_data" | "schedule" | "rag" | "llm" | "template" | "handoff" | "clarification"
    source_of_truth: str = "none"          # "professionals" | "insurance_catalog" | "clinic_settings" | "schedule_db" | "rag" | "llm" | "template"

    # Component flags
    structured_lookup_used: bool = False
    rag_used: bool = False
    tool_used: str | None = None           # "schedule_actions" | "rag_service" | None
    handoff_triggered: bool = False
    handoff_reason: str | None = None

    # Operational validity flags (live data checks)
    active_only_applied: bool = True       # professionals always filtered by active=True
    professionals_returned: int = 0        # number of professionals returned in lookup
    medical_availability_check: bool = False  # whether slot/professional validity was checked
    invalidated_schedule_detected: bool = False  # detected a booked slot with deactivated professional
    contingency_flow_triggered: bool = False     # contingency response was sent to patient
    patient_notification_required: bool = False  # patient needs notification (set by reconciliation)
    alternative_offered: bool = False            # alternative slot/doctor was offered

    # Guardrails
    guardrail_pre: str = "allow"
    guardrail_post: str = "allow"

    # Response mode
    response_mode: str = "unknown"


# ─── Engine Response ──────────────────────────────────────────────────────────

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
    route: str = "unknown"
    source_of_truth: str = "none"
    structured_lookup_used: bool = False
    rag_used: bool = False


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class AIOrchestrator:
    """
    Main AI pipeline orchestrator — Stage 3.

    Node map:
      load_runtime_context → resolve_conversation_state → analyze_intent_and_entities
      → policy_guardrails → decision_router →
          structured_data_lookup | schedule_flow | rag_retrieval | clarification_flow | handoff_flow
      → response_composer → post_guardrails → persist_and_audit → emit_response
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
        self.structured_lookup = StructuredLookup(session)

    async def process_message(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
    ) -> EngineResponse:

        state = ConversationState()

        # ══ NODE 1: load_runtime_context ════════════════════════════════════
        clinic_cfg = None
        clinic_name: str | None = None
        chatbot_name: str | None = None
        custom_system_prompt: str | None = None
        rag_top_k_override: int | None = None
        insurance_items: list = []
        insurance_context: str | None = None
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
                state.clinic_name_source = "db"
                logger.info(
                    "[NODE:load_runtime_context] ClinicSettings carregado: clinic='%s' bot='%s' handoff=%s",
                    clinic_name or "(vazio)", chatbot_name or "(vazio)", handoff_enabled,
                )
            else:
                logger.info(
                    "[NODE:load_runtime_context] ClinicSettings não encontrado (clinic_id='%s') — .env fallback",
                    settings.clinic_id,
                )

            insurance_items = await self.admin_repo.list_insurance(settings.clinic_id, active_only=True)
            if insurance_items:
                insurance_context = "Convênios aceitos: " + ", ".join(i.name for i in insurance_items)
                state.insurance_catalog_size = len(insurance_items)
                logger.info("[NODE:load_runtime_context] %d convênios ativos", len(insurance_items))

            db_specialties = await self.admin_repo.list_specialties(settings.clinic_id, active_only=True)
            if db_specialties:
                specialties_override = [s.name for s in db_specialties]
                state.specialties_source = "db"
                logger.info("[NODE:load_runtime_context] %d especialidades do banco", len(db_specialties))

            active_prompt = await self.admin_repo.get_active_prompt(settings.clinic_id, "response_builder")
            if active_prompt:
                custom_system_prompt = active_prompt.content
                state.prompt_source = "db_registry"
                logger.info(
                    "[NODE:load_runtime_context] PromptRegistry ativo: '%s' v%d agent=%s",
                    active_prompt.name, active_prompt.version, active_prompt.agent,
                )
            else:
                logger.info(
                    "[NODE:load_runtime_context] Sem prompt ativo no PromptRegistry (agent='response_builder') — padrão",
                )
        except Exception:
            logger.exception("[NODE:load_runtime_context] Falha — usando defaults do .env")

        # ══ NODE 2: resolve_conversation_state (multi-turn) ═════════════════
        pending = self._load_pending_action(conversation)
        if pending:
            result = await self._handle_pending_action(patient, conversation, user_text, pending)
            if result is not None:
                state.route = "multi_turn"
                state.source_of_truth = "schedule_db"
                await self._audit(conversation, user_text, state, result)
                return result

        # ══ NODE 3: analyze_intent_and_entities (FARO) ══════════════════════
        faro = intent_router.analyze(user_text, specialties_override=specialties_override)
        state.intent = faro.intent.value
        state.confidence = faro.confidence
        state.entities = faro.entities

        logger.info(
            "[NODE:analyze_intent] intent=%s confidence=%.2f entities=%s",
            faro.intent.value, faro.confidence, faro.entities,
        )

        await self.conv_svc.update_intent(conversation.id, faro.intent.value, faro.confidence)

        # ══ NODE 4: build context ════════════════════════════════════════════
        context = await self.context_mgr.build_context(
            patient=patient,
            conversation=conversation,
            faro_brief=faro.to_dict(),
        )

        # ══ NODE 5: policy_guardrails (pre-response) ═════════════════════════
        pre_guard = evaluate_guardrails(
            user_text=user_text,
            ai_response="",
            confidence=faro.confidence,
            consented_ai=patient.consented_ai,
            handoff_enabled=handoff_enabled,
            handoff_confidence_threshold=handoff_confidence_threshold,
            clinical_questions_block=clinical_questions_block,
        )
        state.guardrail_pre = pre_guard.action.value
        logger.info(
            "[NODE:policy_guardrails] pre action=%s reason=%s consented=%s conf=%.2f",
            pre_guard.action.value, pre_guard.reason, patient.consented_ai, faro.confidence,
        )

        if pre_guard.action == GuardrailAction.BLOCK:
            state.route = "blocked"
            state.source_of_truth = "guardrails"
            resp = EngineResponse(
                text=pre_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                guardrail_action="block",
                faro_brief=faro.to_dict(),
                route=state.route,
                source_of_truth=state.source_of_truth,
            )
            await self._audit(conversation, user_text, state, resp)
            return resp

        if pre_guard.action == GuardrailAction.FORCE_HANDOFF and pre_guard.reason == "no_ai_consent":
            state.route = "handoff_flow"
            state.source_of_truth = "guardrails"
            state.handoff_triggered = True
            state.handoff_reason = "no_ai_consent"
            await self._create_handoff(conversation.id, user_text, faro, reason="no_ai_consent")
            resp = EngineResponse(
                text=pre_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                handoff_created=True,
                guardrail_action="force_handoff",
                faro_brief=faro.to_dict(),
                route=state.route,
                source_of_truth=state.source_of_truth,
            )
            await self._audit(conversation, user_text, state, resp)
            return resp

        # ══ NODE 6: decision_router → structured_data_lookup (Priority 1) ═══
        #
        # Before action execution or RAG, check if the question can be answered
        # directly from structured database records (professionals, insurance, address).
        # This prevents questions about specific doctors returning generic lists.
        #
        lookup_result: LookupResult | None = None
        try:
            lookup_result = await self.structured_lookup.lookup(
                user_text=user_text,
                faro=faro,
                clinic_cfg=clinic_cfg,
                insurance_items=insurance_items,
            )
        except Exception:
            logger.exception("[NODE:structured_data_lookup] Falha — continuando para próximo nó")

        if lookup_result and lookup_result.answered:
            state.route = "structured_data"
            state.source_of_truth = lookup_result.source
            state.structured_lookup_used = True
            state.tool_used = "structured_lookup"
            state.response_mode = "structured"

            logger.info(
                "[NODE:decision_router] route=structured_data source=%s",
                lookup_result.source,
            )

            # Apply post-guardrails on structured response
            post_guard = evaluate_guardrails(
                user_text=user_text,
                ai_response=lookup_result.text,
                confidence=1.0,
                consented_ai=patient.consented_ai,
                handoff_enabled=handoff_enabled,
                handoff_confidence_threshold=handoff_confidence_threshold,
                clinical_questions_block=clinical_questions_block,
            )
            state.guardrail_post = post_guard.action.value

            resp = EngineResponse(
                text=post_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                urgency_detected=post_guard.urgency_detected,
                guardrail_action=post_guard.action.value,
                faro_brief=faro.to_dict(),
                route=state.route,
                source_of_truth=state.source_of_truth,
                structured_lookup_used=True,
                rag_used=False,
            )
            await self._audit(conversation, user_text, state, resp)
            return resp

        # ══ NODE 7: schedule_flow (action intents) ══════════════════════════
        action_response = await self._execute_action(patient, conversation, faro)
        if action_response is not None:
            state.route = "schedule_flow"
            state.source_of_truth = "schedule_db"
            state.tool_used = "schedule_actions"
            state.response_mode = "action"

            logger.info("[NODE:decision_router] route=schedule_flow intent=%s", faro.intent.value)

            post_guard = evaluate_guardrails(
                user_text=user_text,
                ai_response=action_response,
                confidence=1.0,
                consented_ai=patient.consented_ai,
                handoff_enabled=handoff_enabled,
                handoff_confidence_threshold=handoff_confidence_threshold,
                clinical_questions_block=clinical_questions_block,
            )
            state.guardrail_post = post_guard.action.value

            resp = EngineResponse(
                text=post_guard.modified_response,
                intent=faro.intent,
                confidence=faro.confidence,
                urgency_detected=post_guard.urgency_detected,
                guardrail_action=post_guard.action.value,
                faro_brief=faro.to_dict(),
                route=state.route,
                source_of_truth=state.source_of_truth,
            )
            await self._audit(conversation, user_text, state, resp)
            return resp

        # ══ NODE 8: rag_retrieval + response_composer ════════════════════════
        logger.info(
            "[NODE:response_composer] intent=%s prompt_source=%s insurance=%s",
            faro.intent.value, state.prompt_source, bool(insurance_context),
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
        state.rag_used = composed.rag_used
        state.tool_used = "rag_service" if composed.rag_used else None
        state.response_mode = composed.mode

        if composed.rag_used:
            state.route = "rag_retrieval"
            state.source_of_truth = "rag"
        else:
            state.route = "llm" if composed.mode == "llm" else "clarification"
            state.source_of_truth = "llm" if composed.mode == "llm" else "template"

        logger.info(
            "[NODE:decision_router] route=%s mode=%s rag=%s text=%.120r",
            state.route, composed.mode, composed.rag_used, raw_response,
        )

        # ══ NODE 9: post_guardrails ═══════════════════════════════════════════
        effective_confidence = (
            faro.confidence if faro.intent == Intent.DESCONHECIDA
            else max(faro.confidence, 0.80)
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
        state.guardrail_post = post_guard.action.value

        final_text = post_guard.modified_response
        handoff_created = False

        if post_guard.action == GuardrailAction.FORCE_HANDOFF:
            if post_guard.reason == "low_confidence":
                # Don't auto-handoff on low confidence — use clarification response instead.
                # Automatic handoff on unknown messages creates bad UX.
                logger.info(
                    "[NODE:post_guardrails] low_confidence=%.2f — clarification response (sem handoff)",
                    effective_confidence,
                )
                final_text = raw_response
            else:
                logger.warning(
                    "[NODE:post_guardrails] HANDOFF reason=%s conf=%.2f",
                    post_guard.reason, effective_confidence,
                )
                await self._create_handoff(conversation.id, user_text, faro, reason=post_guard.reason or "")
                handoff_created = True
                state.handoff_triggered = True
                state.handoff_reason = post_guard.reason
                state.route = "handoff_flow"

        # Explicit handoff request from patient
        if faro.intent == Intent.FALAR_COM_HUMANO and not handoff_created:
            priority = "urgent" if detect_urgency(user_text) else "normal"
            await self._create_handoff(conversation.id, user_text, faro, reason="patient_request", priority=priority)
            handoff_created = True
            state.handoff_triggered = True
            state.handoff_reason = "patient_request"
            state.route = "handoff_flow"

        # ══ NODE 10: persist_and_audit ════════════════════════════════════════
        final_resp = EngineResponse(
            text=final_text,
            intent=faro.intent,
            confidence=faro.confidence,
            handoff_created=handoff_created,
            urgency_detected=post_guard.urgency_detected,
            guardrail_action=post_guard.action.value,
            faro_brief=faro.to_dict(),
            route=state.route,
            source_of_truth=state.source_of_truth,
            structured_lookup_used=state.structured_lookup_used,
            rag_used=state.rag_used,
        )
        await self._audit(conversation, user_text, state, final_resp)
        return final_resp

    # ─── Audit helper ─────────────────────────────────────────────────────────

    async def _audit(
        self,
        conversation: Conversation,
        user_text: str,
        state: ConversationState,
        resp: EngineResponse,
    ) -> None:
        """Persist structured pipeline audit log."""
        try:
            await self.audit_svc.log_event(
                actor_type="ai",
                actor_id="orchestrator",
                action="pipeline.completed",
                resource_type="conversation",
                resource_id=str(conversation.id),
                payload={
                    # Intent + entities
                    "intent": state.intent,
                    "confidence": round(state.confidence, 3),
                    "entities": state.entities,
                    # Route decision
                    "route": state.route,
                    "source_of_truth": state.source_of_truth,
                    "response_mode": state.response_mode,
                    # Component flags
                    "structured_lookup_used": state.structured_lookup_used,
                    "rag_used": state.rag_used,
                    "tool_used": state.tool_used,
                    "handoff_triggered": state.handoff_triggered,
                    "handoff_reason": state.handoff_reason,
                    # Operational validity checks
                    "active_only_applied": state.active_only_applied,
                    "professionals_returned": state.professionals_returned,
                    "medical_availability_check": state.medical_availability_check,
                    "invalidated_schedule_detected": state.invalidated_schedule_detected,
                    "contingency_flow_triggered": state.contingency_flow_triggered,
                    "patient_notification_required": state.patient_notification_required,
                    "alternative_offered": state.alternative_offered,
                    # Runtime context sources
                    "clinic_name_source": state.clinic_name_source,
                    "prompt_source": state.prompt_source,
                    "specialties_source": state.specialties_source,
                    "insurance_catalog_size": state.insurance_catalog_size,
                    # Guardrails
                    "guardrail_pre": state.guardrail_pre,
                    "guardrail_post": state.guardrail_post,
                },
            )
        except Exception:
            logger.exception("[NODE:persist_and_audit] Falha ao persistir audit log")

    # ─── Multi-turn state management ──────────────────────────────────────────

    def _load_pending_action(self, conversation: Conversation) -> dict | None:
        if not conversation.pending_action:
            return None
        try:
            return json.loads(conversation.pending_action)
        except (json.JSONDecodeError, TypeError):
            return None

    async def _save_pending_action(self, conversation: Conversation, action: dict | None) -> None:
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
        action_type = pending.get("type")
        logger.info("[NODE:resolve_conversation_state] pending_action type=%s", action_type)

        if action_type == "select_slot":
            return await self._handle_slot_selection(patient, conversation, user_text, pending)
        if action_type == "select_slot_to_cancel":
            return await self._handle_slot_to_cancel_selection(patient, conversation, user_text, pending)
        if action_type == "confirm_cancel":
            return await self._handle_cancel_confirmation(patient, conversation, user_text, pending)
        if action_type == "awaiting_schedule_date":
            return await self._handle_awaiting_schedule_date(patient, conversation, user_text, pending)

        # Unknown pending — clear and fall through
        await self._save_pending_action(conversation, None)
        return None

    async def _handle_slot_selection(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        text = user_text.strip()
        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in text.lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! O agendamento foi cancelado. Posso ajudar com algo mais?",
                intent=Intent.AGENDAR, confidence=1.0, guardrail_action="allow",
            )

        slot_number = self._extract_number(text)
        slot_ids = pending.get("slot_ids", [])

        if slot_number is None or slot_number < 1 or slot_number > len(slot_ids):
            return EngineResponse(
                text=f"Por favor, responda com um número de 1 a {len(slot_ids)}, "
                     f"ou diga 'cancelar' para desistir.",
                intent=Intent.CONFIRMACAO, confidence=1.0, guardrail_action="allow",
            )

        selected_id = uuid.UUID(slot_ids[slot_number - 1])

        # ── Operational validity check: verify the professional is still active ──
        # This guards against the case where a professional was deactivated after
        # the slot list was shown but before the patient confirmed the choice.
        slot_record = await self.schedule_actions.schedule_repo.get_by_id(selected_id)
        if slot_record:
            prof = await self.structured_lookup.prof_repo.get_by_id(slot_record.professional_id)
            if not prof or not prof.active:
                await self._save_pending_action(conversation, None)
                prof_name = prof.full_name if prof else "o profissional selecionado"
                specialty = prof.specialty if prof else None

                await self.audit_svc.log_event(
                    actor_type="system",
                    actor_id="orchestrator",
                    action="operational.slot_invalidated_at_booking",
                    resource_type="schedule_slot",
                    resource_id=str(selected_id),
                    payload={
                        "reason": "professional_deactivated",
                        "professional_id": str(slot_record.professional_id),
                        "professional_name": prof_name,
                        "conversation_id": str(conversation.id),
                        "medical_availability_check": True,
                        "invalidated_schedule_detected": True,
                        "contingency_flow_triggered": True,
                        "patient_notification_required": True,
                    },
                )
                logger.warning(
                    "[NODE:operational_state_check] professional_deactivated slot_id=%s prof='%s' conv=%s "
                    "invalidated_schedule_detected=True contingency_flow_triggered=True",
                    selected_id, prof_name, conversation.id,
                )

                contingency_text = (
                    f"Lamentamos informar que *{prof_name}* não está mais disponível para atendimento. "
                    "Pedimos desculpas pelo transtorno.\n\n"
                )

                # Try to offer alternative slot in the same specialty
                if specialty:
                    alt = await self.schedule_actions.search_slots(specialty=specialty)
                    if alt.success and alt.slots:
                        await self._save_pending_action(conversation, {
                            "type": "select_slot",
                            "slot_ids": [str(s.slot_id) for s in alt.slots],
                        })
                        contingency_text += (
                            f"Encontrei outras opções disponíveis em *{specialty}*:\n\n"
                            + "\n".join(
                                f"{i}️⃣ {s.display()}" for i, s in enumerate(alt.slots, 1)
                            )
                            + "\n\nQual horário prefere? Responda com o número."
                        )
                        logger.info(
                            "[NODE:contingency_flow] alternative_offered=True specialty='%s' options=%d",
                            specialty, len(alt.slots),
                        )
                    else:
                        contingency_text += (
                            "No momento não encontrei outros horários disponíveis em "
                            f"*{specialty}*. Nossa equipe entrará em contato para reagendar."
                        )
                        await self._create_handoff(
                            conversation.id, user_text,
                            FaroBrief(intent=Intent.AGENDAR, confidence=1.0),
                            reason="professional_unavailable",
                            priority="high",
                        )
                        logger.warning(
                            "[NODE:contingency_flow] no_alternative specialty='%s' handoff_created=True",
                            specialty,
                        )
                else:
                    contingency_text += (
                        "Nossa equipe entrará em contato para reagendar. "
                        "Pedimos desculpas pelo inconveniente."
                    )
                    await self._create_handoff(
                        conversation.id, user_text,
                        FaroBrief(intent=Intent.AGENDAR, confidence=1.0),
                        reason="professional_unavailable",
                        priority="high",
                    )

                return EngineResponse(
                    text=contingency_text,
                    intent=Intent.AGENDAR,
                    confidence=1.0,
                    guardrail_action="allow",
                    route="contingency_flow",
                    source_of_truth="professionals",
                )

        result = await self.schedule_actions.book_slot(selected_id, patient.id, source="telegram")
        await self._save_pending_action(conversation, None)
        return EngineResponse(
            text=result.message, intent=Intent.AGENDAR, confidence=1.0, guardrail_action="allow",
        )

    async def _handle_cancel_confirmation(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        text = user_text.strip().lower()
        faro = intent_router.analyze(user_text)

        if faro.confirmation_detected or text in ("sim", "s", "confirmo", "pode"):
            slot_id = pending.get("slot_id")
            if slot_id:
                result = await self.schedule_actions.cancel_slot(patient.id, slot_id=uuid.UUID(slot_id))
                await self._save_pending_action(conversation, None)
                return EngineResponse(
                    text=result.message, intent=Intent.CANCELAR, confidence=1.0, guardrail_action="allow",
                )

        if any(w in text for w in ["nao", "não", "cancelar", "desistir"]):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Ok, a consulta foi mantida. Posso ajudar com algo mais?",
                intent=Intent.CANCELAR, confidence=1.0, guardrail_action="allow",
            )

        return EngineResponse(
            text="Por favor, confirme com 'sim' ou 'não'.",
            intent=Intent.CONFIRMACAO, confidence=1.0, guardrail_action="allow",
        )

    async def _handle_slot_to_cancel_selection(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        text = user_text.strip()
        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in text.lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! Nenhuma consulta foi cancelada. Posso ajudar com algo mais?",
                intent=Intent.CANCELAR, confidence=1.0, guardrail_action="allow",
            )

        slot_number = self._extract_number(text)
        slot_ids = pending.get("slot_ids", [])
        slot_displays = pending.get("slot_displays", [])

        if slot_number is None or slot_number < 1 or slot_number > len(slot_ids):
            return EngineResponse(
                text=f"Por favor, responda com um número de 1 a {len(slot_ids)}, "
                     f"ou diga 'cancelar' para desistir.",
                intent=Intent.CONFIRMACAO, confidence=1.0, guardrail_action="allow",
            )

        selected_id = slot_ids[slot_number - 1]
        display = (
            slot_displays[slot_number - 1]
            if slot_displays and slot_number <= len(slot_displays)
            else selected_id
        )
        await self._save_pending_action(conversation, {"type": "confirm_cancel", "slot_id": selected_id})
        return EngineResponse(
            text=f"Você selecionou:\n\n📅 {display}\n\nDeseja realmente cancelar? Responda 'sim' ou 'não'.",
            intent=Intent.CANCELAR, confidence=1.0, guardrail_action="allow",
        )

    async def _handle_awaiting_schedule_date(
        self,
        patient: Patient,
        conversation: Conversation,
        user_text: str,
        pending: dict,
    ) -> EngineResponse | None:
        cancel_words = ["cancelar", "desistir", "nao", "não", "sair", "voltar"]
        if any(w in user_text.strip().lower() for w in cancel_words):
            await self._save_pending_action(conversation, None)
            return EngineResponse(
                text="Tudo bem! Agendamento cancelado. Posso ajudar com algo mais?",
                intent=Intent.AGENDAR, confidence=1.0, guardrail_action="allow",
            )

        faro = intent_router.analyze(user_text)
        date_str = faro.entities.get("date")
        time_str = faro.entities.get("time")

        if not date_str:
            return EngineResponse(
                text="Por favor, informe uma data. Exemplo: 'amanhã', 'segunda-feira' ou '20/04'.",
                intent=Intent.AGENDAR, confidence=1.0, guardrail_action="allow",
            )

        specialty = pending.get("specialty")
        doctor_name = pending.get("doctor_name")
        logger.info(
            "[NODE:resolve_conversation_state] multi-turn schedule: specialty=%s doctor=%s date=%s",
            specialty, doctor_name, date_str,
        )

        result = await self.schedule_actions.search_slots(
            specialty=specialty, doctor_name=doctor_name,
            date_str=date_str, time_str=time_str,
        )
        if result.success and result.slots:
            await self._save_pending_action(conversation, {
                "type": "select_slot",
                "slot_ids": [str(s.slot_id) for s in result.slots],
            })
        else:
            await self._save_pending_action(conversation, None)

        return EngineResponse(
            text=result.message, intent=Intent.AGENDAR, confidence=1.0, guardrail_action="allow",
        )

    def _extract_number(self, text: str) -> int | None:
        match = re.search(r"\b(\d+)\b", text)
        if match:
            return int(match.group(1))
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

    # ─── Action execution (schedule_flow) ────────────────────────────────────

    async def _execute_action(
        self, patient: Patient, conversation: Conversation, faro: FaroBrief
    ) -> str | None:
        """Execute real schedule actions. Returns None if intent is not actionable."""
        entities = faro.entities

        if faro.intent == Intent.AGENDAR:
            specialty = entities.get("specialty")
            doctor_name = entities.get("doctor_name")
            date_str = entities.get("date")
            time_str = entities.get("time")
            has_target = specialty or doctor_name

            if has_target:
                # Search slots (with or without date — no date = next 14 days)
                result = await self.schedule_actions.search_slots(
                    specialty=specialty, doctor_name=doctor_name,
                    date_str=date_str, time_str=time_str,
                )
                if result.success and result.slots:
                    await self._save_pending_action(conversation, {
                        "type": "select_slot",
                        "slot_ids": [str(s.slot_id) for s in result.slots],
                    })
                    return result.message
                elif not date_str:
                    # No slots in 14-day window → ask for preferred date
                    target_label = specialty or doctor_name
                    await self._save_pending_action(conversation, {
                        "type": "awaiting_schedule_date",
                        "specialty": specialty,
                        "doctor_name": doctor_name,
                    })
                    return (
                        f"Ótimo! Para agendar com {target_label}, qual data e horário você prefere? "
                        "Pode dizer 'amanhã', 'segunda às 10h', ou uma data específica."
                    )
                else:
                    return result.message

            if date_str and not has_target:
                return (
                    "Para qual especialidade ou médico você gostaria de agendar? "
                    "Por favor, informe a especialidade (ex: Ortopedia, Cardiologia)."
                )

            return None

        if faro.intent == Intent.CANCELAR:
            appointments = await self.schedule_actions.list_patient_appointments(patient.id)
            if appointments.slots and len(appointments.slots) == 1:
                slot = appointments.slots[0]
                await self._save_pending_action(conversation, {
                    "type": "confirm_cancel",
                    "slot_id": str(slot.slot_id),
                })
                return (
                    f"Encontrei sua consulta:\n\n📅 {slot.display()}\n\n"
                    f"Deseja realmente cancelar? Responda 'sim' ou 'não'."
                )
            if appointments.slots and len(appointments.slots) > 1:
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
            result = await self.schedule_actions.cancel_slot(
                patient_id=patient.id, date_str=entities.get("date"),
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
            return None

        if faro.intent == Intent.LISTAR_ESPECIALIDADES:
            doctor_name = entities.get("doctor_name")
            specialty_filter = entities.get("specialty")

            # If a specific doctor was mentioned, structured_lookup should have already
            # handled this. This is a safety net for cases that fall through.
            if doctor_name:
                profs = await self.schedule_actions._find_professionals(None, doctor_name)
                if profs:
                    p = profs[0]
                    return f"{p.full_name} atende na especialidade de *{p.specialty}*."
                return f"Não encontrei um profissional com o nome '{doctor_name}'."

            # If a specialty filter was given, list doctors in that specialty
            if specialty_filter:
                profs = await self.schedule_actions._find_professionals(specialty_filter, None)
                if profs:
                    lines = [f"Profissionais que atendem *{specialty_filter}*:\n"]
                    for p in profs:
                        lines.append(f"  • {p.full_name}")
                    lines.append("\nQual médico prefere para o agendamento?")
                    return "\n".join(lines)

            # Generic: list all available specialties
            profs = await self.schedule_actions._find_professionals(None, None)
            if profs:
                specialties = sorted(set(p.specialty for p in profs))
                lines = ["Especialidades disponíveis:\n"]
                for s in specialties:
                    lines.append(f"  • {s}")
                lines.append("\nQual especialidade deseja?")
                return "\n".join(lines)
            return "No momento não há especialidades cadastradas no sistema."

        return None

    # ─── Handoff ──────────────────────────────────────────────────────────────

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
