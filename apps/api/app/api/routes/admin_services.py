"""Admin routes for services, prices, rules, and professional links."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.db import get_session
from app.core.config import settings
from app.models.auth import User, UserRole
from app.repositories.service_repository import ServiceRepository
from app.schemas.admin import (
    ServiceCategoryCreate,
    ServiceCategoryRead,
    ServiceCategoryUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceRuleCreate,
    ServiceRuleRead,
    ServiceRuleUpdate,
    ServicePriceUpsert,
    ProfessionalServiceLinkCreate,
    ProfessionalServiceLinkRead,
)
from app.services.audit_service import AuditService
from app.services.pinecone_structured_sync import sync_service_to_pinecone

router = APIRouter(prefix="/admin", tags=["admin"])

_READ_ROLES = (UserRole.admin, UserRole.manager)
_WRITE_ROLES = (UserRole.admin,)


async def _audit(session: AsyncSession, actor_id: str, action: str, resource_id: str, payload: dict | None = None):
    audit = AuditService(session)
    await audit.log_event(
        actor_type="user",
        actor_id=actor_id,
        action=action,
        resource_type="service",
        resource_id=str(resource_id),
        payload=payload,
    )


# ── Service Categories ───────────────────────────────────────────────────────

@router.get("/services/categories", response_model=list[ServiceCategoryRead])
async def list_service_categories(
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ServiceCategoryRead]:
    repo = ServiceRepository(session)
    return await repo.list_categories(settings.clinic_id)


@router.post("/services/categories", response_model=ServiceCategoryRead)
async def create_service_category(
    data: ServiceCategoryCreate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceCategoryRead:
    repo = ServiceRepository(session)
    cat = await repo.create_category(settings.clinic_id, data.name, data.description)
    await _audit(session, str(current_user.id), "service_category.created", str(cat.id))
    return cat


@router.patch("/services/categories/{category_id}", response_model=ServiceCategoryRead)
async def update_service_category(
    category_id: uuid.UUID,
    data: ServiceCategoryUpdate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceCategoryRead:
    from app.models.service import ServiceCategory
    row = await session.get(ServiceCategory, category_id)
    if not row or row.clinic_id != settings.clinic_id:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    if data.name is not None:
        row.name = data.name
    if data.description is not None:
        row.description = data.description
    if data.active is not None:
        row.active = data.active
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await _audit(session, str(current_user.id), "service_category.updated", str(row.id))
    return row


# ── Services ─────────────────────────────────────────────────────────────────

@router.get("/services", response_model=list[ServiceRead])
async def list_services(
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ServiceRead]:
    repo = ServiceRepository(session)
    services = await repo.list_services_with_prices(settings.clinic_id)
    return [ServiceRead(**s) for s in services]


@router.post("/services", response_model=ServiceRead)
async def create_service(
    data: ServiceCreate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRead:
    repo = ServiceRepository(session)
    svc = await repo.create_service(
        clinic_id=settings.clinic_id,
        name=data.name,
        description=data.description,
        category_id=data.category_id,
        duration_min=data.duration_min,
        requires_specific_doctor=data.requires_specific_doctor,
        ai_summary=data.ai_summary,
        active=data.active,
    )
    await _audit(session, str(current_user.id), "service.created", str(svc.id), {"name": data.name})
    service_dict = await repo.get_service_with_doctors(svc.id)
    return ServiceRead(**service_dict)


@router.get("/services/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRead:
    repo = ServiceRepository(session)
    svc = await repo.get_service_with_doctors(service_id)
    if not svc or svc.get("clinic_id") != settings.clinic_id:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return ServiceRead(**svc)


@router.patch("/services/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: uuid.UUID,
    data: ServiceUpdate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRead:
    repo = ServiceRepository(session)
    svc = await repo.update_service(
        service_id,
        name=data.name,
        description=data.description,
        category_id=data.category_id,
        duration_min=data.duration_min,
        requires_specific_doctor=data.requires_specific_doctor,
        ai_summary=data.ai_summary,
        active=data.active,
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    await _audit(session, str(current_user.id), "service.updated", str(svc.id), {"name": svc.name})
    service_dict = await repo.get_service_with_doctors(svc.id)
    await sync_service_to_pinecone(svc.id, session)
    return ServiceRead(**service_dict)


@router.delete("/services/{service_id}", response_model=ServiceRead)
async def deactivate_service(
    service_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRead:
    repo = ServiceRepository(session)
    svc = await repo.deactivate_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    await _audit(session, str(current_user.id), "service.deactivated", str(svc.id))
    service_dict = await repo.get_service_with_doctors(svc.id)
    await sync_service_to_pinecone(svc.id, session)
    return ServiceRead(**service_dict)


# ── Service Prices ─────────────────────────────────────────────────────────

@router.post("/services/{service_id}/prices")
async def upsert_service_price(
    service_id: uuid.UUID,
    data: ServicePriceUpsert,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = ServiceRepository(session)
    price = await repo.upsert_price(
        service_id=service_id,
        clinic_id=settings.clinic_id,
        price=data.price,
        insurance_plan_id=data.insurance_plan_id,
        copay=data.copay,
        changed_by=str(current_user.id),
    )
    await _audit(
        session, str(current_user.id), "service_price.updated",
        str(price.id),
        {"service_id": str(service_id), "price": data.price},
    )
    await sync_service_to_pinecone(service_id, session)
    return {"id": price.id, "price": price.price, "copay": price.copay, "version": price.version}


@router.get("/services/{service_id}/prices", response_model=list[ServicePriceUpsert])
async def list_service_prices(
    service_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ServicePriceUpsert]:
    repo = ServiceRepository(session)
    prices = await repo.list_prices_for_service(service_id)
    return [
        ServicePriceUpsert(
            insurance_plan_id=p.insurance_plan_id,
            price=p.price,
            copay=p.copay,
        )
        for p in prices
    ]


# ── Professional Links ─────────────────────────────────────────────────────

@router.post("/services/{service_id}/doctors", response_model=ProfessionalServiceLinkRead)
async def link_professional_to_service(
    service_id: uuid.UUID,
    data: ProfessionalServiceLinkCreate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfessionalServiceLinkRead:
    repo = ServiceRepository(session)
    link = await repo.link_professional_to_service(
        professional_id=data.professional_id,
        service_id=service_id,
        clinic_id=settings.clinic_id,
        notes=data.notes,
        priority_order=data.priority_order,
    )
    await _audit(
        session, str(current_user.id), "service_doctor.linked",
        str(link.id),
        {"professional_id": str(data.professional_id), "service_id": str(service_id)},
    )
    await sync_service_to_pinecone(service_id, session)
    return ProfessionalServiceLinkRead(
        id=link.id,
        professional_id=link.professional_id,
        service_id=link.service_id,
        notes=link.notes,
        active=link.active,
        priority_order=link.priority_order,
        created_at=link.created_at,
    )


@router.delete("/services/{service_id}/doctors/{professional_id}")
async def unlink_professional_from_service(
    service_id: uuid.UUID,
    professional_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = ServiceRepository(session)
    ok = await repo.unlink_professional_from_service(professional_id, service_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    await _audit(
        session, str(current_user.id), "service_doctor.unlinked",
        f"{service_id}/{professional_id}",
        {"professional_id": str(professional_id), "service_id": str(service_id)},
    )
    await sync_service_to_pinecone(service_id, session)
    return {"ok": True}


# ── Operational Rules ───────────────────────────────────────────────────────

@router.post("/services/{service_id}/rules", response_model=ServiceRuleRead)
async def set_service_rule(
    service_id: uuid.UUID,
    data: ServiceRuleCreate,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRuleRead:
    repo = ServiceRepository(session)
    rule = await repo.set_service_rule(
        service_id=service_id,
        clinic_id=settings.clinic_id,
        rule_type=data.rule_type,
        rule_text=data.rule_text,
    )
    await _audit(
        session, str(current_user.id), "service_rule.set",
        str(rule.id),
        {"service_id": str(service_id), "rule_type": data.rule_type},
    )
    return ServiceRuleRead(
        id=rule.id,
        service_id=rule.service_id,
        rule_type=rule.rule_type,
        rule_text=rule.rule_text,
        active=rule.active,
        version=rule.version,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.get("/services/{service_id}/rules", response_model=list[ServiceRuleRead])
async def list_service_rules(
    service_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ServiceRuleRead]:
    repo = ServiceRepository(session)
    rules = await repo.list_service_rules(service_id)
    return [ServiceRuleRead(
        id=r.id,
        service_id=r.service_id,
        rule_type=r.rule_type,
        rule_text=r.rule_text,
        active=r.active,
        version=r.version,
        created_at=r.created_at,
        updated_at=r.updated_at,
    ) for r in rules]
