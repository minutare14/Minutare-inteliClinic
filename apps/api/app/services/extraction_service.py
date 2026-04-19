from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import DocumentExtraction


# ── Patterns ──────────────────────────────────────────────────────────────────

CRM_PATTERN = re.compile(r"(?<![A-Z])CRM[/\s][A-Z]{2}\s*\d+", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"R\$\s*\d+(?:[.,]\d{2})?")
DAY_SLOT_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:seg(?:unda)?|ter(?:ceira)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?)[^,\n]{0,50}",
    re.IGNORECASE,
)


@dataclass
class ExtractionResult:
    entity_type: str
    extracted_data: dict
    raw_text: str
    extraction_method: str
    confidence: float
    requires_review: bool


def extract_crm(text: str) -> list[ExtractionResult]:
    """Extract doctor CRM entities from text."""
    results = []
    for match in CRM_PATTERN.finditer(text):
        raw = match.group(0)
        before = text[: match.start()].strip().split("\n")[-1].strip()
        parts = raw.split()
        crm_idx = next((i for i, p in enumerate(parts) if p.lower().startswith("crm")), -1)
        crm_value = parts[crm_idx] if crm_idx >= 0 else raw
        specialty = " ".join(parts[crm_idx + 1 :]) if crm_idx + 1 < len(parts) else ""
        doctor_name = before if before and len(before) < 100 else ""
        results.append(
            ExtractionResult(
                entity_type="doctor",
                extracted_data={"doctor_name": doctor_name, "crm": crm_value, "specialty": specialty},
                raw_text=raw,
                extraction_method="deterministic",
                confidence=1.0,
                requires_review=False,
            )
        )
    return results


def extract_currency(text: str) -> list[ExtractionResult]:
    """Extract price/currency entities from text."""
    results = []
    for match in CURRENCY_PATTERN.finditer(text):
        raw = match.group(0)
        before = text[: match.start()].strip().split("\n")[-1].strip()
        value_str = raw.replace("R$", "").replace(" ", "").strip()
        try:
            value = float(value_str.replace(",", "."))
        except ValueError:
            value = 0.0
        service_name = before if before and len(before) < 200 else ""
        results.append(
            ExtractionResult(
                entity_type="price",
                extracted_data={"service_name": service_name, "price": value, "currency": "BRL"},
                raw_text=raw,
                extraction_method="deterministic",
                confidence=1.0,
                requires_review=False,
            )
        )
    return results


def extract_insurance(text: str, known_plans: list[str]) -> list[ExtractionResult]:
    """Extract insurance plan entities using case-insensitive matching against known plans."""
    results = []
    text_lower = text.lower()
    for plan in known_plans:
        if plan.lower() in text_lower:
            idx = text_lower.index(plan.lower())
            raw = text[idx : idx + len(plan)]
            results.append(
                ExtractionResult(
                    entity_type="insurance",
                    extracted_data={"insurance_name": plan, "matched_text": raw},
                    raw_text=raw,
                    extraction_method="deterministic",
                    confidence=1.0,
                    requires_review=False,
                )
            )
    return results


def extract_schedule(text: str) -> list[ExtractionResult]:
    """Extract day/time slot patterns from text."""
    results = []
    for match in DAY_SLOT_PATTERN.finditer(text):
        raw = match.group(0)
        results.append(
            ExtractionResult(
                entity_type="schedule",
                extracted_data={"day_slot": raw.strip()},
                raw_text=raw,
                extraction_method="deterministic",
                confidence=1.0,
                requires_review=False,
            )
        )
    return results


def extract_entities(text: str, entity_type: str, known_insurance: list[str] | None = None) -> list[ExtractionResult]:
    """Extract entities of a specific type from text."""
    if entity_type == "doctor":
        return extract_crm(text)
    if entity_type == "price":
        return extract_currency(text)
    if entity_type == "insurance":
        return extract_insurance(text, known_insurance or [])
    if entity_type == "schedule":
        return extract_schedule(text)
    return []


async def save_extractions(
    session: AsyncSession,
    document_id: UUID,
    clinic_id: str,
    extractions: list[ExtractionResult],
    chunk_id: UUID | None = None,
) -> list[DocumentExtraction]:
    """Save extraction results to the database."""
    records = []
    now = datetime.now(timezone.utc)
    for ex in extractions:
        record = DocumentExtraction(
            document_id=document_id,
            chunk_id=chunk_id,
            clinic_id=clinic_id,
            entity_type=ex.entity_type,
            extracted_data=ex.extracted_data,
            raw_text=ex.raw_text,
            extraction_method=ex.extraction_method,
            confidence=ex.confidence,
            requires_review=ex.requires_review,
            status="pending",
            created_at=now,
        )
        session.add(record)
        records.append(record)
    await session.flush()
    return records