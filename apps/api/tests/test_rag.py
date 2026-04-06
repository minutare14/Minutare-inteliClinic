"""Tests for RAG pipeline — real DB text search."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagDocument, RagChunk
from app.services.rag_service import RagService, chunk_text


class TestChunking:
    def test_chunk_text_basic(self):
        text = "A" * 100
        chunks = chunk_text(text, chunk_size=30, overlap=10)
        assert len(chunks) > 1
        assert all(len(c) <= 30 for c in chunks)

    def test_chunk_text_overlap(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_text(text, chunk_size=10, overlap=3)
        # With overlap, second chunk should start at position 7
        assert len(chunks) >= 3

    def test_chunk_text_empty(self):
        chunks = chunk_text("", chunk_size=100, overlap=10)
        assert chunks == []

    def test_chunk_text_small(self):
        chunks = chunk_text("Hello", chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == "Hello"


@pytest.mark.asyncio
class TestRagIngest:
    async def test_ingest_document(self, session: AsyncSession):
        svc = RagService(session)
        result = await svc.ingest_document(
            title="Test Doc",
            content="A clinica funciona de segunda a sexta das 8h as 18h. "
                    "Aceitamos convenios Unimed e Bradesco Saude.",
            category="operacional",
        )
        assert result.document_id is not None
        assert result.chunks_created >= 1

    async def test_ingest_creates_chunks(self, session: AsyncSession):
        svc = RagService(session)
        long_content = "Informacao importante. " * 100  # ~2300 chars
        result = await svc.ingest_document(
            title="Long Doc", content=long_content, category="faq",
        )
        assert result.chunks_created > 1


@pytest.mark.asyncio
class TestRagTextSearch:
    async def test_search_finds_matching_chunks(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("clinica funciona segunda sexta")
        assert len(results) > 0
        # Should find the chunk about business hours
        found_content = " ".join(r["content"] for r in results)
        assert "segunda" in found_content.lower() or "funciona" in found_content.lower()

    async def test_search_convenio(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("convenios unimed bradesco")
        assert len(results) > 0

    async def test_search_endereco(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("endereco flores telefone")
        assert len(results) > 0

    async def test_search_no_results(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("xyz unicornio inexistente")
        assert len(results) == 0

    async def test_search_cancelamento(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("cancelamento antecedencia cobranca")
        assert len(results) > 0
        found = " ".join(r["content"] for r in results)
        assert "24 horas" in found or "cancelamento" in found.lower()


@pytest.mark.asyncio
class TestRagListDocuments:
    async def test_list_all(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        docs = await svc.list_documents()
        assert len(docs) >= 1

    async def test_list_by_category(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        docs = await svc.list_documents(category="operacional")
        assert len(docs) >= 1
        assert all(d.category == "operacional" for d in docs)
