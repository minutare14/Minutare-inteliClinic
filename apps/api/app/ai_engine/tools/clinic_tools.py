"""
Real AI tools — access real database records.
Used by the AI engine to answer questions about professionals and availability.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ─── Tool: list_professionals ─────────────────────────────────────────────────

async def list_professionals(session: AsyncSession) -> list[dict[str, Any]]:
    """
    Returns all ACTIVE professionals with: nome, especialidade, status.
    """
    from app.repositories.professional_repository import ProfessionalRepository

    repo = ProfessionalRepository(session)
    profs = await repo.list_active()

    logger.info("[TOOL:list_professionals] returned=%d", len(profs))
    return [
        {
            "nome": p.full_name,
            "especialidade": p.specialty,
            "status": "ativo" if p.active else "inativo",
            "crm": p.crm,
            "permite_teleconsulta": p.allows_teleconsultation,
        }
        for p in profs
    ]


# ─── Tool: list_specialties ────────────────────────────────────────────────────

async def list_specialties(session: AsyncSession, clinic_id: str) -> list[dict[str, Any]]:
    """
    Returns all ACTIVE specialties from ClinicSpecialty table.
    """
    from app.repositories.admin_repository import AdminRepository

    repo = AdminRepository(session)
    db_specialties = await repo.list_specialties(clinic_id, active_only=True)

    logger.info("[TOOL:list_specialties] returned=%d", len(db_specialties))
    return [
        {"nome": s.name, "descricao": getattr(s, "description", None)}
        for s in db_specialties
    ]


# ─── Tool: get_professionals_by_specialty ─────────────────────────────────────

async def get_professionals_by_specialty(
    session: AsyncSession, specialty: str
) -> list[dict[str, Any]]:
    """
    Returns all ACTIVE professionals for a given specialty.
    """
    from app.repositories.professional_repository import ProfessionalRepository

    repo = ProfessionalRepository(session)
    profs = await repo.list_active(specialty=specialty)

    logger.info(
        "[TOOL:get_professionals_by_specialty] specialty=%s returned=%d",
        specialty, len(profs),
    )
    if not profs:
        return []

    return [
        {
            "nome": p.full_name,
            "especialidade": p.specialty,
            "status": "ativo" if p.active else "inativo",
            "crm": p.crm,
            "permite_teleconsulta": p.allows_teleconsultation,
        }
        for p in profs
    ]


# ─── Tool: check_availability ──────────────────────────────────────────────────

async def check_availability(
    session: AsyncSession,
    professional_id: str | None = None,
    specialty: str | None = None,
    target_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Returns available slots for a professional or specialty on a given date.

    Args:
        session: DB session
        professional_id: UUID of the professional (optional)
        specialty: specialty name (optional, used if no professional_id)
        target_date: ISO date string YYYY-MM-DD (optional, defaults to today+today+6)
    """
    from app.repositories.schedule_repository import ScheduleRepository
    from app.models.schedule import SlotStatus

    sched_repo = ScheduleRepository(session)

    # Default: next 7 days
    if target_date:
        try:
            date_from = date.fromisoformat(target_date)
        except ValueError:
            date_from = date.today()
    else:
        date_from = date.today()

    date_to = date_from + timedelta(days=6)

    # Determine professional_ids to check
    professional_ids: list[str] | None = None
    if professional_id:
        professional_ids = [professional_id]
    elif specialty:
        from app.repositories.professional_repository import ProfessionalRepository
        prof_repo = ProfessionalRepository(session)
        profs = await prof_repo.list_active(specialty=specialty)
        professional_ids = [str(p.id) for p in profs]

    import uuid

    slots = await sched_repo.find_available(
        professional_id=uuid.UUID(professional_ids[0]) if professional_ids and professional_ids[0] else None,
        date_from=date_from,
        date_to=date_to,
    )

    logger.info(
        "[TOOL:check_availability] prof=%s specialty=%s date=%s returned=%d",
        professional_id, specialty, target_date, len(slots),
    )

    return [
        {
            "slot_id": str(s.id),
            "professional_id": str(s.professional_id),
            "start_at": s.start_at.isoformat() if s.start_at else None,
            "end_at": s.end_at.isoformat() if s.end_at else None,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "tipo": s.slot_type.value if hasattr(s.slot_type, "value") else s.slot_type,
        }
        for s in slots
        if s.status == SlotStatus.available
    ]
