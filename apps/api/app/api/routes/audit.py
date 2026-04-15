from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventRead
from app.schemas.pipeline import PipelineTrace, PipelineStep

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventRead]:
    repo = AuditRepository(session)
    events = await repo.list_events(limit=limit, offset=offset)
    return [AuditEventRead.model_validate(e) for e in events]


@router.get("/resource/{resource_type}/{resource_id}", response_model=list[AuditEventRead])
async def list_audit_events_by_resource(
    resource_type: str,
    resource_id: str,
    action: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventRead]:
    repo = AuditRepository(session)
    events = await repo.list_by_resource(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return [AuditEventRead.model_validate(e) for e in events]


@router.get("/pipeline/{conversation_id}", response_model=list[PipelineTrace])
async def get_pipeline_trace(
    conversation_id: str,
    limit: int = Query(20, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[PipelineTrace]:
    repo = AuditRepository(session)
    events = await repo.list_by_resource(
        resource_type="conversation",
        resource_id=conversation_id,
        action="pipeline.completed",
        limit=limit,
    )
    
    traces = []
    for event in events:
        try:
            payload = json.loads(event.payload) if event.payload else {}
            
            # Reconstruct steps from payload
            steps = []
            
            # Step 1: Intent
            steps.append(PipelineStep(
                name="analyze_intent",
                status="completed",
                payload={
                    "intent": payload.get("intent"),
                    "confidence": payload.get("confidence"),
                    "entities": payload.get("entities")
                }
            ))
            
            # Step 2: Guardrails Pre
            steps.append(PipelineStep(
                name="policy_guardrails_pre",
                status="completed",
                payload={"action": payload.get("guardrail_pre")}
            ))
            
            # Step 3: Tooling
            tool_name = payload.get("tool_used") or payload.get("route")
            steps.append(PipelineStep(
                name="decision_router",
                status="completed",
                payload={
                    "route": payload.get("route"),
                    "tool_used": payload.get("tool_used"),
                    "source_of_truth": payload.get("source_of_truth")
                }
            ))
            
            # Step 4: Guardrails Post
            steps.append(PipelineStep(
                name="policy_guardrails_post",
                status="completed",
                payload={"action": payload.get("guardrail_post")}
            ))
            
            traces.append(PipelineTrace(
                conversation_id=conversation_id,
                steps=steps,
                created_at=event.created_at.isoformat()
            ))
        except Exception:
            continue
            
    return traces
