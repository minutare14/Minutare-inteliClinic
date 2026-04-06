from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rag import RagDocument
from app.repositories.rag_repository import RagRepository
from app.schemas.rag import RagIngestResponse, RagQueryResult
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


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


async def get_embedding(text: str) -> list[float] | None:
    """
    Get embedding vector for text.
    Supports: OpenAI, Gemini (free tier), or None (text-search fallback).
    """
    import httpx

    # OpenAI embeddings
    if settings.openai_api_key:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={"input": text, "model": "text-embedding-3-small"},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
        except Exception:
            logger.exception("OpenAI embedding failed")

    # Gemini embeddings (free tier available)
    if settings.gemini_api_key:
        try:
            model = "text-embedding-004"
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
                f":embedContent?key={settings.gemini_api_key}"
            )
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
            logger.exception("Gemini embedding failed")

    # No provider — text search fallback will be used
    logger.warning("No embedding provider configured — storing chunk without embedding")
    return None


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
        doc = await self.repo.create_document(title, category, source_path)

        chunks = chunk_text(
            content,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )

        for idx, chunk_text_content in enumerate(chunks):
            embedding = await get_embedding(chunk_text_content)
            await self.repo.create_chunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_text_content,
                embedding=embedding,
                metadata_json=json.dumps({"source": source_path or title}),
            )

        await self.audit.log_event(
            actor_type="system",
            actor_id="rag_service",
            action="document.ingested",
            resource_type="rag_document",
            resource_id=str(doc.id),
            payload={"title": title, "chunks": len(chunks)},
        )

        logger.info("Ingested document '%s' with %d chunks", title, len(chunks))
        return RagIngestResponse(document_id=doc.id, chunks_created=len(chunks))

    async def query(
        self,
        query_text: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[RagQueryResult]:
        embedding = await get_embedding(query_text)
        if not embedding:
            logger.warning("Cannot query RAG without embeddings")
            return []

        k = top_k or settings.rag_top_k
        rows = await self.repo.search_similar(embedding, top_k=k, category=category)

        return [
            RagQueryResult(
                chunk_id=r["chunk_id"],
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
        """
        Text-based search fallback when embeddings are not available.
        Uses ILIKE on chunk content.
        """
        k = top_k or settings.rag_top_k
        rows = await self.repo.text_search(query_text, top_k=k, category=category)
        return rows

    async def list_documents(self, category: str | None = None) -> list[RagDocument]:
        return await self.repo.list_documents(category)
