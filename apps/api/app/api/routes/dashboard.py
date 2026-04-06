from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.patient import Patient
from app.models.conversation import Conversation, Handoff
from app.models.schedule import ScheduleSlot
from app.models.rag import RagDocument, RagChunk

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    total_patients: int
    total_conversations: int
    total_handoffs_open: int
    total_slots: int
    total_slots_booked: int
    total_rag_documents: int
    total_rag_chunks: int


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    patients = (await session.execute(select(func.count(Patient.id)))).scalar_one()
    conversations = (await session.execute(select(func.count(Conversation.id)))).scalar_one()
    handoffs_open = (await session.execute(
        select(func.count(Handoff.id)).where(Handoff.status == "open")
    )).scalar_one()
    slots = (await session.execute(select(func.count(ScheduleSlot.id)))).scalar_one()
    slots_booked = (await session.execute(
        select(func.count(ScheduleSlot.id)).where(ScheduleSlot.status == "booked")
    )).scalar_one()
    rag_docs = (await session.execute(select(func.count(RagDocument.id)))).scalar_one()
    rag_chunks = (await session.execute(select(func.count(RagChunk.id)))).scalar_one()

    return DashboardSummary(
        total_patients=patients,
        total_conversations=conversations,
        total_handoffs_open=handoffs_open,
        total_slots=slots,
        total_slots_booked=slots_booked,
        total_rag_documents=rag_docs,
        total_rag_chunks=rag_chunks,
    )
