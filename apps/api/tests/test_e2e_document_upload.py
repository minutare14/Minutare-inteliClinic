"""End-to-end test for document upload pipeline."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.chunking import semantic_chunk
from app.services.extraction_service import extract_crm, extract_currency, extract_insurance


class TestDocumentUploadPipeline:
    """Test the full document upload pipeline components."""

    def test_crm_extraction_from_chunk(self):
        """Verify CRM extraction from chunked content."""
        text = "Dr. Teste CRM/AM 99999 Clínica Geral"
        results = extract_crm(text)
        assert len(results) == 1
        assert results[0].entity_type == "doctor"
        assert results[0].confidence == 1.0

    def test_currency_extraction_from_chunk(self):
        """Verify price extraction from chunked content."""
        text = "Consulta R$ 150,00"
        results = extract_currency(text)
        assert len(results) == 1
        assert results[0].entity_type == "price"
        assert results[0].extracted_data["price"] == 150.0

    def test_insurance_extraction(self):
        """Verify insurance extraction with known plans."""
        text = "Aceitamos Bradesco Saúde e Amil"
        results = extract_insurance(text, ["Bradesco Saúde", "Amil", "Unimed"])
        assert len(results) == 2
        names = {r.extracted_data["insurance_name"] for r in results}
        assert names == {"Bradesco Saúde", "Amil"}

    def test_full_pipeline_chunking_and_extraction(self):
        """Test that a full document chunks correctly and CRM is extractable."""
        text = """
# Manual da Clínica

## Médicos

Dr. Carlos - CRM/SP 11111 - Cardiologia
Dra. Ana - CRM/MG 22222 - Pediatria

## Convênios

Aceitos: Bradesco Saúde, Amil, Unimed

## Tabela de Preços

Consulta Cardiologia: R$ 250,00
Consulta Pediatria: R$ 180,00
"""
        chunks = semantic_chunk(text)
        assert len(chunks) >= 1

        # Extract from all chunks
        all_doctors = []
        all_prices = []
        for chunk in chunks:
            all_doctors.extend(extract_crm(chunk.content))
            all_prices.extend(extract_currency(chunk.content))

        assert len(all_doctors) >= 2  # At least 2 doctors
        assert len(all_prices) >= 2  # At least 2 prices

    def test_no_chunk_exceeds_hard_limit(self):
        """Verify HARD_MAX is respected across all chunks."""
        text = "A" * 2000
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content) <= 1000

    def test_minimum_chunk_size_filtered(self):
        """Verify chunks below MIN_CHUNK are not returned."""
        text = "x"
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content) >= 50


class TestExtractionApprovalLogic:
    """Test extraction approval service logic (without DB)."""

    def test_crm_extraction_confidence_deterministic(self):
        """Deterministic CRM extraction has confidence 1.0."""
        text = "Dr. Teste CRM/SP 99999 Clínica"
        results = extract_crm(text)
        for r in results:
            assert r.confidence == 1.0
            assert r.extraction_method == "deterministic"
            assert r.requires_review is False

    def test_price_extraction_confidence_deterministic(self):
        """Deterministic price extraction has confidence 1.0."""
        text = "R$ 500,00"
        results = extract_currency(text)
        for r in results:
            assert r.confidence == 1.0
            assert r.extraction_method == "deterministic"

    def test_insurance_confidence_deterministic(self):
        """Insurance matching is deterministic with confidence 1.0."""
        text = "Plano Amil aceito"
        results = extract_insurance(text, ["Amil"])
        for r in results:
            assert r.confidence == 1.0
            assert r.extraction_method == "deterministic"