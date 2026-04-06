"""Tests for FARO Intent Router."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai_engine.intent_router import Intent, analyze


class TestIntentClassification:
    def test_saudacao(self):
        faro = analyze("Oi, bom dia!")
        assert faro.intent == Intent.SAUDACAO
        assert faro.confidence >= 0.5

    def test_agendar(self):
        faro = analyze("Quero agendar uma consulta")
        assert faro.intent == Intent.AGENDAR

    def test_cancelar(self):
        faro = analyze("Preciso cancelar minha consulta")
        assert faro.intent == Intent.CANCELAR

    def test_remarcar(self):
        faro = analyze("Quero remarcar para sexta")
        assert faro.intent == Intent.REMARCAR

    def test_remarcar_not_confused_with_agendar(self):
        faro = analyze("Preciso remarcar minha consulta")
        assert faro.intent == Intent.REMARCAR

    def test_duvida_operacional(self):
        faro = analyze("Qual o horario de funcionamento?")
        assert faro.intent == Intent.DUVIDA_OPERACIONAL

    def test_falar_com_humano(self):
        faro = analyze("Quero falar com um atendente")
        assert faro.intent == Intent.FALAR_COM_HUMANO

    def test_confirmacao(self):
        faro = analyze("Pode marcar")
        assert faro.intent == Intent.CONFIRMACAO
        assert faro.confidence >= 0.9

    def test_listar_especialidades(self):
        faro = analyze("Quais especialidades a clinica tem?")
        assert faro.intent == Intent.LISTAR_ESPECIALIDADES

    def test_desconhecida(self):
        faro = analyze("xyz abc 123")
        assert faro.intent == Intent.DESCONHECIDA
        assert faro.confidence <= 0.40


class TestEntityExtraction:
    def test_doctor_name(self):
        faro = analyze("Quero consulta com Dr. Silva")
        assert faro.entities.get("doctor_name") == "Silva"

    def test_date_relative_amanha(self):
        faro = analyze("Agendar para amanha")
        assert "date" in faro.entities

    def test_time_extraction(self):
        faro = analyze("Consulta as 14h30")
        assert faro.entities.get("time") == "14:30"

    def test_cpf_extraction(self):
        faro = analyze("Meu cpf e 123.456.789-00")
        assert faro.entities.get("cpf") == "123.456.789-00"

    def test_email_extraction(self):
        faro = analyze("Meu email e maria@teste.com")
        assert faro.entities.get("email") == "maria@teste.com"

    def test_phone_extraction(self):
        faro = analyze("Meu telefone 11 99999-8888")
        assert "phone" in faro.entities


class TestMissingFields:
    def test_agendar_missing_specialty(self):
        faro = analyze("Quero agendar uma consulta")
        assert "especialidade_ou_medico" in faro.missing_fields

    def test_cancelar_missing_reference(self):
        faro = analyze("Preciso cancelar minha consulta")
        assert "referencia_consulta" in faro.missing_fields


class TestConfirmationDetection:
    def test_sim(self):
        faro = analyze("Sim, pode marcar")
        assert faro.confirmation_detected is True

    def test_confirmo(self):
        faro = analyze("Confirmo")
        assert faro.confirmation_detected is True


class TestFaroBriefSerialization:
    def test_to_dict(self):
        faro = analyze("Bom dia")
        d = faro.to_dict()
        assert "intent" in d
        assert "confidence" in d
        assert "entities" in d
        assert isinstance(d["intent"], str)
