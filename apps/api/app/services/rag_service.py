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
from app.services.reranker_service import build_reranker, RerankResult
from app.core.embedding import (
    EmbeddingRuntimeConfig,
    default_embedding_dimension,
    default_embedding_model,
    normalize_embedding_provider,
)
from app.models.rag import RagDocument
from app.repositories.admin_repository import AdminRepository
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
    # Reranker metadata (populated when RAG_RERANKER_ENABLED=true)
    reranker_used: bool = False
    reranker_model: str | None = None
    reranker_top_k_initial: int = 0
    reranker_top_k_final: int = 0
    reranker_latency_ms: float = 0.0
    reranker_fallback: bool = False
    reranker_ranking_changed: bool = False


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


def _normalize_embedding(
    vector: list[float] | None,
    provider: str,
    *,
    expected_dim: int,
) -> list[float] | None:
    if vector is None:
        return None
    if expected_dim and len(vector) != expected_dim:
        logger.error(
            "[RAG:embedding] embedding_generated=false provider=%s reason=dimension_mismatch "
            "expected_dim=%d actual_dim=%d",
            provider,
            expected_dim,
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


async def _openai_embedding(
    text: str,
    *,
    phase: str,
    model: str,
    expected_dim: int,
) -> list[float] | None:
    import httpx

    provider = "openai"
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
            vector = _normalize_embedding(vector, provider, expected_dim=expected_dim)
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


async def _gemini_embedding(
    text: str,
    *,
    phase: str,
    model: str,
    expected_dim: int,
) -> list[float] | None:
    import httpx

    provider = "gemini"
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
            vector = _normalize_embedding(vector, provider, expected_dim=expected_dim)
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


async def _local_embedding(
    text: str,
    *,
    phase: str,
    model_name: str,
    expected_dim: int,
) -> list[float] | None:
    """Local embedding via sentence-transformers."""
    global _local_model, _local_model_lock, _local_model_name

    provider = "local"
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

    if _local_model is None or _local_model_name != model_name:
        if _local_model_lock is None:
            _local_model_lock = asyncio.Lock()
        async with _local_model_lock:
            if _local_model is None or _local_model_name != model_name:
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
        vector = _normalize_embedding(vector, provider, expected_dim=expected_dim)
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


async def get_embedding(
    text: str,
    *,
    phase: str = "query",
    embedding_config: EmbeddingRuntimeConfig | None = None,
) -> list[float] | None:
    """
    Return an embedding using the resolved embedding runtime config.
    """
    config = embedding_config or EmbeddingRuntimeConfig(
        provider=_normalize_runtime_provider(settings.embedding_provider or "local"),
        model=default_embedding_model(settings.embedding_provider or "local", settings.embedding_model),
        schema_dimension=settings.embedding_dim,
        source="env",
    )
    provider = config.provider

    if provider == "local":
        return await _local_embedding(
            text,
            phase=phase,
            model_name=config.model,
            expected_dim=config.schema_dimension,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            logger.error(
                "[RAG:embedding] phase=%s provider=openai embedding_generated=false "
                "error=openai_api_key_missing",
                phase,
            )
            return None
        return await _openai_embedding(
            text,
            phase=phase,
            model=config.model,
            expected_dim=config.schema_dimension,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.error(
                "[RAG:embedding] phase=%s provider=gemini embedding_generated=false "
                "error=gemini_api_key_missing",
                phase,
            )
            return None
        return await _gemini_embedding(
            text,
            phase=phase,
            model=config.model,
            expected_dim=config.schema_dimension,
        )

    if provider == "auto":
        candidates: list[str] = []
        if config.schema_dimension == default_embedding_dimension("openai") and settings.openai_api_key:
            candidates.append("openai")
        if config.schema_dimension == default_embedding_dimension("gemini") and settings.gemini_api_key:
            candidates.append("gemini")
        if config.schema_dimension == default_embedding_dimension("local"):
            candidates.append("local")

        for candidate in candidates:
            if candidate == "openai":
                vector = await _openai_embedding(
                    text,
                    phase=phase,
                    model=default_embedding_model("openai"),
                    expected_dim=config.schema_dimension,
                )
            elif candidate == "gemini":
                vector = await _gemini_embedding(
                    text,
                    phase=phase,
                    model=default_embedding_model("gemini"),
                    expected_dim=config.schema_dimension,
                )
            else:
                vector = await _local_embedding(
                    text,
                    phase=phase,
                    model_name=default_embedding_model("local"),
                    expected_dim=config.schema_dimension,
                )
            if vector is not None:
                return vector

        logger.error(
            "[RAG:embedding] phase=%s provider=auto embedding_generated=false "
            "error=no_provider_available_for_schema_dimension_%d",
            phase,
            config.schema_dimension,
        )
        return None

    return await _local_embedding(
        text,
        phase=phase,
        model_name=default_embedding_model("local"),
        expected_dim=config.schema_dimension,
    )


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


def _normalize_runtime_provider(raw_provider: str | None) -> str:
    provider = normalize_embedding_provider(raw_provider or "local")
    if provider == "groq":
        logger.error(
            "[RAG:config] invalid embedding provider 'groq' detected. Falling back to local."
        )
        return "local"
    if provider not in {"local", "openai", "gemini", "auto"}:
        logger.warning(
            "[RAG:config] invalid embedding provider '%s' detected. Falling back to local.",
            raw_provider,
        )
        return "local"
    return provider


class RagService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = RagRepository(session)
        self.admin_repo = AdminRepository(session)
        self.audit = AuditService(session)
        # Reranker: built from config. NoOp when RAG_RERANKER_ENABLED=false.
        self._reranker = build_reranker(
            enabled=settings.rag_reranker_enabled,
            model_name=settings.rag_reranker_model,
        )

    async def _resolve_embedding_config(self) -> EmbeddingRuntimeConfig:
        clinic_cfg = await self.admin_repo.get_clinic_settings(settings.clinic_id)

        env_provider = _normalize_runtime_provider(settings.embedding_provider or "local")
        env_model = default_embedding_model(
            env_provider if env_provider != "auto" else "local",
            settings.embedding_model if settings.embedding_model else None,
        )
        env_config = EmbeddingRuntimeConfig(
            provider=env_provider,
            model=env_model,
            schema_dimension=settings.embedding_dim,
            source="env",
        )
        config = env_config

        if clinic_cfg and clinic_cfg.embedding_provider:
            clinic_provider = _normalize_runtime_provider(clinic_cfg.embedding_provider)
            clinic_model = default_embedding_model(
                clinic_provider if clinic_provider != "auto" else "local",
                clinic_cfg.embedding_model,
            )
            clinic_config = EmbeddingRuntimeConfig(
                provider=clinic_provider,
                model=clinic_model,
                schema_dimension=settings.embedding_dim,
                source="clinic_settings",
            )
            clinic_error = self._embedding_config_error(clinic_config)
            if clinic_error:
                logger.warning(
                    "[RAG:config] invalid clinic embedding config provider=%s model=%s "
                    "reason=%s fallback_provider=%s fallback_model=%s",
                    clinic_config.provider,
                    clinic_config.model,
                    clinic_error,
                    env_config.provider,
                    env_config.model,
                )
                config = EmbeddingRuntimeConfig(
                    provider=env_config.provider,
                    model=env_config.model,
                    schema_dimension=env_config.schema_dimension,
                    source="env_fallback",
                )
            else:
                config = clinic_config

        logger.info(
            "[RAG:config] source=%s provider=%s model=%s schema_dimension=%d",
            config.source,
            config.provider,
            config.model,
            config.schema_dimension,
        )
        return config

    def _extract_entity_signatures(self, text: str) -> list[str]:
        """Extract lightweight entity mentions from chunk text for GraphRAG traversal.

        Uses simple regex-based extraction (names starting with capital,
        CRM numbers, specialty names). Returns list of normalized signatures.
        No NER model required — works with any embedding provider.
        """
        import re

        # Capitalized words likely to be names, specialties, procedures
        # Use string pattern to handle UTF-8 Brazilian Portuguese chars
        capitalized = re.findall(
            r'(?<![a-zA-Z0-9\-])([A-Z][a-zA-Zà-ÿÀ-Ü]+(?:\s+[A-Z][a-zA-Zà-ÿÀ-Ü]+)*)',
            text,
        )
        signatures = []
        for word in capitalized:
            if len(word) < 3:
                continue
            if word.lower() in {
                'vc', 'você', 'o', 'a', 'os', 'as', 'um', 'uma', 'e', 'é', 'foi', 'ser', 'seu',
                'sua', 'na', 'no', 'não', 'para', 'com', 'por', 'mais', 'que',
            }:
                continue
            signatures.append(word.strip())

        # CRM pattern (e.g. "CRM/SP 123456")
        crms = re.findall(r'CRM[/\s]\w{2}\s*\d+', text)
        for m in crms:
            signatures.append(m)

        # Unique, limited to top 20 to avoid bloating entity_signatures JSON
        seen = set()
        unique = []
        for s in signatures:
            if s not in seen and len(unique) < 20:
                seen.add(s)
                unique.append(s)
        return unique

    def _embedding_config_error(self, config: EmbeddingRuntimeConfig) -> str | None:
        if config.provider in {"local", "openai", "gemini"}:
            expected_dim = default_embedding_dimension(config.provider)
            if config.schema_dimension != expected_dim:
                return (
                    f"embedding_dimension_mismatch provider={config.provider} "
                    f"expected_dim={expected_dim} schema_dim={config.schema_dimension}"
                )

        if config.provider == "openai" and not settings.openai_api_key:
            return "openai_api_key_missing"

        if config.provider == "gemini" and not settings.gemini_api_key:
            return "gemini_api_key_missing"

        if config.provider == "auto":
            if config.schema_dimension == default_embedding_dimension("openai") and not settings.openai_api_key:
                return "openai_api_key_missing"
            if config.schema_dimension == default_embedding_dimension("gemini") and not settings.gemini_api_key:
                return "gemini_api_key_missing"
            if config.schema_dimension not in {
                default_embedding_dimension("local"),
                default_embedding_dimension("openai"),
                default_embedding_dimension("gemini"),
            }:
                return f"unsupported_schema_dimension={config.schema_dimension}"

        return None

    async def ingest_document(
        self,
        title: str,
        content: str,
        clinic_id: str | None = None,
        category: str = "general",
        source_path: str | None = None,
        *,
        skip_embeddings: bool = False,
    ) -> RagIngestResponse:
        """
        Ingest a document with the full pipeline:
        parse -> chunk -> generate embedding -> persist -> mark embedded=true/false.
        """
        clinic_id = clinic_id or settings.clinic_id
        doc = await self.repo.create_document(title, category, clinic_id, source_path)
        chunks = chunk_text(
            content,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )

        embedded_count = 0
        failed_count = 0
        embedding_config = await self._resolve_embedding_config()
        config_error = "embedding_skipped_on_ingest" if skip_embeddings else self._embedding_config_error(embedding_config)

        for idx, chunk_content in enumerate(chunks):
            embedding: list[float] | None = None
            chunk_status = "failed"
            error: str | None = None

            try:
                if skip_embeddings:
                    chunk_status = "skipped"
                    error = config_error
                elif config_error:
                    failed_count += 1
                    error = config_error
                else:
                    embedding = await get_embedding(
                        chunk_content,
                        phase="ingest",
                        embedding_config=embedding_config,
                    )
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
                clinic_id=clinic_id,
                embedding=embedding,
                embedded=embedding is not None,
                embedding_error=error,
                metadata_json=json.dumps({"source": source_path or title, "chunk": idx}),
                parent_chunk_id=None,  # sibling linking done after loop
                entity_signatures=self._extract_entity_signatures(chunk_content),
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
            "chunks_failed=%d embedding_provider=%s embedding_model=%s config_source=%s skip_embeddings=%s",
            doc.id,
            title,
            len(chunks),
            embedded_count,
            failed_count,
            embedding_config.provider,
            embedding_config.model,
            embedding_config.source,
            str(skip_embeddings).lower(),
        )

        # Sibling linking: link each chunk (except first) to its previous chunk
        # Done after all inserts so every chunk has its ID and parent_chunk_id can be set
        chunks_with_ids = await self.repo.get_chunks(doc.id, clinic_id)
        if len(chunks_with_ids) > 1:
            for prev, curr in zip(chunks_with_ids, chunks_with_ids[1:]):
                prev.parent_chunk_id = prev.id
                curr.parent_chunk_id = prev.id
                self.repo.session.add(prev)
                self.repo.session.add(curr)
            await self.repo.session.commit()
            logger.info(
                "[RAG:ingest] document_id=%s sibling_links=%d",
                doc.id,
                len(chunks_with_ids) - 1,
            )

        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.ingested",
            resource_type="rag_document",
            resource_id=str(doc.id),
            payload={
                "clinic_id": clinic_id,
                "title": title,
                "chunks_total": len(chunks),
                "chunks_embedded": embedded_count,
                "chunks_failed": failed_count,
                "embedding_provider": embedding_config.provider,
                "embedding_model": embedding_config.model,
                "embedding_config_source": embedding_config.source,
                "config_error": config_error,
                "skip_embeddings": skip_embeddings,
            },
        )

        return RagIngestResponse(
            document_id=doc.id,
            chunks_created=len(chunks),
            chunks_embedded=embedded_count,
            chunks_failed=failed_count,
            embedding_provider=embedding_config.provider,
            embedding_model=embedding_config.model,
        )

    async def query(
        self,
        query_text: str,
        clinic_id: str | None = None,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[RagQueryResult]:
        execution = await self.query_with_metadata(query_text, clinic_id=clinic_id, top_k=top_k, category=category)
        return execution.results

    async def query_with_metadata(
        self,
        query_text: str,
        clinic_id: str | None = None,
        top_k: int | None = None,
        category: str | None = None,
    ) -> RagQueryExecution:
        """
        Query the RAG index with two-stage retrieval and optional cross-encoder reranking.

        Pipeline:
          1. Vector search (pgvector) → top_k_initial candidates
          2. Lexical rerank (fast, always applied to vector results)
          3. Cross-encoder rerank (if RAG_RERANKER_ENABLED=true)
          4. Slice to top_k_final → send to LLM
          5. Fall back to text search if embeddings unavailable

        Config:
          RAG_RERANKER_ENABLED      — enable/disable cross-encoder (default: false)
          RAG_RERANKER_TOP_K_INITIAL — candidates from pgvector (default: 20)
          RAG_RERANKER_TOP_K_FINAL   — chunks to LLM (default: 5)
          RAG_TOP_K                  — used when reranker is disabled (default: 5)
        """
        clinic_id = clinic_id or settings.clinic_id

        # When reranker is active, retrieve more candidates for reranking.
        reranker_active = settings.rag_reranker_enabled and self._reranker.model_name != "noop"
        if reranker_active:
            k_initial = settings.rag_reranker_top_k_initial
            k_final = top_k or settings.rag_reranker_top_k_final
        else:
            k_initial = top_k or settings.rag_top_k
            k_final = k_initial

        t0 = time.monotonic()
        embedded_chunks_available = await self.repo.has_embeddings(clinic_id, category)
        query_embedding_generated = False
        embedding_config = await self._resolve_embedding_config()
        config_error = self._embedding_config_error(embedding_config)

        if embedded_chunks_available:
            query_embedding = None
            if config_error:
                logger.warning(
                    "[RAG:query] retrieval_mode=text rag_used=false reason=%s provider=%s model=%s",
                    config_error,
                    embedding_config.provider,
                    embedding_config.model,
                )
            else:
                query_embedding = await get_embedding(
                    query_text,
                    phase="query",
                    embedding_config=embedding_config,
                )
                query_embedding_generated = query_embedding is not None

            if query_embedding is not None:
                try:
                    # Stage 1: vector retrieval (larger pool when reranker active)
                    rows = await self.repo.search_similar(
                        query_embedding, clinic_id, top_k=k_initial, category=category
                    )

                    # Stage 2: lexical boost (fast, always applied)
                    rows = _rerank_vector_rows(query_text, rows)

                    latency_vector = time.monotonic() - t0

                    if not rows:
                        logger.info(
                            "[RAG:query] retrieval_mode=vector top_k=%d results=0 "
                            "rag_used=false latency=%.3fs fallback=text",
                            k_initial, latency_vector,
                        )
                    else:
                        rerank_result = None
                        reranker_used = False

                        # Stage 3: cross-encoder reranking (if enabled)
                        if reranker_active:
                            rerank_result = await self._reranker.rerank(
                                query_text, rows, top_k=k_final
                            )
                            reranker_used = True

                            # Log initial vs. final ranking
                            logger.info(
                                "[RAG:query] reranker=true model='%s' "
                                "top_k_initial=%d top_k_final=%d "
                                "ranking_changed=%s reranker_latency_ms=%.1f "
                                "fallback=%s",
                                rerank_result.model_used,
                                rerank_result.top_k_initial,
                                rerank_result.top_k_final,
                                str(rerank_result.ranking_changed).lower(),
                                rerank_result.latency_ms,
                                str(rerank_result.fallback_used).lower(),
                            )
                            for c in rerank_result.candidates[:5]:
                                logger.info(
                                    "[RAG:query] reranked rank=%d chunk_id=%s "
                                    "vector_score=%.4f reranker_score=%.4f title='%s'",
                                    c.final_rank, c.chunk_id,
                                    c.vector_score, c.reranker_score,
                                    c.title[:60],
                                )

                            # Convert RerankCandidate → row dicts for _rows_to_results
                            final_rows = [
                                {
                                    "chunk_id": c.chunk_id,
                                    "document_id": c.document_id,
                                    "document_title": c.title,
                                    "content": c.content,
                                    "category": c.category,
                                    "score": c.reranker_score,
                                }
                                for c in rerank_result.candidates
                            ]
                        else:
                            # No reranker — slice to k_final from lexical-boosted order
                            final_rows = rows[:k_final]

                        total_latency = time.monotonic() - t0
                        logger.info(
                            "[RAG:query] retrieval_mode=vector top_k_initial=%d "
                            "top_k_final=%d results=%d reranker=%s rag_used=true "
                            "total_latency=%.3fs",
                            k_initial, k_final, len(final_rows),
                            str(reranker_used).lower(), total_latency,
                        )

                        execution = RagQueryExecution(
                            results=_rows_to_results(final_rows),
                            retrieval_mode="vector",
                            rag_used=True,
                            embedded_chunks_available=True,
                            query_embedding_generated=True,
                            reranker_used=reranker_used,
                        )
                        if rerank_result:
                            execution.reranker_model = rerank_result.model_used
                            execution.reranker_top_k_initial = rerank_result.top_k_initial
                            execution.reranker_top_k_final = rerank_result.top_k_final
                            execution.reranker_latency_ms = rerank_result.latency_ms
                            execution.reranker_fallback = rerank_result.fallback_used
                            execution.reranker_ranking_changed = rerank_result.ranking_changed
                        return execution

                except Exception as exc:
                    await self.repo.session.rollback()
                    logger.exception(
                        "[RAG:query] retrieval_mode=vector failed, falling back to text: %s",
                        exc,
                    )
            else:
                logger.warning(
                    "[RAG:query] retrieval_mode=text rag_used=false "
                    "reason=query_embedding_unavailable",
                )
        else:
            logger.info(
                "[RAG:query] retrieval_mode=text rag_used=false reason=no_embedded_chunks",
            )

        # Fallback: text search
        rows = await self.repo.text_search(query_text, clinic_id, top_k=k_final, category=category)
        latency = time.monotonic() - t0
        logger.info(
            "[RAG:query] retrieval_mode=text top_k=%d results=%d rag_used=%s latency=%.3fs",
            k_final, len(rows), str(bool(rows)).lower(), latency,
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
        clinic_id: str | None = None,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[dict]:
        """Text-based search fallback."""
        clinic_id = clinic_id or settings.clinic_id
        k = top_k or settings.rag_top_k
        return await self.repo.text_search(query_text, clinic_id, top_k=k, category=category)

    async def reindex_document(
        self,
        clinic_id: str | None = None,
        doc_id: uuid.UUID | None = None,
        *,
        force: bool = False,
    ) -> dict:
        """
        Reprocess chunk embeddings.

        force=False reindexes only missing/failed chunks.
        force=True regenerates embeddings for all chunks in scope.
        """
        clinic_id = clinic_id or settings.clinic_id
        chunks = await self.repo.get_chunks_for_reindex(clinic_id, doc_id, force=force)
        processed = 0
        embedded_count = 0
        failed_count = 0
        documents_processed = len({chunk.document_id for chunk in chunks})
        embedding_config = await self._resolve_embedding_config()
        config_error = self._embedding_config_error(embedding_config)

        logger.info(
            "[RAG:reindex] doc_scope=%s force=%s documents=%d chunks=%d provider=%s model=%s source=%s",
            str(doc_id) if doc_id else "all",
            str(force).lower(),
            documents_processed,
            len(chunks),
            embedding_config.provider,
            embedding_config.model,
            embedding_config.source,
        )

        for chunk in chunks:
            processed += 1
            try:
                if config_error:
                    failed_count += 1
                    await self.repo.update_chunk_indexing(
                        chunk.id,
                        embedding=None,
                        embedded=False,
                        embedding_error=config_error,
                    )
                    _log_chunk_status(
                        operation="reindex",
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        chunk_status="failed",
                        embedding_generated=False,
                        error=config_error,
                    )
                    continue

                embedding = await get_embedding(
                    chunk.content,
                    phase="reindex",
                    embedding_config=embedding_config,
                )
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

        stats = await self.repo.get_embedding_stats(clinic_id)
        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.reindexed",
            resource_type="rag_document",
            resource_id=str(doc_id) if doc_id else "all",
            payload={
                "clinic_id": clinic_id,
                "documents_processed": documents_processed,
                "chunks_processed": processed,
                "chunks_embedded": embedded_count,
                "chunks_failed": failed_count,
                "force": force,
                "embedding_provider": embedding_config.provider,
                "embedding_model": embedding_config.model,
                "embedding_config_source": embedding_config.source,
                "config_error": config_error,
                "chunks_without_embedding": stats["chunks_without_embedding"],
                "coverage_pct": stats["coverage_pct"],
            },
        )

        logger.info(
            "[RAG:reindex] completed documents=%d processed=%d embedded=%d failed=%d "
            "chunks_without_embedding=%d coverage_pct=%.1f provider=%s model=%s",
            documents_processed,
            processed,
            embedded_count,
            failed_count,
            stats["chunks_without_embedding"],
            stats["coverage_pct"],
            embedding_config.provider,
            embedding_config.model,
        )
        return {
            "documents_processed": documents_processed,
            "processed": processed,
            "embedded": embedded_count,
            "failed": failed_count,
            "embedding_provider": embedding_config.provider,
            "embedding_model": embedding_config.model,
            "embedding_config_source": embedding_config.source,
            "config_error": config_error,
            "chunks_without_embedding": stats["chunks_without_embedding"],
            "coverage_pct": stats["coverage_pct"],
        }

    async def get_stats(self, clinic_id: str | None = None) -> dict:
        clinic_id = clinic_id or settings.clinic_id
        stats = await self.repo.get_embedding_stats(clinic_id)
        embedding_config = await self._resolve_embedding_config()
        stats.update(
            {
                "embedding_provider": embedding_config.provider,
                "embedding_model": embedding_config.model,
                "embedding_config_source": embedding_config.source,
                "config_error": self._embedding_config_error(embedding_config),
            }
        )
        return stats

    async def list_documents(self, clinic_id: str | None = None, category: str | None = None) -> list[RagDocument]:
        clinic_id = clinic_id or settings.clinic_id
        return await self.repo.list_documents(clinic_id, category)

    async def get_document(self, doc_id: uuid.UUID, clinic_id: str | None = None) -> RagDocument | None:
        clinic_id = clinic_id or settings.clinic_id
        return await self.repo.get_document(doc_id, clinic_id)

    async def get_chunks(self, doc_id: uuid.UUID, clinic_id: str | None = None):
        clinic_id = clinic_id or settings.clinic_id
        return await self.repo.get_chunks(doc_id, clinic_id)

    async def delete_document(self, doc_id: uuid.UUID, clinic_id: str | None = None) -> bool:
        clinic_id = clinic_id or settings.clinic_id
        deleted = await self.repo.delete_document(doc_id, clinic_id)
        if deleted:
            await self.audit.log_event(
                actor_type="human",
                actor_id="operator",
                action="document.deleted",
                resource_type="rag_document",
                resource_id=str(doc_id),
                payload={"clinic_id": clinic_id},
            )
        return deleted
