"""Tests for the runtime RAG pipeline."""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.rag import RagChunk, RagDocument
from app.services.rag_service import RagService, chunk_text


async def _fake_embedding(_: str, *, phase: str = "query") -> list[float]:
    base = 0.1 if phase == "query" else 0.2
    return [base] * 384


class TestChunking:
    def test_chunk_text_basic(self):
        text = "A" * 100
        chunks = chunk_text(text, chunk_size=30, overlap=10)
        assert len(chunks) > 1
        assert all(len(c) <= 30 for c in chunks)

    def test_chunk_text_overlap(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_text(text, chunk_size=10, overlap=3)
        assert len(chunks) >= 3

    def test_chunk_text_empty(self):
        chunks = chunk_text("", chunk_size=100, overlap=10)
        assert chunks == []

    def test_chunk_text_small(self):
        chunks = chunk_text("Hello", chunk_size=100, overlap=10)
        assert chunks == ["Hello"]

    def test_chunk_text_validates_overlap(self):
        with pytest.raises(ValueError):
            chunk_text("abc", chunk_size=10, overlap=10)


@pytest.mark.asyncio
class TestRagIngest:
    async def test_ingest_document_generates_embeddings(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.rag_service.get_embedding", _fake_embedding)

        svc = RagService(session)
        result = await svc.ingest_document(
            title="Test Doc",
            content=(
                "A clinica funciona de segunda a sexta das 8h as 18h. "
                "Aceitamos convenios Unimed e Bradesco Saude."
            ),
            category="operacional",
        )

        assert result.document_id is not None
        assert result.chunks_created >= 1
        assert result.chunks_embedded == result.chunks_created
        assert result.chunks_failed == 0

        chunks = await svc.get_chunks(result.document_id)
        assert chunks
        assert all(chunk.embedded is True for chunk in chunks)
        assert all(chunk.embedding is not None for chunk in chunks)
        assert all(chunk.embedding_error is None for chunk in chunks)

    async def test_ingest_creates_multiple_chunks(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.rag_service.get_embedding", _fake_embedding)

        svc = RagService(session)
        long_content = "Informacao importante. " * 100
        result = await svc.ingest_document(
            title="Long Doc",
            content=long_content,
            category="faq",
        )
        assert result.chunks_created > 1
        assert result.chunks_embedded == result.chunks_created

    async def test_reindex_backfills_missing_embeddings(self, session: AsyncSession, monkeypatch):
        monkeypatch.setattr("app.services.rag_service.get_embedding", _fake_embedding)

        doc = RagDocument(
            id=uuid.uuid4(),
            title="Legacy Doc",
            category="faq",
            status="active",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        chunk = RagChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content="Conteudo legado sem embedding",
            embedded=False,
            embedding_error="legacy_missing_embedding",
        )
        session.add(chunk)
        await session.commit()

        svc = RagService(session)
        result = await svc.reindex_document(force=False)
        assert result["processed"] == 1
        assert result["embedded"] == 1
        assert result["failed"] == 0
        assert result["chunks_without_embedding"] == 0

        updated = (await svc.get_chunks(doc.id))[0]
        assert updated.embedded is True
        assert updated.embedding is not None
        assert updated.embedding_error is None


@pytest.mark.asyncio
class TestRagRetrieval:
    async def test_query_uses_text_fallback_when_no_embeddings(
        self,
        session: AsyncSession,
        sample_rag_data,
        monkeypatch,
    ):
        async def fake_get_embedding(*args, **kwargs):
            return None

        svc = RagService(session)
        monkeypatch.setattr("app.services.rag_service.get_embedding", fake_get_embedding)

        result = await svc.query_with_metadata("convenios unimed bradesco")
        assert result.retrieval_mode == "text"
        assert result.rag_used is True
        assert result.results
        assert "Unimed" in result.results[0].content or "Bradesco" in result.results[0].content

    async def test_query_prefers_vector_when_embeddings_exist(self, session: AsyncSession, monkeypatch):
        svc = RagService(session)

        async def fake_has_embeddings(category=None):
            return True

        async def fake_search_similar(query_embedding, top_k=5, category=None):
            return [
                {
                    "chunk_id": uuid.uuid4(),
                    "document_id": uuid.uuid4(),
                    "content": "Texto retornado pela busca vetorial",
                    "document_title": "Documento Vetorial",
                    "category": "faq",
                    "score": 0.98,
                }
            ]

        monkeypatch.setattr("app.services.rag_service.get_embedding", _fake_embedding)
        monkeypatch.setattr(svc.repo, "has_embeddings", fake_has_embeddings)
        monkeypatch.setattr(svc.repo, "search_similar", fake_search_similar)

        result = await svc.query_with_metadata("texto vetorial")
        assert result.retrieval_mode == "vector"
        assert result.rag_used is True
        assert result.results[0].document_title == "Documento Vetorial"

    async def test_text_search_finds_matching_chunks(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("clinica funciona segunda sexta")
        assert len(results) > 0
        found_content = " ".join(r["content"] for r in results)
        assert "segunda" in found_content.lower() or "funciona" in found_content.lower()

    async def test_text_search_cancelamento(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        results = await svc.text_search("cancelamento antecedencia cobranca")
        assert len(results) > 0
        found = " ".join(r["content"] for r in results)
        assert "24 horas" in found or "cancelamento" in found.lower()


@pytest.mark.asyncio
class TestRagStats:
    async def test_list_all(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        docs = await svc.list_documents()
        assert len(docs) >= 1

    async def test_list_by_category(self, session: AsyncSession, sample_rag_data):
        svc = RagService(session)
        docs = await svc.list_documents(category="operacional")
        assert len(docs) >= 1
        assert all(d.category == "operacional" for d in docs)
