import pytest
from app.ai_engine.ner_service import NerService, DetectedEntities

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