from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_session
from app.models.auth import User
from app.models.audit import AuditEvent
from app.models.conversation import Conversation, Message, Handoff
from app.models.patient import Patient
from app.models.schedule import ScheduleSlot
from app.models.rag import RagDocument, RagChunk

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class IntentDistribution(BaseModel):
    intent: str
    count: int
    percentage: float


class IntentAnalyticsResponse(BaseModel):
    total_conversations: int
    intent_distribution: list[IntentDistribution]
    period_days: int


class HandoffRateResponse(BaseModel):
    total_conversations: int
    total_handoffs: int
    handoff_rate_pct: float
    period_days: int


class FunnelStep(BaseModel):
    step: str
    count: int
    percentage: float


class FunnelAnalyticsResponse(BaseModel):
    total_conversations: int
    steps: list[FunnelStep]
    period_days: int


class RAGEvalResult(BaseModel):
    metric: str
    score: float | None


class RAGAnalyticsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    avg_chunks_per_doc: float
    categories: dict[str, int]
    eval_results: list[RAGEvalResult] | None


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
    _: User = Depends(get_current_user),
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


@router.get("/analytics/intent", response_model=IntentAnalyticsResponse)
async def get_intent_analytics(
    period_days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> IntentAnalyticsResponse:
    """Intent distribution from conversation audit events in the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=period_days)
    result = await session.execute(
        select(Conversation.current_intent, func.count(Conversation.id))
        .where(Conversation.created_at >= cutoff)
        .group_by(Conversation.current_intent)
    )
    rows = result.all()
    total = sum(r[1] for r in rows) or 1
    distribution = [
        IntentDistribution(
            intent=r[0] or "unknown",
            count=r[1],
            percentage=round(r[1] / total * 100, 1),
        )
        for r in rows
    ]
    distribution.sort(key=lambda x: x.count, reverse=True)
    return IntentAnalyticsResponse(
        total_conversations=total,
        intent_distribution=distribution,
        period_days=period_days,
    )


@router.get("/analytics/handoff-rate", response_model=HandoffRateResponse)
async def get_handoff_rate(
    period_days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> HandoffRateResponse:
    """Handoff rate: conversations that resulted in human handoff vs total."""
    cutoff = datetime.utcnow() - timedelta(days=period_days)
    total_result = await session.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= cutoff)
    )
    total = total_result.scalar_one() or 1
    handoffs_result = await session.execute(
        select(func.count(Conversation.id))
        .join(Handoff, Handoff.conversation_id == Conversation.id)
        .where(Conversation.created_at >= cutoff)
    )
    handoffs = handoffs_result.scalar_one()
    return HandoffRateResponse(
        total_conversations=total,
        total_handoffs=handoffs,
        handoff_rate_pct=round(handoffs / total * 100, 1),
        period_days=period_days,
    )


@router.get("/analytics/funnel", response_model=FunnelAnalyticsResponse)
async def get_analytics_funnel(
    period_days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FunnelAnalyticsResponse:
    """Conversational funnel: intent → structured_lookup → handoff/response."""
    cutoff = datetime.utcnow() - timedelta(days=period_days)

    # Count by route from audit_events (pipeline.completed events)
    route_result = await session.execute(
        select(AuditEvent.resource_type, func.count(AuditEvent.id))
        .where(
            AuditEvent.action == "pipeline.completed",
            AuditEvent.created_at >= cutoff,
        )
        .group_by(AuditEvent.resource_type)
    )
    route_rows = route_result.all()
    total = sum(r[1] for r in route_rows) or 1

    # Known route labels
    route_labels = {
        "structured_data_lookup": "Structured Lookup",
        "schedule_flow": "Agendamento",
        "rag_retrieval": "RAG Retrieval",
        "handoff_flow": "Handoff",
        "clarification_flow": "Esclarecimento",
        "response_composer": "Resposta Final",
        "multi_turn": "Multi-turn",
    }
    steps = [
        FunnelStep(
            step=route_labels.get(r[0], r[0]),
            count=r[1],
            percentage=round(r[1] / total * 100, 1),
        )
        for r in route_rows
    ]
    steps.sort(key=lambda x: x.count, reverse=True)
    return FunnelAnalyticsResponse(
        total_conversations=total,
        steps=steps,
        period_days=period_days,
    )


@router.get("/analytics/rag", response_model=RAGAnalyticsResponse)
async def get_rag_analytics(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> RAGAnalyticsResponse:
    """RAG statistics: document count, chunk count, avg chunks/doc, categories."""
    total_docs = (await session.execute(select(func.count(RagDocument.id)))).scalar_one() or 0
    total_chunks = (await session.execute(select(func.count(RagChunk.id)))).scalar_one() or 0
    avg_chunks = round(total_chunks / total_docs, 2) if total_docs > 0 else 0.0

    # Category distribution
    cat_result = await session.execute(
        select(RagDocument.category, func.count(RagDocument.id))
        .group_by(RagDocument.category)
    )
    categories = {r[0] or "uncategorized": r[1] for r in cat_result.all()}

    return RAGAnalyticsResponse(
        total_documents=total_docs,
        total_chunks=total_chunks,
        avg_chunks_per_doc=avg_chunks,
        categories=categories,
        eval_results=None,  # RAG eval requires offline benchmark run; placeholder
    )
