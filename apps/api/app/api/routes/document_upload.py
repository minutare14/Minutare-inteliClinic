from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentSummary,
    DocumentDetail,
    DocumentListResponse,
    ExtractionItem,
    ChunkInfo,
    DocumentUploadRequest,
)

router = APIRouter(prefix="/admin/documents", tags=["admin/documents"])
_READ_ROLES = (UserRole.admin, UserRole.manager)
_WRITE_ROLES = (UserRole.admin,)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    category: str = Form(...),
    title: str | None = Form(None),
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentUploadResponse:
    """Upload and process a PDF or Markdown document."""
    # Validate file type
    if file.content_type not in ("application/pdf", "text/markdown", "text/x-markdown"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or Markdown.")
    # Validate file size (10MB max)
    await file.seek(0)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10MB.")
    await file.seek(0)

    # TODO: wire to document_upload_service
    # For now return stub
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentListResponse:
    """List all documents with status and counts."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentDetail:
    """Get document detail with chunks and extractions."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> None:
    """Soft delete document, remove from Pinecone, orphan extractions."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")