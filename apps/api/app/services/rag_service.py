"""
RAG Service — document ingestion, embedding generation and retrieval.

Embedding providers (SEPARADOS do LLM provider):
  local  → fastembed ONNX (gratuito, sem API key, 384 dims, PT-BR)  ← padrão para EMBEDDING_PROVIDER=auto sem keys
  openai → text-embedding-3-small (1536 dims, requires OPENAI_API_KEY)
  gemini → text-embedding-004 (768 dims, requires GEMINI_API_KEY)
  auto   → detecta: openai → gemini → local → None (text search fallback)

IMPORTANTE: Groq NÃO suporta embeddings. Se LLM_PROVIDER=groq,
configure EMBEDDING_PROVIDER separado (local, openai ou gemini).

Retrieval logs:
  [RAG:embedding] provider=local model=... dim=384 latency=0.12s status=ok
  [RAG:query] retrieval_mode=vector top_k=5 results=3
  [RAG:query] retrieval_mode=text top_k=5 results=2
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rag import RagDocument
from app.repositories.rag_repository import RagRepository
from app.schemas.rag import RagIngestResponse, RagQueryResult
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# ─── Local model singleton (fastembed) ───────────────────────────────────────

_local_model: Any = None
_local_model_lock: asyncio.Lock | None = None
_local_model_name: str | None = None


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


# ─── Embedding helpers ────────────────────────────────────────────────────────

def _log_embedding(result: list[float] | None, provider: str, t0: float) -> None:
    latency = time.monotonic() - t0
    if result:
        logger.info(
            "[RAG:embedding] provider=%s dim=%d latency=%.3fs status=ok",
            provider, len(result), latency,
        )
    else:
        logger.warning(
            "[RAG:embedding] provider=%s latency=%.3fs status=failed",
            provider, latency,
        )


async def _openai_embedding(text: str) -> list[float] | None:
    """OpenAI text-embedding-3-small (1536 dims)."""
    import httpx
    model = settings.embedding_model or "text-embedding-3-small"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"input": text, "model": model},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        logger.exception("[RAG:embedding] OpenAI embedding failed (model=%s)", model)
        return None


async def _gemini_embedding(text: str) -> list[float] | None:
    """Gemini text-embedding-004 (768 dims)."""
    import httpx
    model = settings.embedding_model or "text-embedding-004"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":embedContent?key={settings.gemini_api_key}"
    )
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
            return resp.json()["embedding"]["values"]
    except Exception:
        logger.exception("[RAG:embedding] Gemini embedding failed (model=%s)", model)
        return None


async def _local_embedding(text: str) -> list[float] | None:
    """
    Local embedding via fastembed (ONNX Runtime — sem PyTorch, sem API key).

    Modelo padrão: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
      - 384 dims
      - Multilíngue (excelente para PT-BR)
      - Download único ~90MB, armazenado em cache

    O modelo é inicializado lazy (primeiro uso) e mantido em memória.
    """
    global _local_model, _local_model_lock, _local_model_name

    try:
        from fastembed import TextEmbedding
    except ImportError:
        logger.error(
            "[RAG:embedding] fastembed não instalado. "
            "Instale com: pip install fastembed  "
            "Ou adicione EMBEDDING_PROVIDER=openai com sua OPENAI_API_KEY."
        )
        return None

    model_name = settings.embedding_model or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Lazy initialization with lock (thread-safe singleton)
    if _local_model is None:
        if _local_model_lock is None:
            _local_model_lock = asyncio.Lock()
        async with _local_model_lock:
            if _local_model is None:
                logger.info(
                    "[RAG:embedding] Inicializando modelo local fastembed: %s "
                    "(download ~90MB no primeiro uso)", model_name,
                )
                loop = asyncio.get_event_loop()
                try:
                    _local_model = await loop.run_in_executor(
                        None, lambda: TextEmbedding(model_name=model_name)
                    )
                    _local_model_name = model_name
                    logger.info("[RAG:embedding] Modelo local carregado: %s", model_name)
                except Exception:
                    logger.exception("[RAG:embedding] Falha ao carregar modelo local")
                    return None

    try:
        loop = asyncio.get_event_loop()
        embeddings_gen = await loop.run_in_executor(
            None, lambda: list(_local_model.embed([text]))
        )
        return embeddings_gen[0].tolist()
    except Exception:
        logger.exception("[RAG:embedding] Falha ao gerar embedding local")
        return None


async def get_embedding(text: str) -> list[float] | None:
    """
    Get embedding vector for text using the configured provider.

    Provider selection respects settings.embedding_provider:
      - "local"  → fastembed (384 dims, gratuito, sem API key) — RECOMENDADO
      - "openai" → OpenAI text-embedding-3-small (1536 dims, pago)
      - "gemini" → Gemini text-embedding-004 (768 dims, free tier)
      - "auto"   → detecta disponível: openai → gemini → local → None

    IMPORTANTE: "groq" NÃO é um provider de embeddings válido.
    Groq só suporta LLM (geração de texto). Configure EMBEDDING_PROVIDER
    separado do LLM_PROVIDER.
    """
    t0 = time.monotonic()
    provider = (settings.embedding_provider or "auto").strip().lower()

    # Guard: Groq não suporta embeddings
    if provider == "groq":
        logger.warning(
            "[RAG:embedding] ERRO CONFIG: Groq não suporta embeddings. "
            "Use EMBEDDING_PROVIDER=local (gratuito) ou openai/gemini. "
            "Redirecionando para auto-detect."
        )
        provider = "auto"

    # ── Explicit: local ───────────────────────────────────────────────────────
    if provider == "local":
        result = await _local_embedding(text)
        _log_embedding(result, "local", t0)
        return result

    # ── Explicit: openai ──────────────────────────────────────────────────────
    if provider == "openai":
        if not settings.openai_api_key:
            logger.error(
                "[RAG:embedding] EMBEDDING_PROVIDER=openai mas OPENAI_API_KEY não configurada. "
                "Use EMBEDDING_PROVIDER=local para embeddings gratuitos."
            )
            return None
        result = await _openai_embedding(text)
        _log_embedding(result, "openai", t0)
        return result

    # ── Explicit: gemini ──────────────────────────────────────────────────────
    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.error(
                "[RAG:embedding] EMBEDDING_PROVIDER=gemini mas GEMINI_API_KEY não configurada."
            )
            return None
        result = await _gemini_embedding(text)
        _log_embedding(result, "gemini", t0)
        return result

    # ── Auto-detect: openai → gemini → local → None ──────────────────────────
    if settings.openai_api_key:
        result = await _openai_embedding(text)
        if result:
            _log_embedding(result, "openai", t0)
            return result

    if settings.gemini_api_key:
        result = await _gemini_embedding(text)
        if result:
            _log_embedding(result, "gemini", t0)
            return result

    # Try local as last resort
    result = await _local_embedding(text)
    if result:
        _log_embedding(result, "local", t0)
        return result

    logger.warning(
        "[RAG:embedding] Nenhum provider disponível — fallback para busca textual. "
        "Dica: defina EMBEDDING_PROVIDER=local para embeddings gratuitos sem API key."
    )
    return None


# ─── RAG Service ─────────────────────────────────────────────────────────────

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
        Ingest a document: chunk → embed → persist.
        Chunks without embedding (provider unavailable) are stored with embedding=NULL
        and can be reindexed later via /api/v1/rag/reindex.
        """
        doc = await self.repo.create_document(title, category, source_path)

        chunks = chunk_text(
            content,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )

        embedded = 0
        failed = 0

        for idx, chunk_content in enumerate(chunks):
            try:
                embedding = await get_embedding(chunk_content)
            except Exception:
                logger.exception("[RAG:ingest] Embedding falhou no chunk %d de '%s'", idx, title)
                embedding = None
                failed += 1

            if embedding:
                embedded += 1
            else:
                failed += 1

            await self.repo.create_chunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_content,
                embedding=embedding,
                metadata_json=json.dumps({"source": source_path or title, "chunk": idx}),
            )

        logger.info(
            "[RAG:ingest] Documento '%s' — chunks=%d embedded=%d sem_embedding=%d provider=%s",
            title, len(chunks), embedded, failed,
            (settings.embedding_provider or "auto"),
        )

        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.ingested",
            resource_type="rag_document",
            resource_id=str(doc.id),
            payload={
                "title": title,
                "chunks": len(chunks),
                "embedded": embedded,
                "sem_embedding": failed,
                "embedding_provider": settings.embedding_provider or "auto",
            },
        )

        return RagIngestResponse(document_id=doc.id, chunks_created=len(chunks))

    async def query(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[RagQueryResult]:
        """
        Query the RAG index.
        Tries vector search first; falls back to text search if no embeddings available.
        Logs: retrieval_mode=vector|text, top_k, results count.
        """
        k = top_k or settings.rag_top_k
        t0 = time.monotonic()
        embedding = await get_embedding(query_text)

        if embedding:
            rows = await self.repo.search_similar(embedding, top_k=k, category=category)
            latency = time.monotonic() - t0
            logger.info(
                "[RAG:query] retrieval_mode=vector top_k=%d results=%d latency=%.3fs",
                k, len(rows), latency,
            )
            if rows:
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
            # No vector results — fall through to text search
            logger.info("[RAG:query] Vector search sem resultados — tentando busca textual")

        # Text search fallback
        rows = await self.repo.text_search(query_text, top_k=k, category=category)
        latency = time.monotonic() - t0
        logger.info(
            "[RAG:query] retrieval_mode=text top_k=%d results=%d latency=%.3fs",
            k, len(rows), latency,
        )
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

    async def text_search(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[dict]:
        """Text-based search fallback (ILIKE on chunk content)."""
        k = top_k or settings.rag_top_k
        return await self.repo.text_search(query_text, top_k=k, category=category)

    async def reindex_document(
        self,
        doc_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Reprocess chunks without embedding.
        If doc_id is None, reindexes ALL documents.
        Returns {"processed": N, "embedded": N, "failed": N}.
        """
        chunks = await self.repo.get_chunks_without_embedding(doc_id)
        processed = 0
        embedded = 0
        failed = 0

        logger.info(
            "[RAG:reindex] Iniciando reindexação — doc_id=%s chunks_sem_embedding=%d",
            str(doc_id) if doc_id else "all", len(chunks),
        )

        for chunk in chunks:
            processed += 1
            try:
                embedding = await get_embedding(chunk.content)
                if embedding:
                    await self.repo.update_chunk_embedding(chunk.id, embedding)
                    embedded += 1
                    logger.debug("[RAG:reindex] Chunk %s embutido (dim=%d)", chunk.id, len(embedding))
                else:
                    failed += 1
                    logger.warning("[RAG:reindex] Chunk %s sem embedding — provider indisponível", chunk.id)
            except Exception:
                logger.exception("[RAG:reindex] Falha no chunk %s", chunk.id)
                failed += 1

        logger.info(
            "[RAG:reindex] Concluído — processed=%d embedded=%d failed=%d",
            processed, embedded, failed,
        )
        return {"processed": processed, "embedded": embedded, "failed": failed}

    async def get_stats(self) -> dict:
        """
        Returns embedding stats for the RAG index.
        Used by admin panel to show "sem embedding" counts.
        """
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
