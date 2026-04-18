from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import Boolean, Column, JSON, Text
from sqlmodel import Field, SQLModel

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # allow import without pgvector installed

# Read from env to stay aligned with the Alembic vector dimension.
# Provider dimensions:
#   local/sentence-transformers -> 384 (default)
#   gemini                      -> 768
#   openai                      -> 1536
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))


class RagDocument(SQLModel, table=True):
    __tablename__ = "rag_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    title: str = Field(max_length=512)
    category: str = Field(default="general", max_length=64)
    source_path: str | None = Field(default=None, max_length=1024)
    version: str = Field(default="1.0", max_length=20)
    status: str = Field(default="active", max_length=20)  # active | archived
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RagChunk(SQLModel, table=True):
    __tablename__ = "rag_chunks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="rag_documents.id", index=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)  # denormalized from RagDocument for fast filtering
    chunk_index: int = Field(default=0)
    content: str = Field(sa_column=Column(Text, nullable=False))
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIM)) if Vector else Column(JSON),
    )
    embedded: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    embedding_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    parent_chunk_id: uuid.UUID | None = Field(default=None, index=True)
    entity_signatures: list[str] | None = Field(default=None)
    page: int | None = None
    metadata_json: str | None = None  # JSON string for extra metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
