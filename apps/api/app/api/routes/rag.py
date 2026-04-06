from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.rag import (
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
