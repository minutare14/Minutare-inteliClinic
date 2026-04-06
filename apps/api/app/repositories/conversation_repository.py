from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus, Handoff, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(
        self, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Conversation]:
        stmt = select(Conversation)
        if status:
            stmt = stmt.where(Conversation.status == status)
        stmt = stmt.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_handoffs(
        self, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Handoff]:
        stmt = select(Handoff)
        if status:
            stmt = stmt.where(Handoff.status == status)
        stmt = stmt.order_by(Handoff.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_handoff_by_id(self, handoff_id: uuid.UUID) -> Handoff | None:
        return await self.session.get(Handoff, handoff_id)

    async def update_handoff_status(self, handoff_id: uuid.UUID, status: str) -> Handoff | None:
        handoff = await self.get_handoff_by_id(handoff_id)
        if not handoff:
            return None
        handoff.status = status
        self.session.add(handoff)
        await self.session.commit()
        await self.session.refresh(handoff)
        return handoff

    async def get_or_create_active(
        self, patient_id: uuid.UUID, channel: str = "telegram"
    ) -> tuple[Conversation, bool]:
        """Return (conversation, created). Reuse active conversation if exists."""
        stmt = select(Conversation).where(
            and_(
                Conversation.patient_id == patient_id,
                Conversation.channel == channel,
                Conversation.status.in_([
                    ConversationStatus.active,
                    ConversationStatus.waiting_input,
                ]),
            )
        )
        result = await self.session.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            return conv, False

        conv = Conversation(patient_id=patient_id, channel=channel)
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv, True

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def update_intent(
        self, conversation_id: uuid.UUID, intent: str, confidence: float
    ) -> None:
        conv = await self.get_by_id(conversation_id)
        if conv:
            conv.current_intent = intent
            conv.confidence_score = confidence
            conv.updated_at = datetime.utcnow()
            self.session.add(conv)
            await self.session.commit()

    async def escalate(self, conversation_id: uuid.UUID, assignee: str | None = None) -> None:
        conv = await self.get_by_id(conversation_id)
        if conv:
            conv.status = ConversationStatus.escalated
            conv.human_assignee = assignee
            conv.updated_at = datetime.utcnow()
            self.session.add(conv)
            await self.session.commit()

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        direction: str,
        content: str,
        raw_payload: str | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            direction=direction,
            content=content,
            raw_payload=raw_payload,
        )
        self.session.add(msg)
        # Update last_message_at
        conv = await self.get_by_id(conversation_id)
        if conv:
            conv.last_message_at = datetime.utcnow()
            self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_handoff(
        self,
        conversation_id: uuid.UUID,
        reason: str,
        priority: str = "normal",
        context_summary: str | None = None,
    ) -> Handoff:
        handoff = Handoff(
            conversation_id=conversation_id,
            reason=reason,
            priority=priority,
            context_summary=context_summary,
        )
        self.session.add(handoff)
        await self.escalate(conversation_id)
        await self.session.commit()
        await self.session.refresh(handoff)
        return handoff
