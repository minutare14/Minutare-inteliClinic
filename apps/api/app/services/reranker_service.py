"""
RerankerService — Cross-encoder reranking stage for the RAG pipeline.

Two-stage retrieval architecture:
  Stage 1: pgvector cosine similarity → top_k_initial candidates (default 20)
  Stage 2: cross-encoder scoring → reorder + slice to top_k_final (default 5)
  Stage 3: LLM receives only the best-ranked chunks

The reranker operates ONLY on queries that reach the RAG path.
It is never called for:
  - structured_data_lookup (professionals, insurance, address, phone)
  - schedule_flow (AGENDAR, CANCELAR, REMARCAR)
  - guardrail blocks or handoff flows

References:
  - sentence-transformers CrossEncoder:
      https://sbert.net/docs/cross_encoder/pretrained_models.html
  - mMARCO multilingual cross-encoder (PT-BR compatible):
      https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  - Qdrant FastEmbed Rerankers (architecture reference):
      https://qdrant.github.io/fastembed/examples/Reranking/
  - Pinecone reranking docs (comparison reference, NOT used here):
      https://docs.pinecone.io/guides/inference/rerank
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Lazily loaded cross-encoder model (shared across requests) ─────────────────
_cross_encoder_model = None
_cross_encoder_model_name: str | None = None
_cross_encoder_lock: asyncio.Lock | None = None


@dataclass
class RerankCandidate:
    """A single candidate chunk before/after reranking."""
    chunk_id: str
    document_id: str
    title: str
    content: str
    category: str
    vector_score: float
    reranker_score: float = 0.0
    final_rank: int = 0


@dataclass
class RerankResult:
    """Full result of a reranking pass."""
    candidates: list[RerankCandidate]
    model_used: str
    top_k_initial: int
    top_k_final: int
    latency_ms: float
    fallback_used: bool = False
    fallback_reason: str | None = None
    ranking_changed: bool = False


# ── Abstract base ──────────────────────────────────────────────────────────────

class BaseReranker(ABC):
    """Abstract interface for reranker implementations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> RerankResult:
        """
        Score and reorder candidates for the given query.

        Args:
            query:      The user query string.
            candidates: List of chunk dicts (keys: chunk_id, document_id, title,
                        content, category, score).
            top_k:      How many candidates to return after reranking.

        Returns:
            RerankResult with reordered candidates sliced to top_k.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the reranker backend is configured and loadable."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""


# ── Cross-encoder implementation (sentence-transformers) ──────────────────────

class CrossEncoderReranker(BaseReranker):
    """
    Reranker using sentence-transformers CrossEncoder.

    Default model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
      - Multilingual (PT-BR supported), trained on mMARCO corpus
      - Fast inference (~50–80 ms for 20 candidates on CPU)
      - ~120 MB download on first use

    Model is loaded lazily on first call and shared across instances
    via a module-level singleton.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        try:
            from sentence_transformers import CrossEncoder  # noqa: F401
            return True
        except ImportError:
            return False

    async def _load_model(self):
        global _cross_encoder_model, _cross_encoder_model_name, _cross_encoder_lock

        if _cross_encoder_model is not None and _cross_encoder_model_name == self._model_name:
            return _cross_encoder_model

        if _cross_encoder_lock is None:
            _cross_encoder_lock = asyncio.Lock()

        async with _cross_encoder_lock:
            # Double-check after acquiring lock
            if _cross_encoder_model is not None and _cross_encoder_model_name == self._model_name:
                return _cross_encoder_model

            logger.info(
                "[RAG:reranker] loading model='%s' status=loading",
                self._model_name,
            )
            t0 = time.monotonic()
            loop = asyncio.get_running_loop()
            try:
                from sentence_transformers import CrossEncoder

                model = await loop.run_in_executor(
                    None,
                    lambda: CrossEncoder(self._model_name),
                )
                _cross_encoder_model = model
                _cross_encoder_model_name = self._model_name
                logger.info(
                    "[RAG:reranker] model='%s' status=ready load_ms=%.0f",
                    self._model_name,
                    (time.monotonic() - t0) * 1000,
                )
                return model
            except Exception as exc:
                logger.exception(
                    "[RAG:reranker] model='%s' status=load_failed error=%s",
                    self._model_name,
                    exc,
                )
                return None

    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> RerankResult:
        t0 = time.monotonic()
        top_k_initial = len(candidates)

        if not candidates:
            return RerankResult(
                candidates=[],
                model_used=self._model_name,
                top_k_initial=0,
                top_k_final=0,
                latency_ms=0.0,
                fallback_used=False,
            )

        model = await self._load_model()
        if model is None:
            return self._fallback(
                query, candidates, top_k, reason="model_load_failed"
            )

        try:
            loop = asyncio.get_running_loop()
            pairs = [(query, c.get("content", "")) for c in candidates]

            scores: list[float] = await loop.run_in_executor(
                None,
                lambda: model.predict(pairs, show_progress_bar=False).tolist(),
            )

            # Build RerankCandidates with cross-encoder scores
            reranked = []
            for i, (chunk, score) in enumerate(zip(candidates, scores)):
                reranked.append(
                    RerankCandidate(
                        chunk_id=str(chunk.get("chunk_id", "")),
                        document_id=str(chunk.get("document_id", "")),
                        title=chunk.get("document_title", chunk.get("title", "")),
                        content=chunk.get("content", ""),
                        category=chunk.get("category", ""),
                        vector_score=float(chunk.get("score", 0.0)),
                        reranker_score=float(score),
                        final_rank=0,
                    )
                )

            # Sort by reranker score descending
            reranked.sort(key=lambda c: c.reranker_score, reverse=True)
            top_candidates = reranked[:top_k]
            for i, c in enumerate(top_candidates):
                c.final_rank = i + 1

            latency_ms = (time.monotonic() - t0) * 1000

            # Detect if ranking changed vs. original vector order
            original_ids = [str(c.get("chunk_id", "")) for c in candidates[:top_k]]
            reranked_ids = [c.chunk_id for c in top_candidates]
            ranking_changed = original_ids != reranked_ids

            logger.info(
                "[RAG:reranker] model='%s' top_k_initial=%d top_k_final=%d "
                "ranking_changed=%s latency_ms=%.1f",
                self._model_name,
                top_k_initial,
                len(top_candidates),
                str(ranking_changed).lower(),
                latency_ms,
            )

            # Detailed score log (first 5 candidates)
            for c in top_candidates[:5]:
                logger.debug(
                    "[RAG:reranker] rank=%d chunk_id=%s vector_score=%.4f "
                    "reranker_score=%.4f title='%s'",
                    c.final_rank,
                    c.chunk_id,
                    c.vector_score,
                    c.reranker_score,
                    c.title[:60],
                )

            return RerankResult(
                candidates=top_candidates,
                model_used=self._model_name,
                top_k_initial=top_k_initial,
                top_k_final=len(top_candidates),
                latency_ms=latency_ms,
                fallback_used=False,
                ranking_changed=ranking_changed,
            )

        except Exception as exc:
            logger.exception(
                "[RAG:reranker] scoring failed model='%s' error=%s — fallback",
                self._model_name,
                exc,
            )
            return self._fallback(query, candidates, top_k, reason=str(exc))

    def _fallback(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
        reason: str,
    ) -> RerankResult:
        """Return original vector-ranked candidates, sliced to top_k."""
        logger.warning(
            "[RAG:reranker] fallback_used=true reason='%s' model='%s' "
            "returning vector-ordered top_%d",
            reason,
            self._model_name,
            top_k,
        )
        fallback_candidates = []
        for i, chunk in enumerate(candidates[:top_k]):
            fallback_candidates.append(
                RerankCandidate(
                    chunk_id=str(chunk.get("chunk_id", "")),
                    document_id=str(chunk.get("document_id", "")),
                    title=chunk.get("document_title", chunk.get("title", "")),
                    content=chunk.get("content", ""),
                    category=chunk.get("category", ""),
                    vector_score=float(chunk.get("score", 0.0)),
                    reranker_score=float(chunk.get("score", 0.0)),
                    final_rank=i + 1,
                )
            )
        return RerankResult(
            candidates=fallback_candidates,
            model_used=self._model_name,
            top_k_initial=len(candidates),
            top_k_final=len(fallback_candidates),
            latency_ms=0.0,
            fallback_used=True,
            fallback_reason=reason,
            ranking_changed=False,
        )


# ── No-op reranker (disabled state) ───────────────────────────────────────────

class NoOpReranker(BaseReranker):
    """
    Pass-through reranker used when RAG_RERANKER_ENABLED=false.
    Returns original vector-ordered candidates unchanged.
    """

    @property
    def model_name(self) -> str:
        return "noop"

    def is_available(self) -> bool:
        return True

    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> RerankResult:
        passthrough = []
        for i, chunk in enumerate(candidates[:top_k]):
            passthrough.append(
                RerankCandidate(
                    chunk_id=str(chunk.get("chunk_id", "")),
                    document_id=str(chunk.get("document_id", "")),
                    title=chunk.get("document_title", chunk.get("title", "")),
                    content=chunk.get("content", ""),
                    category=chunk.get("category", ""),
                    vector_score=float(chunk.get("score", 0.0)),
                    reranker_score=float(chunk.get("score", 0.0)),
                    final_rank=i + 1,
                )
            )
        return RerankResult(
            candidates=passthrough,
            model_used="noop",
            top_k_initial=len(candidates),
            top_k_final=len(passthrough),
            latency_ms=0.0,
            fallback_used=False,
            ranking_changed=False,
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def build_reranker(enabled: bool, model_name: str) -> BaseReranker:
    """
    Build the correct reranker based on config.

    Args:
        enabled:    RAG_RERANKER_ENABLED env var.
        model_name: RAG_RERANKER_MODEL env var.

    Returns:
        CrossEncoderReranker if enabled, else NoOpReranker.
    """
    if not enabled:
        logger.debug("[RAG:reranker] disabled — using NoOpReranker")
        return NoOpReranker()

    reranker = CrossEncoderReranker(model_name)
    if not reranker.is_available():
        logger.warning(
            "[RAG:reranker] sentence-transformers not installed — "
            "falling back to NoOpReranker despite enabled=true. "
            "Install: pip install sentence-transformers"
        )
        return NoOpReranker()

    logger.info(
        "[RAG:reranker] enabled=true model='%s'",
        model_name,
    )
    return reranker
