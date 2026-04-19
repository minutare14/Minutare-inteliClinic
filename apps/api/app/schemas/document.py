from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    CONVENIO = "convenio"
    PROTOCOLO = "protocolo"
    FAQ = "faq"
    MANUAL = "manual"
    TABELA = "tabela"
    OUTRO = "outro"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    ARCHIVED = "archived"


class DocumentUploadRequest(BaseModel):
    title: str | None = None
    category: DocumentCategory = DocumentCategory.OUTRO


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    category: str
    status: str
    chunks_created: int = 0
    message: str


class ChunkInfo(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    page: int | None = None
    metadata_json: str | None = None


class ExtractionItem(BaseModel):
    id: UUID
    entity_type: str
    extracted_data: dict[str, Any]
    raw_text: str | None
    extraction_method: str
    confidence: float
    requires_review: bool
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    published_to: str | None
    published_entity_id: UUID | None
    superseded_by: UUID | None
    source_extraction_id: UUID | None
    created_at: datetime


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    category: str
    status: str
    chunks_count: int
    extractions_count: int
    approved_count: int
    rejected_count: int
    created_at: datetime


class DocumentDetail(BaseModel):
    id: UUID
    title: str
    category: str
    status: str
    source_path: str | None
    version: str
    created_at: datetime
    updated_at: datetime
    chunks: list[ChunkInfo]
    extractions: list[ExtractionItem]
    stats: dict


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int


class ExtractionApproveRequest(BaseModel):
    notes: str | None = None


class ExtractionRejectRequest(BaseModel):
    reason: str


class ExtractionReviseRequest(BaseModel):
    corrected_data: dict[str, Any]
