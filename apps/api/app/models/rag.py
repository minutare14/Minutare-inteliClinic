from __future__ import annotations

import os
import uuid
from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # allow import without pgvector installed

# Lido do ambiente para sincronizar com a migration de Alembic.
# Valores por provider:
#   local/fastembed → 384 (padrão, gratuito)
#   gemini          → 768
#   openai          → 1536
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))


class RagDocument(SQLModel, table=True):
    __tablename__ = "rag_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
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
    chunk_index: int = Field(default=0)
    content: str = Field(sa_column=Column(Text, nullable=False))
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIM)) if Vector else Column(Text),
    )
    page: int | None = None
    metadata_json: str | None = None  # JSON string for extra metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
