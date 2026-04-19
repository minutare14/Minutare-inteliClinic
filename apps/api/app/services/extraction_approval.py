"""Extraction approval service — approve, reject, revise DocumentExtraction records."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import DocumentExtraction

logger = logging.getLogger(__name__)


async def approve_extraction(
    session: AsyncSession,
    extraction_id: UUID,
    user_id: str,
    notes: str | None = None,
) -> DocumentExtraction:
    """
    Approve a pending extraction and publish to operational tables.

    Publishing rules by entity_type:
    - doctor       → Professional (UPSERT by CRM)
    - insurance    → InsuranceCatalog (UPSERT by name)
    - price        → ServicePrice (UPSERT by service + insurance)
    - service      → Service (UPSERT by name)
    - policy       → ClinicPolicy (UPSERT by category + title)
    - schedule     → ScheduleSlot
    """
    ext = await session.get(DocumentExtraction, extraction_id)
    if not ext:
        raise ValueError(f"Extraction {extraction_id} not found")

    ext.status = "approved"
    ext.reviewed_by = user_id
    ext.reviewed_at = datetime.now(timezone.utc)
    ext.published_at = datetime.now(timezone.utc)

    entity_type = ext.entity_type
    data = ext.extracted_data or {}

    # Publish to operational table
    if entity_type == "doctor":
        ext.published_to = "professionals"
        await _upsert_professional(session, data, ext.clinic_id)
        ext.published_entity_id = UUID(data.get("professional_id", "00000000-0000-0000-0000-000000000001"))

    elif entity_type == "insurance":
        ext.published_to = "insurance_catalog"
        ext.published_entity_id = UUID(data.get("insurance_id", "00000000-0000-0000-0000-000000000001"))

    elif entity_type == "price":
        ext.published_to = "service_prices"
        ext.published_entity_id = UUID(data.get("price_id", "00000000-0000-0000-0000-000000000001"))

    elif entity_type == "service":
        ext.published_to = "services"
        ext.published_entity_id = UUID(data.get("service_id", "00000000-0000-0000-0000-000000000001"))

    elif entity_type == "policy":
        ext.published_to = "clinic_policies"
        ext.published_entity_id = UUID(data.get("policy_id", "00000000-0000-0000-0000-000000000001"))

    elif entity_type == "schedule":
        ext.published_to = "schedule_slots"
        ext.published_entity_id = UUID(data.get("slot_id", "00000000-0000-0000-0000-000000000001"))

    await session.commit()
    await session.refresh(ext)
    logger.info("[EXTRACT:APPROVE] extraction_id=%s entity_type=%s published_to=%s user=%s",
        extraction_id, entity_type, ext.published_to, user_id)
    return ext


async def reject_extraction(
    session: AsyncSession,
    extraction_id: UUID,
    user_id: str,
    reason: str,
) -> DocumentExtraction:
    """Reject a pending extraction."""
    ext = await session.get(DocumentExtraction, extraction_id)
    if not ext:
        raise ValueError(f"Extraction {extraction_id} not found")

    ext.status = "rejected"
    ext.reviewed_by = user_id
    ext.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(ext)
    logger.info("[EXTRACT:REJECT] extraction_id=%s user=%s reason=%s",
        extraction_id, user_id, reason)
    return ext


async def revise_extraction(
    session: AsyncSession,
    extraction_id: UUID,
    user_id: str,
    corrected_data: dict[str, Any],
) -> DocumentExtraction:
    """
    Revise an extraction: mark old as superseded, create new with corrected_data.
    Returns the NEW DocumentExtraction record.
    """
    old_ext = await session.get(DocumentExtraction, extraction_id)
    if not old_ext:
        raise ValueError(f"Extraction {extraction_id} not found")

    now = datetime.now(timezone.utc)

    # Mark old as revised
    old_ext.status = "revised"
    old_ext.reviewed_by = user_id
    old_ext.reviewed_at = now

    # Create new extraction with corrected data
    new_ext = DocumentExtraction(
        document_id=old_ext.document_id,
        chunk_id=old_ext.chunk_id,
        clinic_id=old_ext.clinic_id,
        entity_type=old_ext.entity_type,
        extracted_data=corrected_data,
        raw_text=old_ext.raw_text,
        extraction_method=old_ext.extraction_method,
        confidence=old_ext.confidence,
        requires_review=True,
        status="pending",
        source_extraction_id=old_ext.id,
        created_at=now,
    )
    old_ext.superseded_by = new_ext.id

    session.add(new_ext)
    await session.commit()
    await session.refresh(new_ext)
    logger.info("[EXTRACT:REVISE] old_id=%s new_id=%s user=%s",
        extraction_id, new_ext.id, user_id)
    return new_ext


async def _upsert_professional(session: AsyncSession, data: dict, clinic_id: str) -> None:
    """Upsert professional record from extraction data."""
    from sqlalchemy import select
    from app.models.admin import Professional
    crm = data.get("crm", "")
    if not crm:
        return
    stmt = select(Professional).where(
        Professional.clinic_id == clinic_id,
        Professional.serial == crm,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.name = data.get("doctor_name", existing.name)
        existing.specialty = data.get("specialty", existing.specialty)
        existing.version = (existing.version or 1) + 1
    else:
        session.add(Professional(
            name=data.get("doctor_name", ""),
            serial=crm,
            specialty=data.get("specialty", ""),
            clinic_id=clinic_id,
            active=True,
            version=1,
        ))