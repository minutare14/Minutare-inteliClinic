"""ServiceRepository — CRUD for services, prices, rules, and professional links."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import (
    Service,
    ServiceCategory,
    ServicePrice,
    ServiceOperationalRule,
    ProfessionalServiceLink,
)
from app.models.professional import Professional


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Categories ────────────────────────────────────────────────────────

    async def list_categories(self, clinic_id: str, active_only: bool = True) -> list[ServiceCategory]:
        stmt = select(ServiceCategory).where(ServiceCategory.clinic_id == clinic_id)
        if active_only:
            stmt = stmt.where(ServiceCategory.active == True)
        stmt = stmt.order_by(ServiceCategory.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_category(self, clinic_id: str, name: str, description: str | None = None) -> ServiceCategory:
        cat = ServiceCategory(clinic_id=clinic_id, name=name, description=description)
        self.session.add(cat)
        await self.session.commit()
        await self.session.refresh(cat)
        return cat

    # ── Services ────────────────────────────────────────────────────────────

    async def list_services(
        self, clinic_id: str, active_only: bool = True, category_id: uuid.UUID | None = None
    ) -> list[Service]:
        stmt = select(Service).where(Service.clinic_id == clinic_id)
        if active_only:
            stmt = stmt.where(Service.active == True)
        if category_id:
            stmt = stmt.where(Service.category_id == category_id)
        stmt = stmt.order_by(Service.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_services_with_prices(
        self, clinic_id: str, active_only: bool = True
    ) -> list[dict]:
        """Return services with base price, category name, and linked active professionals."""
        services = await self.list_services(clinic_id, active_only=active_only)
        result = []
        for svc in services:
            # Category name
            cat_name = None
            if svc.category_id:
                cat_row = await self.session.get(ServiceCategory, svc.category_id)
                cat_name = cat_row.name if cat_row else None

            # Base price (no insurance = particular)
            base_price_row = await self.session.execute(
                select(ServicePrice).where(
                    and_(
                        ServicePrice.service_id == svc.id,
                        ServicePrice.insurance_plan_id.is_(None),
                        ServicePrice.active == True,
                    )
                )
            )
            base_price = None
            if base_price_row.scalars().one_or_none() is not None:
                base_price = base_price_row.scalars().one().price

            # Linked professionals
            links_rows = await self.session.execute(
                select(ProfessionalServiceLink).where(
                    and_(
                        ProfessionalServiceLink.service_id == svc.id,
                        ProfessionalServiceLink.active == True,
                    )
                )
            )
            links = list(links_rows.scalars().all())
            prof_ids = [lnk.professional_id for lnk in links if lnk.professional_id]
            profs = []
            if prof_ids:
                prof_result = await self.session.execute(
                    select(Professional).where(
                        and_(
                            Professional.id.in_(prof_ids),
                            Professional.active == True,
                        )
                    )
                )
                profs = list(prof_result.scalars().all())

            result.append({
                "id": svc.id,
                "clinic_id": svc.clinic_id,
                "name": svc.name,
                "description": svc.description,
                "category_id": svc.category_id,
                "category_name": cat_name,
                "duration_min": svc.duration_min,
                "active": svc.active,
                "requires_specific_doctor": svc.requires_specific_doctor,
                "ai_summary": svc.ai_summary,
                "version": svc.version,
                "base_price": base_price,
                "doctors": [{"id": p.id, "full_name": p.full_name, "specialty": p.specialty} for p in profs],
                "created_at": svc.created_at,
                "updated_at": svc.updated_at,
            })
        return result

    async def get_service_with_doctors(self, service_id: uuid.UUID) -> dict | None:
        row = await self.session.get(Service, service_id)
        if not row:
            return None
        svc = row

        # Category
        cat_name = None
        if svc.category_id:
            cat_row = await self.session.get(ServiceCategory, svc.category_id)
            cat_name = cat_row.name if cat_row else None

        # Prices
        prices_result = await self.session.execute(
            select(ServicePrice).where(
                and_(ServicePrice.service_id == svc.id, ServicePrice.active == True)
            )
        )
        prices = list(prices_result.scalars().all())

        # Linked professionals
        links_rows = await self.session.execute(
            select(ProfessionalServiceLink).where(
                and_(
                    ProfessionalServiceLink.service_id == svc.id,
                    ProfessionalServiceLink.active == True,
                )
            )
        )
        links = list(links_rows.scalars().all())
        prof_ids = [lnk.professional_id for lnk in links if lnk.professional_id]
        profs = []
        if prof_ids:
            prof_result = await self.session.execute(
                select(Professional).where(Professional.id.in_(prof_ids))
            )
            profs = list(prof_result.scalars().all())

        # Rules
        rules_result = await self.session.execute(
            select(ServiceOperationalRule).where(
                and_(
                    ServiceOperationalRule.service_id == svc.id,
                    ServiceOperationalRule.active == True,
                )
            )
        )
        rules = list(rules_result.scalars().all())

        return {
            "id": svc.id,
            "clinic_id": svc.clinic_id,
            "name": svc.name,
            "description": svc.description,
            "category_id": svc.category_id,
            "category_name": cat_name,
            "duration_min": svc.duration_min,
            "active": svc.active,
            "requires_specific_doctor": svc.requires_specific_doctor,
            "ai_summary": svc.ai_summary,
            "version": svc.version,
            "prices": [
                {
                    "id": p.id,
                    "insurance_plan_id": p.insurance_plan_id,
                    "price": p.price,
                    "copay": p.copay,
                    "version": p.version,
                }
                for p in prices
            ],
            "doctors": [{"id": p.id, "full_name": p.full_name, "specialty": p.specialty, "crm": p.crm} for p in profs],
            "rules": [
                {"id": r.id, "rule_type": r.rule_type, "rule_text": r.rule_text, "version": r.version}
                for r in rules
            ],
            "created_at": svc.created_at,
            "updated_at": svc.updated_at,
        }

    async def create_service(
        self,
        clinic_id: str,
        name: str,
        description: str | None = None,
        category_id: uuid.UUID | None = None,
        duration_min: int = 30,
        requires_specific_doctor: bool = True,
        ai_summary: str | None = None,
        active: bool = True,
    ) -> Service:
        svc = Service(
            clinic_id=clinic_id,
            name=name,
            description=description,
            category_id=category_id,
            duration_min=duration_min,
            requires_specific_doctor=requires_specific_doctor,
            ai_summary=ai_summary,
            active=active,
        )
        self.session.add(svc)
        await self.session.commit()
        await self.session.refresh(svc)
        return svc

    async def update_service(
        self,
        service_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        category_id: uuid.UUID | None = None,
        duration_min: int | None = None,
        requires_specific_doctor: bool | None = None,
        ai_summary: str | None = None,
        active: bool | None = None,
    ) -> Service | None:
        row = await self.session.get(Service, service_id)
        if not row:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if category_id is not None:
            row.category_id = category_id
        if duration_min is not None:
            row.duration_min = duration_min
        if requires_specific_doctor is not None:
            row.requires_specific_doctor = requires_specific_doctor
        if ai_summary is not None:
            row.ai_summary = ai_summary
        if active is not None:
            row.active = active
        row.version = (row.version or 1) + 1
        row.updated_at = datetime.utcnow()
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def deactivate_service(self, service_id: uuid.UUID) -> Service | None:
        return await self.update_service(service_id, active=False)

    # ── Prices ────────────────────────────────────────────────────────────────

    async def upsert_price(
        self,
        service_id: uuid.UUID,
        clinic_id: str,
        price: float,
        insurance_plan_id: uuid.UUID | None = None,
        copay: float | None = None,
        changed_by: str | None = None,
    ) -> ServicePrice:
        # Find existing
        stmt = select(ServicePrice).where(
            and_(
                ServicePrice.service_id == service_id,
                ServicePrice.insurance_plan_id.is_(insurance_plan_id)
                if insurance_plan_id is None
                else ServicePrice.insurance_plan_id == insurance_plan_id,
                ServicePrice.active == True,
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().one_or_none()

        if existing:
            existing.price = price
            if copay is not None:
                existing.copay = copay
            existing.price_changed_at = datetime.utcnow()
            if changed_by:
                existing.changed_by = changed_by
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.utcnow()
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            sp = ServicePrice(
                clinic_id=clinic_id,
                service_id=service_id,
                insurance_plan_id=insurance_plan_id,
                price=price,
                copay=copay,
                price_changed_at=datetime.utcnow(),
                changed_by=changed_by,
            )
            self.session.add(sp)
            await self.session.commit()
            await self.session.refresh(sp)
            return sp

    async def get_active_price(self, service_id: uuid.UUID) -> ServicePrice | None:
        """Get the base (particular) price for a service."""
        result = await self.session.execute(
            select(ServicePrice).where(
                and_(
                    ServicePrice.service_id == service_id,
                    ServicePrice.insurance_plan_id.is_(None),
                    ServicePrice.active == True,
                )
            )
        )
        return result.scalars().one_or_none()

    async def list_prices_for_service(self, service_id: uuid.UUID) -> list[ServicePrice]:
        result = await self.session.execute(
            select(ServicePrice).where(
                and_(ServicePrice.service_id == service_id, ServicePrice.active == True)
            )
        )
        return list(result.scalars().all())

    # ── Professional links ─────────────────────────────────────────────────

    async def link_professional_to_service(
        self,
        professional_id: uuid.UUID,
        service_id: uuid.UUID,
        clinic_id: str,
        notes: str | None = None,
        priority_order: int = 0,
    ) -> ProfessionalServiceLink:
        # Check existing active link
        result = await self.session.execute(
            select(ProfessionalServiceLink).where(
                and_(
                    ProfessionalServiceLink.professional_id == professional_id,
                    ProfessionalServiceLink.service_id == service_id,
                    ProfessionalServiceLink.active == True,
                )
            )
        )
        existing = result.scalars().one_or_none()
        if existing:
            existing.notes = notes
            existing.priority_order = priority_order
            existing.updated_at = datetime.utcnow()
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        link = ProfessionalServiceLink(
            clinic_id=clinic_id,
            professional_id=professional_id,
            service_id=service_id,
            notes=notes,
            priority_order=priority_order,
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def unlink_professional_from_service(
        self, professional_id: uuid.UUID, service_id: uuid.UUID
    ) -> bool:
        result = await self.session.execute(
            select(ProfessionalServiceLink).where(
                and_(
                    ProfessionalServiceLink.professional_id == professional_id,
                    ProfessionalServiceLink.service_id == service_id,
                    ProfessionalServiceLink.active == True,
                )
            )
        )
        link = result.scalars().one_or_none()
        if not link:
            return False
        link.active = False
        link.updated_at = datetime.utcnow()
        self.session.add(link)
        await self.session.commit()
        return True

    async def list_doctors_for_service(self, service_id: uuid.UUID) -> list[Professional]:
        links_result = await self.session.execute(
            select(ProfessionalServiceLink).where(
                and_(
                    ProfessionalServiceLink.service_id == service_id,
                    ProfessionalServiceLink.active == True,
                )
            ).order_by(ProfessionalServiceLink.priority_order)
        )
        links = list(links_result.scalars().all())
        prof_ids = [lnk.professional_id for lnk in links if lnk.professional_id]
        if not prof_ids:
            return []
        profs_result = await self.session.execute(
            select(Professional).where(
                and_(
                    Professional.id.in_(prof_ids),
                    Professional.active == True,
                )
            )
        )
        return list(profs_result.scalars().all())

    # ── Operational rules ────────────────────────────────────────────────────

    async def set_service_rule(
        self,
        service_id: uuid.UUID,
        clinic_id: str,
        rule_type: str,
        rule_text: str,
    ) -> ServiceOperationalRule:
        # Upsert: find existing active rule of same type
        result = await self.session.execute(
            select(ServiceOperationalRule).where(
                and_(
                    ServiceOperationalRule.service_id == service_id,
                    ServiceOperationalRule.rule_type == rule_type,
                    ServiceOperationalRule.active == True,
                )
            )
        )
        existing = result.scalars().one_or_none()
        if existing:
            existing.rule_text = rule_text
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.utcnow()
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        rule = ServiceOperationalRule(
            clinic_id=clinic_id,
            service_id=service_id,
            rule_type=rule_type,
            rule_text=rule_text,
        )
        self.session.add(rule)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def list_service_rules(self, service_id: uuid.UUID) -> list[ServiceOperationalRule]:
        result = await self.session.execute(
            select(ServiceOperationalRule).where(
                and_(
                    ServiceOperationalRule.service_id == service_id,
                    ServiceOperationalRule.active == True,
                )
            )
        )
        return list(result.scalars().all())

    # ── Service by name (for AI lookup) ─────────────────────────────────────

    async def find_service_by_keywords(self, clinic_id: str, keywords: str) -> list[dict]:
        """Fuzzy search service by name keywords (for AI structured lookup)."""
        kw_lower = keywords.lower().strip()
        services = await self.list_services(clinic_id, active_only=True)
        matched = []
        for svc in services:
            if kw_lower in svc.name.lower() or svc.name.lower() in kw_lower:
                doctors = await self.list_doctors_for_service(svc.id)
                base_price = await self.get_active_price(svc.id)
                rules = await self.list_service_rules(svc.id)
                matched.append({
                    "id": svc.id,
                    "name": svc.name,
                    "description": svc.description,
                    "ai_summary": svc.ai_summary,
                    "requires_specific_doctor": svc.requires_specific_doctor,
                    "base_price": base_price.price if base_price else None,
                    "doctors": [
                        {"id": p.id, "full_name": p.full_name, "specialty": p.specialty}
                        for p in doctors
                    ],
                    "rules": {r.rule_type: r.rule_text for r in rules},
                })
        return matched
