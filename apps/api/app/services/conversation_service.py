from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Handoff, Message
from app.repositories.conversation_repository import ConversationRepository
from app.services.audit_service import AuditService


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ConversationRepository(session)
        self.audit = AuditService(session)

    async def get_or_create(
        self, patient_id: uuid.UUID, channel: str = "telegram"
    ) -> Conversation:
        conv, created = await self.repo.get_or_create_active(patient_id, channel)
        if created:
            await self.audit.log_event(
                actor_type="system",
                actor_id="conversation_service",
                action="conversation.created",
                resource_type="conversation",
                resource_id=str(conv.id),
            )
        return conv

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.repo.get_by_id(conversation_id)

    async def list_conversations(
        self, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Conversation]:
        return await self.repo.list_all(status=status, limit=limit, offset=offset)

    async def list_handoffs(
        self, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list["Handoff"]:
        return await self.repo.list_handoffs(status=status, limit=limit, offset=offset)

    async def update_handoff_status(self, handoff_id: uuid.UUID, status: str) -> "Handoff | None":
        return await self.repo.update_handoff_status(handoff_id, status)

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        direction: str,
        content: str,
        raw_payload: str | None = None,
    ) -> Message:
        return await self.repo.add_message(conversation_id, direction, content, raw_payload)

    async def update_intent(
        self, conversation_id: uuid.UUID, intent: str, confidence: float
    ) -> None:
        await self.repo.update_intent(conversation_id, intent, confidence)

    async def get_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        return await self.repo.get_messages(conversation_id)

    async def create_handoff(
        self,
        conversation_id: uuid.UUID,
        reason: str,
        priority: str = "normal",
        context_summary: str | None = None,
    ) -> Handoff:
        handoff = await self.repo.create_handoff(
            conversation_id, reason, priority, context_summary
        )
        await self.audit.log_event(
            actor_type="ai",
            actor_id="conversation_service",
            action="handoff.created",
            resource_type="handoff",
            resource_id=str(handoff.id),
            payload={"reason": reason, "priority": priority},
        )
        return handoff
