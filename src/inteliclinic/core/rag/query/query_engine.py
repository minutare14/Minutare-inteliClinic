"""RAG query engine — LlamaIndex with clinic-specific filters.

Supports:
- Semantic search (vector similarity via Qdrant)
- Metadata filters (doc_type, source, date range)
- Specialized queries for insurance, protocols, and FAQ
- Future: cross-encoder reranking

Usage:
    engine = ClinicQueryEngine(store=llamaindex_store, top_k=5)
    results = await engine.query("Qual a cobertura para ressonância magnética?")
    results = await engine.query_insurance("cobertura", insurance_name="Unimed")
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """A single retrieved document chunk with score and metadata."""

    content: str
    score: float
    source: str
    doc_type: str
    metadata: dict = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Format for inclusion in LLM prompt context."""
        return f"[{self.doc_type.upper()} | {self.source}]\n{self.content}"


class ClinicQueryEngine:
    """Main query engine for the clinic knowledge base.

    Wraps LlamaIndex's query pipeline with:
    - Async execution (runs sync LlamaIndex in thread pool)
    - Metadata filters for document type isolation
    - Confidence filtering (min_score threshold)
    - Domain-specific query helpers
    """

    def __init__(
        self,
        store: "LlamaIndexStore",
        top_k: int = 5,
        min_score: float = 0.70,
    ):
        self.store = store
        self.top_k = top_k
        self.min_score = min_score

    # ------------------------------------------------------------------
    # Generic query
    # ------------------------------------------------------------------

    async def query(
        self,
        question: str,
        doc_type_filter: str | None = None,
        top_k: int | None = None,
    ) -> list[RAGResult]:
        """Query the knowledge base for relevant passages.

        Args:
            question:        Natural language question.
            doc_type_filter: Restrict to a specific doc_type
                             (e.g. "insurance", "protocol", "faq").
            top_k:           Override default top_k for this query.
        """
        k = top_k or self.top_k

        def _sync_query():
            filters = None
            if doc_type_filter:
                from llama_index.core.vector_stores.types import (
                    MetadataFilter,
                    MetadataFilters,
                )

                filters = MetadataFilters(
                    filters=[MetadataFilter(key="doc_type", value=doc_type_filter)]
                )

            engine = self.store.as_query_engine(similarity_top_k=k, filters=filters)
            response = engine.query(question)
            return response

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _sync_query)
            return self._parse_response(response)
        except Exception as exc:
            logger.exception("RAG query failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    async def query_insurance(
        self,
        question: str,
        insurance_name: str | None = None,
    ) -> list[RAGResult]:
        """Query specifically for insurance/convenio coverage information."""
        enriched = question
        if insurance_name:
            enriched = f"Convênio {insurance_name}: {question}"
        return await self.query(enriched, doc_type_filter="insurance")

    async def query_protocols(
        self,
        specialty: str,
        procedure: str | None = None,
    ) -> list[RAGResult]:
        """Query medical protocols for a given specialty."""
        q = f"Protocolo clínico {specialty}"
        if procedure:
            q += f" — procedimento: {procedure}"
        return await self.query(q, doc_type_filter="protocol")

    async def query_faq(self, question: str) -> list[RAGResult]:
        """Query the clinic's FAQ knowledge base."""
        return await self.query(question, doc_type_filter="faq")

    async def query_tiss(self, procedure_code: str) -> list[RAGResult]:
        """Look up a TISS/TUSS procedure code in the knowledge base."""
        return await self.query(f"Código TUSS {procedure_code}", doc_type_filter="tiss")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(self, response) -> list[RAGResult]:
        """Convert LlamaIndex Response to list of RAGResult."""
        results: list[RAGResult] = []
        if not hasattr(response, "source_nodes"):
            return results

        for node in response.source_nodes:
            score = getattr(node, "score", 0.0) or 0.0
            if score < self.min_score:
                continue
            meta = node.node.metadata if hasattr(node.node, "metadata") else {}
            results.append(
                RAGResult(
                    content=node.node.get_content(),
                    score=score,
                    source=meta.get("source", meta.get("filename", "unknown")),
                    doc_type=meta.get("doc_type", "document"),
                    metadata=meta,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results
