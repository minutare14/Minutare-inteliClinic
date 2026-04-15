from __future__ import annotations

import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        payload: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=json.dumps(payload) if payload else None,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_events(self, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: str,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.resource_type == resource_type)
            .where(AuditEvent.resource_id == resource_id)
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        
        stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count(AuditEvent.id))
        result = await self.session.execute(stmt)
        return result.scalar_one()
