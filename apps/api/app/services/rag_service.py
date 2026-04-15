"""
RAG service: ingestion, embedding generation, reindexing and retrieval.

Embedding providers are intentionally separated from the text-generation LLM.
Groq stays on text generation only. Local embeddings run with sentence-transformers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rag import RagDocument
from app.repositories.rag_repository import RagRepository
from app.schemas.rag import RagIngestResponse, RagQueryResult
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_local_model = None
_local_model_lock: asyncio.Lock | None = None
_local_model_name: str | None = None


@dataclass
class RagQueryExecution:
    results: list[RagQueryResult]
    retrieval_mode: str
    rag_used: bool
    embedded_chunks_available: bool
    query_embedding_generated: bool


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if chunk_size <= 0:
        raise ValueError("rag_chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("rag_chunk_overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += step
    return chunks


def _configured_embedding_provider() -> str:
    provider = (settings.embedding_provider or "local").strip().lower()
    if provider == "groq":
        logger.error(
            "[RAG:embedding] embedding_generated=false provider=groq reason=invalid_provider "
            "Groq does not support embeddings. Falling back to local."
        )
        return "local"
    return provider or "local"


def _default_embedding_model(provider: str) -> str:
    if settings.embedding_model:
        return settings.embedding_model
    if provider == "openai":
        return "text-embedding-3-small"
    if provider == "gemini":
        return "text-embedding-004"
    return "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _normalize_embedding(vector: list[float] | None, provider: str) -> list[float] | None:
    if vector is None:
        return None
    if settings.embedding_dim and len(vector) != settings.embedding_dim:
        logger.error(
            "[RAG:embedding] embedding_generated=false provider=%s reason=dimension_mismatch "
            "expected_dim=%d actual_dim=%d",
            provider,
            settings.embedding_dim,
            len(vector),
        )
        return None
    return vector


def _log_embedding(
    *,
    vector: list[float] | None,
    provider: str,
    model: str,
    phase: str,
    t0: float,
    error: str | None = None,
) -> None:
    latency = time.monotonic() - t0
    if vector is not None:
        logger.info(
            "[RAG:embedding] phase=%s provider=%s model=%s embedding_generated=true dim=%d latency=%.3fs",
            phase,
            provider,
            model,
            len(vector),
            latency,
        )
        return

    logger.warning(
        "[RAG:embedding] phase=%s provider=%s model=%s embedding_generated=false latency=%.3fs error=%s",
        phase,
        provider,
        model,
        latency,
        error or "unknown",
    )


def _log_chunk_status(
    *,
    operation: str,
    document_id: uuid.UUID,
    chunk_index: int,
    chunk_status: str,
    embedding_generated: bool,
    error: str | None = None,
) -> None:
    logger.info(
        "[RAG:chunk] operation=%s document_id=%s chunk_index=%d chunk_index_status=%s "
        "embedding_generated=%s error=%s",
        operation,
        document_id,
        chunk_index,
        chunk_status,
        str(embedding_generated).lower(),
        error or "none",
    )


async def _openai_embedding(text: str, *, phase: str) -> list[float] | None:
    import httpx

    provider = "openai"
    model = _default_embedding_model(provider)
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"input": text, "model": model},
                timeout=30.0,
            )
            resp.raise_for_status()
            vector = resp.json()["data"][0]["embedding"]
            vector = _normalize_embedding(vector, provider)
            _log_embedding(vector=vector, provider=provider, model=model, phase=phase, t0=t0)
            return vector
    except Exception as exc:
        _log_embedding(
            vector=None,
            provider=provider,
            model=model,
            phase=phase,
            t0=t0,
            error=str(exc),
        )
        logger.exception("[RAG:embedding] OpenAI embedding failed")
        return None


async def _gemini_embedding(text: str, *, phase: str) -> list[float] | None:
    import httpx

    provider = "gemini"
    model = _default_embedding_model(provider)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":embedContent?key={settings.gemini_api_key}"
    )
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": text}]},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            vector = resp.json()["embedding"]["values"]
            vector = _normalize_embedding(vector, provider)
            _log_embedding(vector=vector, provider=provider, model=model, phase=phase, t0=t0)
            return vector
    except Exception as exc:
        _log_embedding(
            vector=None,
            provider=provider,
            model=model,
            phase=phase,
            t0=t0,
            error=str(exc),
        )
        logger.exception("[RAG:embedding] Gemini embedding failed")
        return None


async def _local_embedding(text: str, *, phase: str) -> list[float] | None:
    """Local embedding via sentence-transformers."""
    global _local_model, _local_model_lock, _local_model_name

    provider = "local"
    model_name = _default_embedding_model(provider)
    t0 = time.monotonic()

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        _log_embedding(
            vector=None,
            provider=provider,
            model=model_name,
            phase=phase,
            t0=t0,
            error="sentence-transformers not installed",
        )
        logger.exception("[RAG:embedding] sentence-transformers not installed: %s", exc)
        return None

    if _local_model is None:
        if _local_model_lock is None:
            _local_model_lock = asyncio.Lock()
        async with _local_model_lock:
            if _local_model is None:
                logger.info(
                    "[RAG:embedding] provider=local model=%s status=loading",
                    model_name,
                )
                loop = asyncio.get_running_loop()
                try:
                    _local_model = await loop.run_in_executor(
                        None,
                        lambda: SentenceTransformer(model_name),
                    )
                    _local_model_name = model_name
                    logger.info(
                        "[RAG:embedding] provider=local model=%s status=ready",
                        model_name,
                    )
                except Exception as exc:
                    _log_embedding(
                        vector=None,
                        provider=provider,
                        model=model_name,
                        phase=phase,
                        t0=t0,
                        error=str(exc),
                    )
                    logger.exception("[RAG:embedding] Failed to load local model")
                    return None

    try:
        loop = asyncio.get_running_loop()
        matrix = await loop.run_in_executor(
            None,
            lambda: _local_model.encode(  # type: ignore[union-attr]
                [text],
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
        )
        row = matrix[0]
        vector = row.tolist() if hasattr(row, "tolist") else list(row)
        vector = _normalize_embedding(vector, provider)
        _log_embedding(vector=vector, provider=provider, model=_local_model_name or model_name, phase=phase, t0=t0)
        return vector
    except Exception as exc:
        _log_embedding(
            vector=None,
            provider=provider,
            model=_local_model_name or model_name,
            phase=phase,
            t0=t0,
            error=str(exc),
        )
        logger.exception("[RAG:embedding] Failed to generate local embedding")
        return None


async def get_embedding(text: str, *, phase: str = "query") -> list[float] | None:
    """
    Return an embedding using the configured embedding provider.

    Provider selection respects settings.embedding_provider:
      - local  -> sentence-transformers (recommended)
      - openai -> OpenAI embeddings
      - gemini -> Gemini embeddings
      - auto   -> openai -> gemini -> local
    """
    provider = _configured_embedding_provider()

    if provider == "local":
        return await _local_embedding(text, phase=phase)

    if provider == "openai":
        if not settings.openai_api_key:
            logger.error(
                "[RAG:embedding] phase=%s provider=openai embedding_generated=false "
                "error=openai_api_key_missing",
                phase,
            )
            return None
        return await _openai_embedding(text, phase=phase)

    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.error(
                "[RAG:embedding] phase=%s provider=gemini embedding_generated=false "
                "error=gemini_api_key_missing",
                phase,
            )
            return None
        return await _gemini_embedding(text, phase=phase)

    if settings.openai_api_key:
        vector = await _openai_embedding(text, phase=phase)
        if vector is not None:
            return vector

    if settings.gemini_api_key:
        vector = await _gemini_embedding(text, phase=phase)
        if vector is not None:
            return vector

    return await _local_embedding(text, phase=phase)


def _rows_to_results(rows: list[dict]) -> list[RagQueryResult]:
    return [
        RagQueryResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            title=r["document_title"],
            content=r["content"],
            score=float(r["score"]),
            document_title=r["document_title"],
            category=r["category"],
        )
        for r in rows
    ]


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _query_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"\w+", _normalize_for_match(text)):
        if len(token) < 4:
            continue
        if token not in terms:
            terms.append(token)
        if len(token) >= 5:
            stem = token[:5]
            if stem not in terms:
                terms.append(stem)
    return terms


def _rerank_vector_rows(query_text: str, rows: list[dict]) -> list[dict]:
    if not rows:
        return rows

    query_terms = _query_terms(query_text)
    if not query_terms:
        return rows

    def rank(row: dict) -> tuple[float, float]:
        haystack = _normalize_for_match(
            f"{row.get('document_title', '')} {row.get('content', '')}"
        )
        lexical_hits = sum(1 for term in query_terms if term in haystack)
        lexical_score = lexical_hits / len(query_terms)
        combined_score = float(row.get("score", 0.0)) + (lexical_score * 0.35)
        return combined_score, float(row.get("score", 0.0))

    return sorted(rows, key=rank, reverse=True)


class RagService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = RagRepository(session)
        self.audit = AuditService(session)

    async def ingest_document(
        self,
        title: str,
        content: str,
        category: str = "general",
        source_path: str | None = None,
    ) -> RagIngestResponse:
        """
        Ingest a document with the full pipeline:
        parse -> chunk -> generate embedding -> persist -> mark embedded=true/false.
        """
        doc = await self.repo.create_document(title, category, source_path)
        chunks = chunk_text(
            content,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )

        embedded_count = 0
        failed_count = 0
        provider = _configured_embedding_provider()

        for idx, chunk_content in enumerate(chunks):
            embedding: list[float] | None = None
            chunk_status = "failed"
            error: str | None = None

            try:
                embedding = await get_embedding(chunk_content, phase="ingest")
                if embedding is not None:
                    embedded_count += 1
                    chunk_status = "embedded"
                else:
                    failed_count += 1
                    error = "embedding_unavailable"
            except Exception as exc:
                failed_count += 1
                error = str(exc)
                logger.exception(
                    "[RAG:ingest] document_id=%s title=%s chunk_index=%d error=%s",
                    doc.id,
                    title,
                    idx,
                    exc,
                )

            await self.repo.create_chunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_content,
                embedding=embedding,
                embedded=embedding is not None,
                embedding_error=error,
                metadata_json=json.dumps({"source": source_path or title, "chunk": idx}),
            )
            _log_chunk_status(
                operation="ingest",
                document_id=doc.id,
                chunk_index=idx,
                chunk_status=chunk_status,
                embedding_generated=embedding is not None,
                error=error,
            )

        logger.info(
            "[RAG:ingest] document_id=%s title=%s chunks_total=%d chunks_embedded=%d "
            "chunks_failed=%d embedding_provider=%s",
            doc.id,
            title,
            len(chunks),
            embedded_count,
            failed_count,
            provider,
        )

        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.ingested",
            resource_type="rag_document",
            resource_id=str(doc.id),
            payload={
                "title": title,
                "chunks_total": len(chunks),
                "chunks_embedded": embedded_count,
                "chunks_failed": failed_count,
                "embedding_provider": provider,
            },
        )

        return RagIngestResponse(
            document_id=doc.id,
            chunks_created=len(chunks),
            chunks_embedded=embedded_count,
            chunks_failed=failed_count,
            embedding_provider=provider,
        )

    async def query(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[RagQueryResult]:
        execution = await self.query_with_metadata(query_text, top_k=top_k, category=category)
        return execution.results

    async def query_with_metadata(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> RagQueryExecution:
        """
        Query the RAG index with explicit retrieval mode tracking.

        Decision order:
          1. If embedded chunks exist, try vector search.
          2. If vector is unavailable or empty, fall back to text search.
        """
        k = top_k or settings.rag_top_k
        t0 = time.monotonic()

        embedded_chunks_available = await self.repo.has_embeddings(category)
        query_embedding_generated = False

        if embedded_chunks_available:
            query_embedding = await get_embedding(query_text, phase="query")
            query_embedding_generated = query_embedding is not None

            if query_embedding is not None:
                try:
                    rows = await self.repo.search_similar(query_embedding, top_k=k, category=category)
                    rows = _rerank_vector_rows(query_text, rows)
                    latency = time.monotonic() - t0
                    if rows:
                        logger.info(
                            "[RAG:query] retrieval_mode=vector top_k=%d results=%d rag_used=true latency=%.3fs",
                            k,
                            len(rows),
                            latency,
                        )
                        return RagQueryExecution(
                            results=_rows_to_results(rows),
                            retrieval_mode="vector",
                            rag_used=True,
                            embedded_chunks_available=True,
                            query_embedding_generated=True,
                        )

                    logger.info(
                        "[RAG:query] retrieval_mode=vector top_k=%d results=0 rag_used=false "
                        "latency=%.3fs fallback=text",
                        k,
                        latency,
                    )
                except Exception as exc:
                    await self.repo.session.rollback()
                    logger.exception(
                        "[RAG:query] retrieval_mode=vector failed, falling back to text: %s",
                        exc,
                    )
            else:
                logger.warning(
                    "[RAG:query] retrieval_mode=text rag_used=false reason=query_embedding_unavailable",
                )
        else:
            logger.info(
                "[RAG:query] retrieval_mode=text rag_used=false reason=no_embedded_chunks",
            )

        rows = await self.repo.text_search(query_text, top_k=k, category=category)
        latency = time.monotonic() - t0
        logger.info(
            "[RAG:query] retrieval_mode=text top_k=%d results=%d rag_used=%s latency=%.3fs",
            k,
            len(rows),
            str(bool(rows)).lower(),
            latency,
        )
        return RagQueryExecution(
            results=_rows_to_results(rows),
            retrieval_mode="text",
            rag_used=bool(rows),
            embedded_chunks_available=embedded_chunks_available,
            query_embedding_generated=query_embedding_generated,
        )

    async def text_search(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[dict]:
        """Text-based search fallback."""
        k = top_k or settings.rag_top_k
        return await self.repo.text_search(query_text, top_k=k, category=category)

    async def reindex_document(
        self,
        doc_id: uuid.UUID | None = None,
        *,
        force: bool = False,
    ) -> dict:
        """
        Reprocess chunk embeddings.

        force=False reindexes only missing/failed chunks.
        force=True regenerates embeddings for all chunks in scope.
        """
        chunks = await self.repo.get_chunks_for_reindex(doc_id, force=force)
        processed = 0
        embedded_count = 0
        failed_count = 0
        documents_processed = len({chunk.document_id for chunk in chunks})

        logger.info(
            "[RAG:reindex] doc_scope=%s force=%s documents=%d chunks=%d",
            str(doc_id) if doc_id else "all",
            str(force).lower(),
            documents_processed,
            len(chunks),
        )

        for chunk in chunks:
            processed += 1
            try:
                embedding = await get_embedding(chunk.content, phase="reindex")
                if embedding is not None:
                    await self.repo.update_chunk_indexing(
                        chunk.id,
                        embedding=embedding,
                        embedded=True,
                        embedding_error=None,
                    )
                    embedded_count += 1
                    _log_chunk_status(
                        operation="reindex",
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        chunk_status="embedded",
                        embedding_generated=True,
                    )
                    continue

                failed_count += 1
                await self.repo.update_chunk_indexing(
                    chunk.id,
                    embedding=None,
                    embedded=False,
                    embedding_error="embedding_unavailable",
                )
                _log_chunk_status(
                    operation="reindex",
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    chunk_status="failed",
                    embedding_generated=False,
                    error="embedding_unavailable",
                )
            except Exception as exc:
                failed_count += 1
                await self.repo.update_chunk_indexing(
                    chunk.id,
                    embedding=None,
                    embedded=False,
                    embedding_error=str(exc),
                )
                _log_chunk_status(
                    operation="reindex",
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    chunk_status="failed",
                    embedding_generated=False,
                    error=str(exc),
                )
                logger.exception("[RAG:reindex] chunk_id=%s failed", chunk.id)

        stats = await self.repo.get_embedding_stats()
        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.reindexed",
            resource_type="rag_document",
            resource_id=str(doc_id) if doc_id else "all",
            payload={
                "documents_processed": documents_processed,
                "chunks_processed": processed,
                "chunks_embedded": embedded_count,
                "chunks_failed": failed_count,
                "force": force,
                "chunks_without_embedding": stats["chunks_without_embedding"],
                "coverage_pct": stats["coverage_pct"],
            },
        )

        logger.info(
            "[RAG:reindex] completed documents=%d processed=%d embedded=%d failed=%d "
            "chunks_without_embedding=%d coverage_pct=%.1f",
            documents_processed,
            processed,
            embedded_count,
            failed_count,
            stats["chunks_without_embedding"],
            stats["coverage_pct"],
        )
        return {
            "documents_processed": documents_processed,
            "processed": processed,
            "embedded": embedded_count,
            "failed": failed_count,
            "chunks_without_embedding": stats["chunks_without_embedding"],
            "coverage_pct": stats["coverage_pct"],
        }

    async def get_stats(self) -> dict:
        return await self.repo.get_embedding_stats()

    async def list_documents(self, category: str | None = None) -> list[RagDocument]:
        return await self.repo.list_documents(category)

    async def get_document(self, doc_id: uuid.UUID) -> RagDocument | None:
        return await self.repo.get_document(doc_id)

    async def get_chunks(self, doc_id: uuid.UUID):
        return await self.repo.get_chunks(doc_id)

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        deleted = await self.repo.delete_document(doc_id)
        if deleted:
            await self.audit.log_event(
                actor_type="human",
                actor_id="operator",
                action="document.deleted",
                resource_type="rag_document",
                resource_id=str(doc_id),
            )
        return deleted
