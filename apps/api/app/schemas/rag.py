from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RagDocumentRead(BaseModel):
    id: uuid.UUID
    clinic_id: str
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
    chunks_embedded: int
    chunks_failed: int
    embedding_provider: str
    embedding_model: str


class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    category: str | None = None


class RagQueryResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    content: str
    score: float
    document_title: str  # kept for internal use (orchestrator)
    category: str


class RagChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page: int | None
    created_at: datetime
    embedded: bool = False
    embedding_error: str | None = None
    has_embedding: bool = False

    model_config = {"from_attributes": True}
