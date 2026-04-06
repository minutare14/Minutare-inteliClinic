from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Handoff
from app.services.conversation_service import ConversationService


class HandoffService:
    def __init__(self, session: AsyncSession) -> None:
        self.conversation_svc = ConversationService(session)

    async def create(
        self,
        conversation_id: uuid.UUID,
        reason: str,
        priority: str = "normal",
        context_summary: str | None = None,
    ) -> Handoff:
        return await self.conversation_svc.create_handoff(
            conversation_id=conversation_id,
            reason=reason,
            priority=priority,
            context_summary=context_summary,
        )
