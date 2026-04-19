"""
Entity-driven routing decision layer.

Replaces keyword-scoring _classify_intent from intent_router.py.
Applies 11 entity-driven priority rules to produce a RoutingDecision.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.ai_engine.ner_service import DetectedEntities


class Intent(Enum):
    """All supported intents."""
    SCHEDULING = "SCHEDULING"
    LIST_PROFISSIONAIS = "LIST_PROFISSIONAIS"
    LIST_SPECIALTIES = "LIST_SPECIALTIES"
    GET_PROFESSIONAL_SPECIALTY = "GET_PROFESSIONAL_SPECIALTY"
    LIST_PROFISSIONAIS_BY_SPECIALTY = "LIST_PROFISSIONAIS_BY_SPECIALTY"
    CHECK_AVAILABILITY = "CHECK_AVAILABILITY"
    GET_CLINIC_INFO = "GET_CLINIC_INFO"
    GREETING = "GREETING"
    CONFIRMATION = "CONFIRMATION"
    UNKNOWN = "UNKNOWN"


# Legacy alias for backwards compatibility with intent_router.py
class IntentAlias(Enum):
    LIST_PROFISSIONAIS = "LIST_PROFISSIONAIS"
    LISTAR_PROFISSIONAIS = "LISTAR_PROFISSIONAIS"
    LISTAR_ESPECIALIDADES = "LISTAR_ESPECIALIDADES"
    VERIFICAR_DISPONIBILIDADE = "VERIFICAR_DISPONIBILIDADE"
    OBTER_INFORMACOES_CLINICA = "OBTER_INFORMACOES_CLINICA"
    CUMPRIMENTO = "CUMPRIMENTO"
    CONFIRMACAO = "CONFIRMACAO"
    AGENDAMENTO = "AGENDAMENTO"
    CANCELAMENTO = "CANCELAMENTO"
    REAGENDAMENTO = "REAGENDAMENTO"


_legacy_alias_map = {
    IntentAlias.LIST_PROFISSIONAIS: Intent.LIST_PROFISSIONAIS,
    IntentAlias.LISTAR_PROFISSIONAIS: Intent.LIST_PROFISSIONAIS,
    IntentAlias.LISTAR_ESPECIALIDADES: Intent.LIST_SPECIALTIES,
    IntentAlias.VERIFICAR_DISPONIBILIDADE: Intent.CHECK_AVAILABILITY,
    IntentAlias.OBTER_INFORMACOES_CLINICA: Intent.GET_CLINIC_INFO,
    IntentAlias.CUMPRIMENTO: Intent.GREETING,
    IntentAlias.CONFIRMACAO: Intent.CONFIRMATION,
    IntentAlias.AGENDAMENTO: Intent.SCHEDULING,
    IntentAlias.CANCELAMENTO: Intent.SCHEDULING,
    IntentAlias.REAGENDAMENTO: Intent.SCHEDULING,
}


def intent_alias_to_legacy(alias: IntentAlias) -> Intent:
    return _legacy_alias_map.get(alias, Intent.UNKNOWN)


@dataclass
class RoutingDecision:
    """Routing decision produced by decide()."""
    intent: Intent
    confidence: float = 1.0
    route: str = "clarification_flow"
    source_of_truth: str = "entity_driven"
    tool_used: Optional[str] = None
    suggested_action: dict = field(default_factory=dict)
    reason: str = ""


# -------------------------------------------------------------------
# Pattern sets
# -------------------------------------------------------------------

_SCHEDULING_VERBS = frozenset({
    "agendar", "marcar", "reservar", "consulta", "atendimento",
    "bloquear", "horário", "horario", "disponibilidade",
    "verificar", "checar", "confirmar",
})

_LISTING_PATTERNS = frozenset({
    "quais", "quem", "listar", "mostrar", "exibir",
    "tenho", "preciso", "gostaria", "quero",
})

_CLINIC_INFO_PATTERNS = frozenset({
    "endereço", "endereco", "localização", "localizacao",
    "telefone", "contato", "funcionamento", "horário", "horario",
    "convênio", "convenio", "plano", "unidade", "unidades",
    "valor", "preço", "preco", "consulta",
})

_CONFIRMATION_PATTERNS = frozenset({
    "sim", "confirmo", "correto", "certo", "ok", "tudo bem",
    "confirmar", "certeza", "exato", "exatamente",
    "pode", "pode sim", "sim, por favor",
})


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _detect_confirmation(text: str) -> bool:
    """Return True if text is a clear confirmation."""
    normalized = text.lower().strip()
    return normalized in _CONFIRMATION_PATTERNS


def _contains_confirmation_pattern(text: str) -> bool:
    """Return True if text contains confirmation words."""
    normalized = text.lower()
    return any(p in normalized for p in _CONFIRMATION_PATTERNS)


def _contains_scheduling_verb(text: str) -> bool:
    """Return True if text contains scheduling verb or pattern."""
    normalized = text.lower()
    return any(v in normalized for v in _SCHEDULING_VERBS)


def _contains_listing_pattern(text: str) -> bool:
    """Return True if text contains listing question patterns."""
    normalized = text.lower()
    return any(p in normalized for p in _LISTING_PATTERNS)


# -------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------

def decide(text: str, entities: DetectedEntities) -> RoutingDecision:
    """
    Entity-driven routing decision.

    Applies 11 priority rules:
    1. Confirmation detected → CONFIRMATION
    2. greeting=true + fewer than 5 words → GREETING
    3. professional_name detected → GET_PROFESSIONAL_SPECIALTY / CHECK_AVAILABILITY / LIST_PROFISSIONAIS
    4. specialty detected → SCHEDULING / LIST_PROFISSIONAIS_BY_SPECIALTY / CHECK_AVAILABILITY
    5. insurance_plan detected → GET_CLINIC_INFO
    6. clinic_info_topic detected → GET_CLINIC_INFO
    7. date_reference + scheduling verb → SCHEDULING
    8. Listing words ("quais", "quem") → LIST_SPECIALTIES / LIST_PROFISSIONAIS
    9. Scheduling verb without entity → SCHEDULING
    10. Last resort → UNKNOWN (clarification_flow)
    """
    normalized = text.lower().strip()
    word_count = len(text.split())

    # -----------------------------------------------------------------
    # Rule 1 — Confirmation
    # -----------------------------------------------------------------
    if _detect_confirmation(normalized):
        return RoutingDecision(
            intent=Intent.CONFIRMATION,
            confidence=0.95,
            route="clarification_flow",
            source_of_truth="confirmation_pattern",
            suggested_action={"action": "confirm", "args": {}},
            reason="Confirmation pattern detected",
        )

    # -----------------------------------------------------------------
    # Rule 2 — Greeting
    # -----------------------------------------------------------------
    if entities.greeting and word_count < 5:
        return RoutingDecision(
            intent=Intent.GREETING,
            confidence=0.95,
            route="clarification_flow",
            source_of_truth="entity:greeting",
            suggested_action={"action": "greet", "args": {}},
            reason="Greeting entity detected, short text",
        )

    # -----------------------------------------------------------------
    # Rule 3 — professional_name
    # -----------------------------------------------------------------
    if entities.professional_name:
        if _contains_scheduling_verb(normalized):
            return RoutingDecision(
                intent=Intent.SCHEDULING,
                confidence=0.9,
                route="schedule_flow",
                source_of_truth="entity:professional_name + scheduling_verb",
                tool_used="schedule_service",
                suggested_action={
                    "action": "schedule_with_professional",
                    "args": {"professional_name": entities.professional_name},
                },
                reason="professional_name detected with scheduling verb",
            )
        return RoutingDecision(
            intent=Intent.GET_PROFESSIONAL_SPECIALTY,
            confidence=0.9,
            route="structured_data_lookup",
            source_of_truth="entity:professional_name",
            tool_used="list_professionals",
            suggested_action={
                "action": "get_professional_specialty",
                "args": {"professional_name": entities.professional_name},
            },
            reason="professional_name detected, no scheduling verb",
        )

    # -----------------------------------------------------------------
    # Rule 4 — specialty
    # -----------------------------------------------------------------
    if entities.specialty:
        if entities.date_reference:
            return RoutingDecision(
                intent=Intent.SCHEDULING,
                confidence=0.9,
                route="schedule_flow",
                source_of_truth="entity:specialty + date_reference",
                tool_used="schedule_service",
                suggested_action={
                    "action": "schedule_by_specialty",
                    "args": {
                        "specialty": entities.specialty,
                        "date_reference": entities.date_reference,
                    },
                },
                reason="specialty + date_reference detected",
            )
        if _contains_listing_pattern(normalized):
            return RoutingDecision(
                intent=Intent.LIST_PROFISSIONAIS_BY_SPECIALTY,
                confidence=0.9,
                route="structured_data_lookup",
                source_of_truth="entity:specialty + listing_pattern",
                tool_used="list_professionals_by_specialty",
                suggested_action={
                    "action": "list_professionals_by_specialty",
                    "args": {"specialty": entities.specialty},
                },
                reason="specialty detected with listing pattern",
            )
        return RoutingDecision(
            intent=Intent.CHECK_AVAILABILITY,
            confidence=0.8,
            route="schedule_flow",
            source_of_truth="entity:specialty",
            suggested_action={
                "action": "check_availability_by_specialty",
                "args": {"specialty": entities.specialty},
            },
            reason="specialty detected without scheduling context",
        )

    # -----------------------------------------------------------------
    # Rule 5 — insurance_plan
    # -----------------------------------------------------------------
    if entities.insurance_plan:
        return RoutingDecision(
            intent=Intent.GET_CLINIC_INFO,
            confidence=0.85,
            route="structured_data_lookup",
            source_of_truth="entity:insurance_plan",
            tool_used="clinic_info",
            suggested_action={
                "action": "get_clinic_info",
                "args": {"topic": "convenio"},
            },
            reason="insurance_plan detected",
        )

    # -----------------------------------------------------------------
    # Rule 6 — clinic_info_topic
    # -----------------------------------------------------------------
    if entities.clinic_info_topic:
        topic = entities.clinic_info_topic
        action_map = {
            "endereço": "get_address",
            "endereco": "get_address",
            "telefone": "get_phone",
            "contato": "get_contact",
            "funcionamento": "get_hours",
            "horário": "get_hours",
            "horario": "get_hours",
            "convênio": "get_insurance_plans",
            "convenio": "get_insurance_plans",
            "plano": "get_insurance_plans",
            "valor": "get_prices",
            "preço": "get_prices",
            "preco": "get_prices",
        }
        action = action_map.get(topic, "get_clinic_info")
        return RoutingDecision(
            intent=Intent.GET_CLINIC_INFO,
            confidence=0.85,
            route="structured_data_lookup",
            source_of_truth="entity:clinic_info_topic",
            tool_used="clinic_info",
            suggested_action={"action": action, "args": {"topic": topic}},
            reason=f"clinic_info_topic='{topic}' detected",
        )

    # -----------------------------------------------------------------
    # Rule 7 — date_reference + scheduling verb
    # -----------------------------------------------------------------
    if entities.date_reference and _contains_scheduling_verb(normalized):
        return RoutingDecision(
            intent=Intent.SCHEDULING,
            confidence=0.85,
            route="schedule_flow",
            source_of_truth="entity:date_reference + scheduling_verb",
            tool_used="schedule_service",
            suggested_action={
                "action": "schedule",
                "args": {"date_reference": entities.date_reference},
            },
            reason="date_reference + scheduling verb detected",
        )

    # -----------------------------------------------------------------
    # Rule 8 — Listing patterns
    # -----------------------------------------------------------------
    if _contains_listing_pattern(normalized):
        if any(p in normalized for p in {"especialidade", "especialidades"}):
            return RoutingDecision(
                intent=Intent.LIST_SPECIALTIES,
                confidence=0.85,
                route="structured_data_lookup",
                source_of_truth="listing_pattern + specialty_keyword",
                tool_used="list_specialties",
                suggested_action={"action": "list_specialties", "args": {}},
                reason="Listing pattern with specialty keyword",
            )
        return RoutingDecision(
            intent=Intent.LIST_PROFISSIONAIS,
            confidence=0.8,
            route="structured_data_lookup",
            source_of_truth="listing_pattern",
            tool_used="list_professionals",
            suggested_action={"action": "list_professionals", "args": {}},
            reason="Listing pattern without specialty keyword",
        )

    # -----------------------------------------------------------------
    # Rule 9 — Scheduling verb without specific entity
    # -----------------------------------------------------------------
    if _contains_scheduling_verb(normalized):
        return RoutingDecision(
            intent=Intent.SCHEDULING,
            confidence=0.75,
            route="schedule_flow",
            source_of_truth="scheduling_verb",
            tool_used="schedule_service",
            suggested_action={"action": "schedule", "args": {}},
            reason="Scheduling verb without specific entity",
        )

    # -----------------------------------------------------------------
    # Rule 10 — Last resort: UNKNOWN → clarification_flow
    # -----------------------------------------------------------------
    return RoutingDecision(
        intent=Intent.UNKNOWN,
        confidence=0.5,
        route="clarification_flow",
        source_of_truth="fallback",
        suggested_action={"action": "ask_clarification", "args": {}},
        reason="No entity matched; falling back to clarification_flow",
    )
