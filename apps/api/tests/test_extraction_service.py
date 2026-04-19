from __future__ import annotations

import pytest
from app.services.extraction_service import (
    extract_crm,
    extract_currency,
    extract_insurance,
    extract_schedule,
    extract_entities,
)


class TestExtractCRM:
    def test_extract_simple_crm(self):
        text = "Dr. João Silva CRM/AM 12345 Dermatologia"
        results = extract_crm(text)
        assert len(results) == 1
        assert results[0].entity_type == "doctor"
        assert results[0].extracted_data["crm"] == "CRM/AM"
        assert results[0].confidence == 1.0

    def test_extract_crm_without_specialty(self):
        text = "Atendimento CRM/SP 54321"
        results = extract_crm(text)
        assert len(results) >= 1
        assert results[0].extraction_method == "deterministic"

    def test_no_crm_found(self):
        text = "Sem formatação de CRM neste texto."
        results = extract_crm(text)
        assert len(results) == 0

    def test_extract_multiple_crm(self):
        text = "Dr. João CRM/AM 12345 e Dra. Maria CRM/RJ 54321"
        results = extract_crm(text)
        assert len(results) == 2


class TestExtractCurrency:
    def test_extract_simple_price(self):
        text = "Consulta R$ 150,00"
        results = extract_currency(text)
        assert len(results) == 1
        assert results[0].entity_type == "price"
        assert results[0].extracted_data["price"] == 150.0

    def test_extract_price_without_cents(self):
        text = "Exame R$ 200"
        results = extract_currency(text)
        assert len(results) == 1
        assert results[0].extracted_data["price"] == 200.0

    def test_no_currency_found(self):
        text = "Sem preços neste texto."
        results = extract_currency(text)
        assert len(results) == 0

    def test_extract_multiple_prices(self):
        text = "Consulta R$ 150,00 mais exame R$ 200,50"
        results = extract_currency(text)
        assert len(results) == 2


class TestExtractInsurance:
    def test_extract_known_plan(self):
        text = "Aceitamos plano Bradesco Saúde"
        known = ["Bradesco Saúde", "Amil", "Unimed"]
        results = extract_insurance(text, known)
        assert len(results) == 1
        assert results[0].entity_type == "insurance"
        assert results[0].extracted_data["insurance_name"] == "Bradesco Saúde"

    def test_case_insensitive_match(self):
        text = "atendimento brAdesco saúde"
        known = ["Bradesco Saúde"]
        results = extract_insurance(text, known)
        assert len(results) == 1

    def test_no_match_against_unknown(self):
        text = "Aceitamos plano XYZ desconhecido"
        known = ["Bradesco Saúde", "Amil"]
        results = extract_insurance(text, known)
        assert len(results) == 0

    def test_multiple_plans(self):
        text = "Planos aceitos: Amil, Unimed e Bradesco Saúde"
        known = ["Amil", "Unimed", "Bradesco Saúde"]
        results = extract_insurance(text, known)
        assert len(results) == 3


class TestExtractSchedule:
    def test_extract_day_slot(self):
        text = "Horário: Segunda das 09:00 às 18:00"
        results = extract_schedule(text)
        assert len(results) == 1
        assert results[0].entity_type == "schedule"

    def test_multiple_days(self):
        text = "Segundas e quartas das 08:00 às 17:00"
        results = extract_schedule(text)
        assert len(results) >= 1

    def test_no_schedule_found(self):
        text = "Nenhum horário aqui."
        results = extract_schedule(text)
        assert len(results) == 0


class TestExtractEntities:
    def test_dispatch_to_crm(self):
        text = "Dr. Teste CRM/AM 99999 Clínica Geral"
        results = extract_entities(text, "doctor")
        assert len(results) == 1

    def test_dispatch_to_currency(self):
        text = "R$ 500,00"
        results = extract_entities(text, "price")
        assert len(results) == 1

    def test_dispatch_to_insurance(self):
        text = "Amil convênio"
        results = extract_entities(text, "insurance", known_insurance=["Amil"])
        assert len(results) == 1

    def test_unknown_entity_type(self):
        text = "Some text"
        results = extract_entities(text, "unknown_type")
        assert len(results) == 0