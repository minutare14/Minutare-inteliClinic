from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.rag import (
    RagChunkRead,
    RagDocumentRead,
    RagIngestRequest,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResult,
)
from app.services.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ingest", response_model=RagIngestResponse, status_code=201)
async def ingest_document(
    data: RagIngestRequest,
    session: AsyncSession = Depends(get_session),
) -> RagIngestResponse:
    svc = RagService(session)
    return await svc.ingest_document(
        title=data.title,
        content=data.content,
        category=data.category,
        source_path=data.source_path,
    )


@router.post("/query", response_model=list[RagQueryResult])
async def query_rag(
    data: RagQueryRequest,
    session: AsyncSession = Depends(get_session),
) -> list[RagQueryResult]:
    svc = RagService(session)
    return await svc.query(
        query_text=data.query,
        top_k=data.top_k,
        category=data.category,
    )


@router.get("/documents", response_model=list[RagDocumentRead])
async def list_documents(
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[RagDocumentRead]:
    svc = RagService(session)
    docs = await svc.list_documents(category)
    return [RagDocumentRead.model_validate(d) for d in docs]


@router.get("/documents/{doc_id}/chunks", response_model=list[RagChunkRead])
async def get_document_chunks(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[RagChunkRead]:
    svc = RagService(session)
    chunks = await svc.get_chunks(doc_id)
    return [
        RagChunkRead(
            id=c.id,
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            content=c.content,
            page=c.page,
            created_at=c.created_at,
            embedded=c.embedded,
            embedding_error=c.embedding_error,
            has_embedding=c.embedding is not None and c.embedded,
        )
        for c in chunks
    ]


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    svc = RagService(session)
    deleted = await svc.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/stats")
async def get_rag_stats(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Returns embedding coverage stats for the admin panel.

    Response:
      documents: total active documents
      chunks_total: total chunks
      chunks_with_embedding: chunks with embedding vector
      chunks_without_embedding: chunks missing embedding (need reindex)
      coverage_pct: percentage of chunks with embedding
      embedding_provider: effective provider used by runtime (clinic_settings -> env)
      embedding_model: effective model used by runtime
      embedding_config_source: "clinic_settings" or "env"
      config_error: explicit incompatibility or missing-key reason, if any
    """
    svc = RagService(session)
    return await svc.get_stats()


@router.post("/reindex")
async def reindex_documents(
    doc_id: uuid.UUID | None = None,
    force: bool = False,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Regenerate embeddings for chunks without embedding.

    - If doc_id is provided: reindexes only that document's chunks.
    - If doc_id is None: reindexes ALL documents (global backfill).

    Uses the effective embedding config resolved by runtime:
      clinic_settings.embedding_provider / embedding_model -> env fallback.
    Run this after:
      1. Configuring EMBEDDING_PROVIDER for the first time
      2. Changing EMBEDDING_PROVIDER
      3. After ingesting documents when no embedding provider was available

    Response:
      processed: chunks attempted
      embedded: chunks successfully embedded
      failed: chunks that failed (provider error or unavailable)
      embedding_provider: effective provider used
      embedding_model: effective model used
      config_error: explicit incompatibility or missing-key reason, if any
    """
    svc = RagService(session)
    result = await svc.reindex_document(doc_id, force=force)
    return result
