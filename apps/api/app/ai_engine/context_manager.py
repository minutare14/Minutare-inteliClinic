"""
Context Manager — Manages conversation context and patient profile.

Adapted from minutare.ai 3-layer memory architecture:
- Layer A: Short history (last N messages)
- Layer B: Patient profile (persistent, from DB)
- Layer C: FARO brief (session, from analysis)

This module builds the full context that feeds the response builder.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.patient import Patient
from app.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6


@dataclass
class ConversationContext:
    """Full context for response generation."""
    # Patient
    patient_id: uuid.UUID | None = None
    patient_name: str = "Paciente"
    patient_cpf: str | None = None
    patient_email: str | None = None
    patient_phone: str | None = None
    patient_convenio: str | None = None
    consented_ai: bool = False

    # Conversation
    conversation_id: uuid.UUID | None = None
    channel: str = "telegram"
    current_intent: str | None = None

    # History (last N messages as dicts)
    history: list[dict] = field(default_factory=list)

    # FARO brief
    faro_brief: dict = field(default_factory=dict)

    def patient_profile_block(self) -> str:
        """Format patient profile for prompt injection."""
        lines = ["## PERFIL DO PACIENTE (MEMÓRIA PERSISTENTE)"]
        lines.append("Use estes dados se o paciente não informar outros na mensagem atual.")
        lines.append(f"- Nome: {self.patient_name or 'Não informado'}")
        lines.append(f"- E-mail: {self.patient_email or 'Não informado'}")
        lines.append(f"- CPF: {self.patient_cpf or 'Não informado'}")
        lines.append(f"- Telefone: {self.patient_phone or 'Não informado'}")
        lines.append(f"- Convênio: {self.patient_convenio or 'Não informado'}")
        return "\n".join(lines)

    def history_block(self) -> str:
        """Format recent history for prompt context."""
        if not self.history:
            return ""
        lines = ["## HISTÓRICO RECENTE"]
        for msg in self.history:
            role = "Paciente" if msg["direction"] == "inbound" else "Assistente"
            lines.append(f"{role}: {msg['content'][:300]}")
        return "\n".join(lines)


class ContextManager:
    """Builds conversation context from DB state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_repo = ConversationRepository(session)

    async def build_context(
        self,
        patient: Patient,
        conversation: Conversation,
        faro_brief: dict | None = None,
    ) -> ConversationContext:
        """
        Build full context for the AI engine.
        Loads recent messages and patient profile.
        """
        # Load recent messages
        messages = await self.conv_repo.get_messages(conversation.id)
        recent = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages

        history = [
            {"direction": m.direction, "content": m.content}
            for m in recent
        ]

        ctx = ConversationContext(
            patient_id=patient.id,
            patient_name=patient.full_name,
            patient_cpf=patient.cpf,
            patient_email=patient.email,
            patient_phone=patient.phone,
            patient_convenio=patient.convenio_name,
            consented_ai=patient.consented_ai,
            conversation_id=conversation.id,
            channel=conversation.channel,
            current_intent=conversation.current_intent,
            history=history,
            faro_brief=faro_brief or {},
        )

        return ctx
