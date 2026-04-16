"""
CRM routes — Lead management, follow-ups, alerts.

All endpoints require authentication.
Stage-changing and follow-up creation require reception or above.
Alert resolution requires manager or admin.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.models.jobs import AlertPriority, FollowUpType
from app.services.crm_service import CrmService

router = APIRouter(prefix="/crm", tags=["crm"])

_MANAGER_ROLES = (UserRole.admin, UserRole.manager)
_STAFF_ROLES = (UserRole.admin, UserRole.manager, UserRole.reception)


# ── Schemas ───────────────────────────────────────────────────────────────────

class StageUpdateRequest(BaseModel):
    stage: str  # lead | patient | inactive


class AddTagsRequest(BaseModel):
    tags: list[str]


class AddNoteRequest(BaseModel):
    note: str


class FollowUpCreateRequest(BaseModel):
    patient_id: uuid.UUID
    followup_type: FollowUpType = FollowUpType.manual
    scheduled_at: datetime
    notes: str | None = None


class AlertCreateRequest(BaseModel):
    patient_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message: str
    alert_type: str = "general"
    priority: AlertPriority = AlertPriority.normal


# ── Leads / patients ──────────────────────────────────────────────────────────

@router.get("/leads")
async def list_leads(
    stage: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    """List patients by CRM stage. Any authenticated user."""
    svc = CrmService(session)
    patients = await svc.list_by_stage(stage=stage, limit=limit, offset=offset)
    return [
        {
            "id": str(p.id),
            "full_name": p.full_name,
            "phone": p.phone,
            "stage": p.stage,
            "tags": p.tags.split(",") if p.tags else [],
            "source": p.source,
            "crm_notes": p.crm_notes,
            "created_at": p.created_at,
        }
        for p in patients
    ]


@router.patch("/leads/{patient_id}/stage")
async def update_stage(
    patient_id: uuid.UUID,
    body: StageUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(*_STAFF_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    patient = await svc.update_stage(
        patient_id, body.stage, actor_id=current_user.email
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    return {"id": str(patient.id), "stage": patient.stage}


@router.patch("/leads/{patient_id}/tags")
async def add_tags(
    patient_id: uuid.UUID,
    body: AddTagsRequest,
    current_user: Annotated[User, Depends(require_roles(*_STAFF_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    patient = await svc.add_tags(patient_id, body.tags)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    return {"id": str(patient.id), "tags": patient.tags}


@router.post("/leads/{patient_id}/notes")
async def add_note(
    patient_id: uuid.UUID,
    body: AddNoteRequest,
    current_user: Annotated[User, Depends(require_roles(*_STAFF_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    patient = await svc.add_note(patient_id, body.note, actor_id=current_user.email)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    return {"id": str(patient.id), "crm_notes": patient.crm_notes}


@router.get("/stats")
async def get_stats(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    return await svc.get_stats()


# ── Follow-ups ────────────────────────────────────────────────────────────────

@router.post("/followups", status_code=201)
async def create_followup(
    body: FollowUpCreateRequest,
    current_user: Annotated[User, Depends(require_roles(*_STAFF_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    fu = await svc.schedule_followup(
        patient_id=body.patient_id,
        followup_type=body.followup_type,
        scheduled_at=body.scheduled_at,
        notes=body.notes,
        created_by=current_user.email,
    )
    return {"id": str(fu.id), "scheduled_at": fu.scheduled_at, "type": fu.followup_type}


@router.get("/followups/pending")
async def list_pending_followups(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    items = await svc.list_pending_followups()
    return [
        {
            "id": str(f.id),
            "patient_id": str(f.patient_id),
            "type": f.followup_type,
            "scheduled_at": f.scheduled_at,
            "notes": f.notes,
        }
        for f in items
    ]


@router.patch("/followups/{followup_id}/complete")
async def complete_followup(
    followup_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_STAFF_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    fu = await svc.complete_followup(followup_id)
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up não encontrado")
    return {"id": str(fu.id), "completed": fu.completed}


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    alert = await svc.create_alert(
        patient_id=body.patient_id,
        message=body.message,
        alert_type=body.alert_type,
        priority=body.priority,
        conversation_id=body.conversation_id,
    )
    return {"id": str(alert.id), "priority": alert.priority, "created_at": alert.created_at}


@router.get("/alerts")
async def list_alerts(
    priority: AlertPriority | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    alerts = await svc.list_open_alerts(priority=priority)
    return [
        {
            "id": str(a.id),
            "patient_id": str(a.patient_id) if a.patient_id else None,
            "type": a.alert_type,
            "message": a.message,
            "priority": a.priority,
            "created_at": a.created_at,
        }
        for a in alerts
    ]


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_MANAGER_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
):
    svc = CrmService(session)
    alert = await svc.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return {"id": str(alert.id), "resolved": alert.resolved}
