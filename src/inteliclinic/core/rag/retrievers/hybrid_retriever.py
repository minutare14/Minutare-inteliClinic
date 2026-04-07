"""Hybrid retriever — combines dense (vector) and sparse (BM25) retrieval.

Reciprocal Rank Fusion (RRF) is used to merge results from both retrievers.
This improves recall for exact-match queries (e.g. TISS codes, procedure names)
while preserving semantic retrieval for natural language questions.

Future: Add cross-encoder reranking after fusion.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from .query_engine import RAGResult  # type: ignore[relative-beyond-top-level]

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard RRF constant


@dataclass
class HybridResult:
    """Merged result with RRF score."""

    result: RAGResult
    rrf_score: float


class HybridRetriever:
    """Combines dense vector search and BM25 keyword search via RRF.

    Configuration:
        dense_weight:  Relative weight for vector similarity scores (0-1).
        sparse_weight: Relative weight for BM25 scores (0-1).
        top_k:         Number of final results to return after fusion.
    """

    def __init__(
        self,
        store: "LlamaIndexStore",  # noqa: F821
        top_k: int = 5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        min_score: float = 0.0,
    ):
        self.store = store
        self.top_k = top_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.min_score = min_score

    async def retrieve(self, query: str, top_k: int | None = None) -> list[RAGResult]:
        """Retrieve documents using hybrid dense + sparse strategy."""
        k = top_k or self.top_k

        dense_task = self._dense_retrieve(query, k * 2)
        sparse_task = self._sparse_retrieve(query, k * 2)

        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

        fused = self._rrf_fusion(dense_results, sparse_results, k)
        return fused

    # ------------------------------------------------------------------
    # Internal retrieval methods
    # ------------------------------------------------------------------

    async def _dense_retrieve(self, query: str, top_k: int) -> list[RAGResult]:
        """Vector similarity retrieval via LlamaIndex / Qdrant."""
        from .query_engine import ClinicQueryEngine

        engine = ClinicQueryEngine(store=self.store, top_k=top_k, min_score=self.min_score)
        return await engine.query(query, top_k=top_k)

    async def _sparse_retrieve(self, query: str, top_k: int) -> list[RAGResult]:
        """Keyword-based retrieval (BM25 approximation using term matching).

        Note: Full BM25 requires a sparse index (e.g. Qdrant sparse vectors or
        a separate BM25 index). This implementation is a basic keyword overlap
        fallback. Replace with proper BM25 in production.
        """
        # Placeholder: return empty for now — dense retrieval is primary
        # In production: integrate llama_index BM25Retriever or Qdrant sparse vectors
        return []

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion
    # ------------------------------------------------------------------

    def _rrf_fusion(
        self,
        dense: list[RAGResult],
        sparse: list[RAGResult],
        top_k: int,
    ) -> list[RAGResult]:
        """Merge dense and sparse results using Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        result_map: dict[str, RAGResult] = {}

        for rank, result in enumerate(dense):
            key = result.content[:100]  # Use content prefix as dedup key
            scores[key] = scores.get(key, 0.0) + self.dense_weight / (RRF_K + rank + 1)
            result_map[key] = result

        for rank, result in enumerate(sparse):
            key = result.content[:100]
            scores[key] = scores.get(key, 0.0) + self.sparse_weight / (RRF_K + rank + 1)
            if key not in result_map:
                result_map[key] = result

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [result_map[k] for k, _ in ranked[:top_k]]
