from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.schemas.document import (
    ExtractionItem,
    ExtractionApproveRequest,
    ExtractionRejectRequest,
    ExtractionReviseRequest,
)

router = APIRouter(prefix="/admin/documents/extractions", tags=["admin/documents/extractions"])
_ROLES = (UserRole.admin, UserRole.manager)


@router.patch("/{extraction_id}/approve", response_model=ExtractionItem)
async def approve_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionApproveRequest | None = None,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Approve a pending extraction, publish to target table."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.patch("/{extraction_id}/reject", response_model=ExtractionItem)
async def reject_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionRejectRequest,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Reject an extraction with reason."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.patch("/{extraction_id}/revise", response_model=ExtractionItem)
async def revise_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionReviseRequest,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Revise an extraction with corrected data, creates new pending extraction."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")
