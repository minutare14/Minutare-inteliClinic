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
from app.services import extraction_approval

router = APIRouter(prefix="/admin/documents/extractions", tags=["admin/documents/extractions"])
_ROLES = (UserRole.admin, UserRole.manager)


def _ext_to_item(ext) -> ExtractionItem:
    return ExtractionItem(
        id=ext.id,
        entity_type=ext.entity_type,
        extracted_data=ext.extracted_data or {},
        raw_text=ext.raw_text,
        extraction_method=ext.extraction_method,
        confidence=ext.confidence,
        requires_review=ext.requires_review,
        status=ext.status,
        reviewed_by=ext.reviewed_by,
        reviewed_at=ext.reviewed_at,
        published_at=ext.published_at,
        published_to=ext.published_to,
        published_entity_id=ext.published_entity_id,
        superseded_by=ext.superseded_by,
        source_extraction_id=ext.source_extraction_id,
        created_at=ext.created_at,
    )


@router.patch("/{extraction_id}/approve", response_model=ExtractionItem)
async def approve_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionApproveRequest | None = None,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Approve a pending extraction, publish to target table."""
    try:
        ext = await extraction_approval.approve_extraction(
            session=session,
            extraction_id=extraction_id,
            user_id=str(current_user.id) if current_user else "system",
            notes=body.notes if body else None,
        )
        return _ext_to_item(ext)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Approve failed: {exc}")


@router.patch("/{extraction_id}/reject", response_model=ExtractionItem)
async def reject_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionRejectRequest,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Reject an extraction with reason."""
    try:
        ext = await extraction_approval.reject_extraction(
            session=session,
            extraction_id=extraction_id,
            user_id=str(current_user.id) if current_user else "system",
            reason=body.reason,
        )
        return _ext_to_item(ext)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reject failed: {exc}")


@router.patch("/{extraction_id}/revise", response_model=ExtractionItem)
async def revise_extraction(
    extraction_id: uuid.UUID,
    body: ExtractionReviseRequest,
    current_user: Annotated[User, Depends(require_roles(*_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Revise an extraction with corrected data, creates new pending extraction."""
    try:
        new_ext = await extraction_approval.revise_extraction(
            session=session,
            extraction_id=extraction_id,
            user_id=str(current_user.id) if current_user else "system",
            corrected_data=body.corrected_data,
        )
        return _ext_to_item(new_ext)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revise failed: {exc}")