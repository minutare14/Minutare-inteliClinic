"""
FARRO Intent Router — refactored with GLiNER + entity-driven routing.

GLiNER (or greedy fallback) extracts entities.
RoutingDecision applies entity-based rules to pick intent + route.
Legacy Intent enum preserved for backwards compat with orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.ai_engine.ner_service import NerService, DetectedEntities
from app.ai_engine.routing_decision import (
    decide,
    RoutingDecision as RoutingDecisionImpl,
    Intent as RoutingIntent,
    IntentAlias,
    intent_alias_to_legacy,
)

logger = logging.getLogger(__name__)


# Legacy Intent enum — kept for backwards compatibility with orchestrator
class Intent(str, Enum):
    AGENDAR = "agendar"
    REMARCAR = "remarcar"
    CANCELAR = "cancelar"
    DUVIDA_OPERACIONAL = "duvida_operacional"
    FALAR_COM_HUMANO = "falar_com_humano"
    POLITICAS = "politicas"
    LISTAR_PROFISSIONAIS = "listar_profissionais"
    LISTAR_ESPECIALIDADES = "listar_especialidades"
    SAUDACAO = "saudacao"
    CONFIRMACAO = "confirmacao"
    DESCONHECIDA = "desconhecida"


@dataclass
class FaroBrief:
    """Structured output from FARO analysis."""
    intent: Intent
    confidence: float
    entities: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    confirmation_detected: bool = False
    suggested_actions: list[dict] = field(default_factory=list)
    gliner_used: bool = False
    routing_decision: RoutingDecisionImpl | None = None

    def to_dict(self) -> dict:
        base = {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "missing_fields": self.missing_fields,
            "confirmation_detected": self.confirmation_detected,
            "suggested_actions": self.suggested_actions,
            "gliner_used": self.gliner_used,
        }
        if self.routing_decision:
            base["routing"] = {
                "route": self.routing_decision.route,
                "source_of_truth": self.routing_decision.source_of_truth,
                "tool_used": self.routing_decision.tool_used,
                "reason": self.routing_decision.reason,
            }
        return base


def analyze(text: str, specialties_override: list[str] | None = None) -> FaroBrief:
    """
    Full FARO analysis with GLiNER NER + entity-driven routing.

    Pipeline:
      1. NerService.detect() → DetectedEntities
      2. decide() → RoutingDecision
      3. Build FaroBrief with legacy Intent (backwards compat)
    """
    ner = NerService()
    detected = ner.detect(text)
    routing = decide(text, detected)
    legacy_intent = intent_alias_to_legacy(routing.intent)
    entities_dict = _build_entities_dict(detected)

    faro_brief = FaroBrief(
        intent=legacy_intent,
        confidence=routing.confidence,
        entities=entities_dict,
        missing_fields=_compute_missing_fields(routing),
        confirmation_detected=routing.intent == RoutingIntent.CONFIRMATION,
        suggested_actions=[routing.suggested_action] if routing.suggested_action else [],
        gliner_used=detected.gliner_used,
        routing_decision=routing,
    )

    logger.info(
        "[FARO] text=%.50r gliner=%s intent=%s route=%s tool=%s confidence=%.2f",
        text,
        detected.gliner_used,
        routing.intent.value,
        routing.route,
        routing.tool_used,
        routing.confidence,
    )

    return faro_brief


def _build_entities_dict(detected: DetectedEntities) -> dict:
    """Build legacy entities dict from DetectedEntities."""
    entities = {}
    if detected.professional_name:
        entities["doctor_name"] = detected.professional_name
    if detected.specialty:
        entities["specialty"] = detected.specialty
    if detected.insurance_plan:
        entities["insurance"] = detected.insurance_plan
    if detected.service_name:
        entities["service"] = detected.service_name
    if detected.date_reference:
        entities["date"] = _parse_date_value(detected.date_reference)
    if detected.time_period:
        entities["time"] = detected.time_period
    if detected.clinic_info_topic:
        entities["clinic_info_topic"] = detected.clinic_info_topic
    return entities


def _parse_date_value(date_ref: str) -> str:
    """Convert relative date to ISO format."""
    from datetime import datetime, timedelta

    today = datetime.now().date()
    date_lower = date_ref.lower()

    RELATIVE = {"hoje": 0, "amanha": 1, "amanhã": 1, "depois de amanha": 2}
    if date_lower in RELATIVE:
        return (today + timedelta(days=RELATIVE[date_lower])).strftime("%Y-%m-%d")

    WEEKDAYS = {
        "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
        "sexta": 4, "sabado": 5, "domingo": 6,
    }
    for day, offset in WEEKDAYS.items():
        if day in date_lower:
            days_ahead = (offset - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    import re

    match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", date_ref)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).date().strftime("%Y-%m-%d")
        except ValueError:
            pass

    return date_ref


def _compute_missing_fields(routing: RoutingDecisionImpl) -> list[str]:
    """Compute missing fields from routing decision."""
    missing = []
    if routing.intent == RoutingIntent.SCHEDULING:
        args = routing.suggested_action.get("args", {})
        if not args.get("specialty") and not args.get("professional"):
            missing.append("especialidade_ou_medico")
    return missing
