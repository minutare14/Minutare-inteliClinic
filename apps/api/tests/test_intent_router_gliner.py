import pytest
from app.ai_engine.ner_service import NerService, DetectedEntities
from app.ai_engine.routing_decision import decide, RoutingDecision, Intent

def test_greedy_specialty_detection():
    ner = NerService()
    result = ner.detect("quais médicos atendem neurologia?")
    assert result.specialty == "Neurologia"
    assert result.gliner_used == False  # greedy fallback

def test_greedy_professional_name():
    ner = NerService()
    result = ner.detect("Dr. Carlos atende qual especialidade?")
    assert result.professional_name is not None
    assert result.specialty is None

def test_greedy_greeting():
    ner = NerService()
    result = ner.detect("oi, bom dia!")
    assert result.greeting == True

def test_greedy_insurance():
    ner = NerService()
    result = ner.detect("vocês aceitam Unimed?")
    assert result.insurance_plan == "Unimed"

def test_greedy_clinic_info_topic():
    ner = NerService()
    result = ner.detect("qual o endereço da clínica?")
    assert result.clinic_info_topic == "endereço"


def test_routing_professional_name_question():
    result = decide("Dr. Carlos atende qual especialidade?", DetectedEntities(professional_name="Dr. Carlos"))
    assert result.intent == Intent.GET_PROFESSIONAL_SPECIALTY
    assert result.route == "structured_data_lookup"
    assert result.tool_used == "list_professionals"


def test_routing_specialty_listing():
    result = decide("quem atende neurologia?", DetectedEntities(specialty="Neurologia"))
    assert result.intent == Intent.LIST_PROFISSIONAIS_BY_SPECIALTY
    assert result.suggested_action["action"] == "list_professionals_by_specialty"
    assert result.suggested_action["args"]["specialty"] == "Neurologia"


def test_routing_specialty_with_scheduling():
    result = decide("agendar com neurologista amanhã", DetectedEntities(specialty="Neurologia", date_reference="amanhã"))
    assert result.intent == Intent.SCHEDULING
    assert result.route == "schedule_flow"


def test_routing_greeting():
    result = decide("oi, bom dia!", DetectedEntities(greeting=True))
    assert result.intent == Intent.GREETING
    assert result.confidence == 0.95


def test_routing_list_specialties():
    result = decide("quais especialidades vocês têm?", DetectedEntities())
    assert result.intent == Intent.LIST_SPECIALTIES


def test_routing_no_entity_fallback():
    result = decide("o tempo está bonito hoje", DetectedEntities())
    assert result.intent == Intent.UNKNOWN
    assert result.route == "clarification_flow"


# ─── Integration tests for refactored intent_router.py ─────────────────────────────────

from app.ai_engine.intent_router import analyze

def test_analyze_quais_medicos():
    """'quais médicos vocês têm?' → LIST_PROFISSIONAIS, route=structured_data_lookup"""
    faro = analyze("quais médicos vocês têm?")
    assert faro.intent.value in ("listar_profissionais", "listar_especialidades", "desconhecida")
    # Must NOT be desconhecida (that's the bug we're fixing)
    assert faro.intent.value != "desconhecida", f"Got DESCONHECIDA for 'quais médicos vocês têm?'"
    assert faro.routing_decision is not None
    assert faro.routing_decision.route in ("structured_data_lookup", "schedule_flow")

def test_analyze_quem_atende_neuro():
    """'quem atende neurologia?' → LIST_PROFESSIONALS_BY_SPECIALTY"""
    faro = analyze("quem atende neurologia?")
    assert faro.routing_decision is not None
    # Check the legacy intent (faro.intent) which is what the orchestrator uses
    assert faro.intent.value == "listar_profissionais", f"Expected listar_profissionais, got {faro.intent.value}"
    assert faro.routing_decision.route == "structured_data_lookup"

def test_analyze_greeting():
    faro = analyze("oi, bom dia!")
    assert faro.intent.value == "saudacao"
    assert faro.routing_decision.greeting

def test_analyze_agendar():
    faro = analyze("quero agendar com neurologista amanhã")
    assert faro.intent.value == "agendar"
    assert faro.routing_decision.route == "schedule_flow"