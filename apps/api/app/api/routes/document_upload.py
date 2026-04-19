from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.config import settings
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentSummary,
    DocumentDetail,
    DocumentListResponse,
    ChunkInfo,
)
from app.services import document_upload as doc_service

router = APIRouter(prefix="/admin/documents", tags=["admin/documents"])
_READ_ROLES = (UserRole.admin, UserRole.manager)
_WRITE_ROLES = (UserRole.admin,)


def _build_summary(doc) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        title=doc.title,
        category=doc.category,
        status=doc.status,
        chunks_count=0,
        extractions_count=0,
        approved_count=0,
        rejected_count=0,
        created_at=doc.created_at,
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    category: str = Form(...),
    title: str | None = Form(None),
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentUploadResponse:
    """Upload and process a PDF or Markdown document."""
    await file.seek(0)
    content = await file.read()
    await file.seek(0)

    try:
        result = await doc_service.process_document(
            session=session,
            file_content=content,
            filename=file.filename or "untitled",
            content_type=file.content_type or "application/octet-stream",
            title=title,
            category=category,
            clinic_id=settings.clinic_id,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentListResponse:
    """List all documents with status and counts."""
    try:
        result = await doc_service.list_documents(
            session=session,
            clinic_id=settings.clinic_id,
            category=category,
            status=status,
            page=page,
            limit=limit,
        )
        docs = result["items"]
        return DocumentListResponse(
            items=[_build_summary(d) for d in docs],
            total=result["total"],
            page=page,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"List failed: {exc}")


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentDetail:
    """Get document detail with chunks and extractions."""
    try:
        result = await doc_service.get_document_detail(
            session=session,
            document_id=document_id,
            clinic_id=settings.clinic_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentDetail(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Get document failed: {exc}")


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> None:
    """Soft delete document, remove from Pinecone, orphan extractions."""
    try:
        deleted = await doc_service.delete_document(
            session=session,
            document_id=document_id,
            clinic_id=settings.clinic_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")