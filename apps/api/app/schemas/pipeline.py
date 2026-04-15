from __future__ import annotations
from pydantic import BaseModel
from typing import Any

class PipelineStep(BaseModel):
    name: str
    status: str  # active, completed, skipped, failed
    payload: dict[str, Any] | None = None

class PipelineTrace(BaseModel):
    conversation_id: str
    steps: list[PipelineStep]
    created_at: str
