from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.admin import (
    AISettingsUpdate,
    BrandingUpdate,
    ClinicProfileUpdate,
    ClinicSettingsRead,
    InsuranceCreate,
    InsuranceRead,
    InsuranceUpdate,
    PromptCreate,
    PromptRead,
    PromptUpdate,
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Clinic Profile ──────────────────────────────────────────────────────────

@router.get("/clinic", response_model=ClinicSettingsRead)
async def get_clinic(session: AsyncSession = Depends(get_session)) -> ClinicSettingsRead:
    svc = AdminService(session)
    return await svc.get_clinic_settings()


@router.patch("/clinic/profile", response_model=ClinicSettingsRead)
async def update_clinic_profile(
    data: ClinicProfileUpdate,
    session: AsyncSession = Depends(get_session),
) -> ClinicSettingsRead:
    svc = AdminService(session)
    return await svc.update_profile(data)


@router.patch("/clinic/branding", response_model=ClinicSettingsRead)
async def update_branding(
    data: BrandingUpdate,
    session: AsyncSession = Depends(get_session),
) -> ClinicSettingsRead:
    svc = AdminService(session)
    return await svc.update_branding(data)


@router.patch("/clinic/ai", response_model=ClinicSettingsRead)
async def update_ai_settings(
    data: AISettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> ClinicSettingsRead:
    svc = AdminService(session)
    return await svc.update_ai_settings(data)


# ── Insurance Catalog ───────────────────────────────────────────────────────

@router.get("/insurance", response_model=list[InsuranceRead])
async def list_insurance(
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[InsuranceRead]:
    svc = AdminService(session)
    return await svc.list_insurance(active_only=active_only)


@router.post("/insurance", response_model=InsuranceRead, status_code=201)
async def create_insurance(
    data: InsuranceCreate,
    session: AsyncSession = Depends(get_session),
) -> InsuranceRead:
    svc = AdminService(session)
    return await svc.create_insurance(data)


@router.patch("/insurance/{insurance_id}", response_model=InsuranceRead)
async def update_insurance(
    insurance_id: uuid.UUID,
    data: InsuranceUpdate,
    session: AsyncSession = Depends(get_session),
) -> InsuranceRead:
    svc = AdminService(session)
    result = await svc.update_insurance(insurance_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Insurance not found")
    return result


@router.delete("/insurance/{insurance_id}", status_code=204)
async def delete_insurance(
    insurance_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    svc = AdminService(session)
    ok = await svc.delete_insurance(insurance_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Insurance not found")


# ── Prompt Registry ─────────────────────────────────────────────────────────

@router.get("/prompts", response_model=list[PromptRead])
async def list_prompts(
    agent: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PromptRead]:
    svc = AdminService(session)
    return await svc.list_prompts(agent=agent)


@router.post("/prompts", response_model=PromptRead, status_code=201)
async def create_prompt(
    data: PromptCreate,
    session: AsyncSession = Depends(get_session),
) -> PromptRead:
    svc = AdminService(session)
    return await svc.create_prompt(data)


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> PromptRead:
    svc = AdminService(session)
    result = await svc.get_prompt(prompt_id)
    if not result:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return result


@router.patch("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: uuid.UUID,
    data: PromptUpdate,
    session: AsyncSession = Depends(get_session),
) -> PromptRead:
    svc = AdminService(session)
    result = await svc.update_prompt(prompt_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return result


# ── Specialties ─────────────────────────────────────────────────────────────

@router.get("/specialties", response_model=list[SpecialtyRead])
async def list_specialties(
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[SpecialtyRead]:
    svc = AdminService(session)
    return await svc.list_specialties(active_only=active_only)


@router.post("/specialties", response_model=SpecialtyRead, status_code=201)
async def create_specialty(
    data: SpecialtyCreate,
    session: AsyncSession = Depends(get_session),
) -> SpecialtyRead:
    svc = AdminService(session)
    return await svc.create_specialty(data)


@router.patch("/specialties/{specialty_id}", response_model=SpecialtyRead)
async def update_specialty(
    specialty_id: uuid.UUID,
    data: SpecialtyUpdate,
    session: AsyncSession = Depends(get_session),
) -> SpecialtyRead:
    svc = AdminService(session)
    result = await svc.update_specialty(specialty_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Specialty not found")
    return result


@router.delete("/specialties/{specialty_id}", status_code=204)
async def delete_specialty(
    specialty_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    svc = AdminService(session)
    ok = await svc.delete_specialty(specialty_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Specialty not found")
