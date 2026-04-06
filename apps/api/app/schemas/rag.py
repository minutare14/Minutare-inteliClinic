from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RagDocumentRead(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    source_path: str | None
    version: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RagIngestRequest(BaseModel):
    title: str
    category: str = "general"
    content: str
    source_path: str | None = None


class RagIngestResponse(BaseModel):
    document_id: uuid.UUID
    chunks_created: int


class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    category: str | None = None


class RagQueryResult(BaseModel):
    chunk_id: uuid.UUID
    content: str
    score: float
    document_title: str
    category: str
