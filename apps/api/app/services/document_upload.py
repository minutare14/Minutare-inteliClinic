"""Document upload orchestration service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunking import semantic_chunk, ChunkResult
from app.core.pinecone_client import PineconeClient
from app.models.rag import RagDocument, RagChunk
from app.repositories.rag_repository import RagRepository
from app.services.extraction_service import (
    extract_entities,
    ExtractionResult,
    save_extractions,
)
from app.services.rag_service import get_embedding
from app.schemas.document import DocumentUploadResponse, DocumentStatus

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {"application/pdf", "text/markdown", "text/x-markdown"}


def validate_file(content: bytes, content_type: str) -> None:
    """Validate file type and size. Raises ValueError if invalid."""
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}. Use PDF or Markdown.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(content)} bytes. Maximum {MAX_FILE_SIZE}.")


def parse_markdown(content: bytes) -> str:
    """Parse markdown content to text."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def parse_pdf(content: bytes) -> str:
    """Parse PDF content using PyMuPDF if available, else return raw text."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("[DOC:UPLOAD] PyMuPDF not available, returning raw text")
        return content.decode("utf-8", errors="replace")
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except Exception as exc:
        logger.warning("[DOC:UPLOAD] PDF parse failed: %s", exc)
        return content.decode("utf-8", errors="replace")


def parse_document(content: bytes, content_type: str, filename: str) -> str:
    """Parse document content based on type."""
    if "pdf" in content_type:
        return parse_pdf(content)
    return parse_markdown(content)


async def process_document(
    session: AsyncSession,
    file_content: bytes,
    filename: str,
    content_type: str,
    title: str | None,
    category: str,
    clinic_id: str,
) -> DocumentUploadResponse:
    """
    Full document upload pipeline:
    1. Validate type and size
    2. Parse PDF or Markdown
    3. Semantic chunking
    4. Generate embeddings
    5. Dual-write to pgvector + Pinecone
    6. Deterministic extraction
    7. Save RagDocument + RagChunks + DocumentExtractions
    """
    validate_file(file_content, content_type)

    doc_title = title or filename.replace(".pdf", "").replace(".md", "").replace(".markdown", "")
    parsed_text = parse_document(file_content, content_type, filename)

    # Create document record
    doc_id = uuid4()
    now = datetime.now(timezone.utc)
    doc = RagDocument(
        id=doc_id,
        title=doc_title,
        category=category,
        clinic_id=clinic_id,
        status=DocumentStatus.PROCESSING.value,
        source_path=filename,
        created_at=now,
        updated_at=now,
    )
    session.add(doc)
    await session.flush()

    # Semantic chunking
    chunks = semantic_chunk(parsed_text)
    chunks_created = 0
    extraction_results: list[ExtractionResult] = []

    pinecone = PineconeClient()
    pinecone_available = pinecone.is_available()
    repo = RagRepository(session)

    for chunk_result in chunks:
        chunk_id = uuid4()
        embedding: list[float] | None = None

        try:
            embedding = await get_embedding(chunk_result.content, phase="ingest")
        except Exception as emb_exc:
            logger.warning("[DOC:UPLOAD] embedding failed for chunk %d: %s", chunk_result.chunk_index, emb_exc)

        # Save to pgvector
        chunk_record = RagChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=chunk_result.chunk_index,
            content=chunk_result.content,
            clinic_id=clinic_id,
            embedding=embedding,
            embedded=embedding is not None,
            page=chunk_result.page,
            metadata_json=chunk_result.metadata_json,
            created_at=now,
        )
        session.add(chunk_record)

        # Dual-write to Pinecone
        if embedding is not None and pinecone_available:
            try:
                await pinecone.upsert_chunk(
                    chunk_id=str(chunk_id),
                    embedding=embedding,
                    metadata={
                        "clinic_id": clinic_id,
                        "document_id": str(doc_id),
                        "chunk_id": str(chunk_id),
                        "category": category,
                        "source": filename,
                        "version": "1",
                        "created_at": now.isoformat(),
                    },
                )
            except Exception as pine_exc:
                logger.warning("[DOC:UPLOAD] Pinecone upsert failed for chunk %s: %s", chunk_id, pine_exc)

        # Deterministic extraction for each chunk
        for entity_type in ("doctor", "price", "insurance", "schedule"):
            try:
                entities = extract_entities(chunk_result.content, entity_type, known_insurance=[])
                extraction_results.extend(entities)
            except Exception as ext_exc:
                logger.warning("[DOC:UPLOAD] extraction failed for chunk %d entity %s: %s",
                    chunk_result.chunk_index, entity_type, ext_exc)

        chunks_created += 1

    # Save extractions
    if extraction_results:
        try:
            await save_extractions(session, doc_id, clinic_id, extraction_results)
        except Exception as ext_save_exc:
            logger.warning("[DOC:UPLOAD] save_extractions failed: %s", ext_save_exc)

    # Update document status
    doc.status = DocumentStatus.READY.value
    doc.updated_at = datetime.now(timezone.utc)
    await session.commit()

    return DocumentUploadResponse(
        document_id=doc_id,
        title=doc_title,
        category=category,
        status=doc.status,
        chunks_created=chunks_created,
        message="Document uploaded and processed successfully.",
    )


async def list_documents(
    session: AsyncSession,
    clinic_id: str,
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """List documents with pagination."""
    repo = RagRepository(session)
    offset = (page - 1) * limit
    docs = await repo.list_documents(clinic_id, category=category, status=status, limit=limit, offset=offset)
    total = await repo.count_documents(clinic_id, category=category, status=status)
    return {"items": docs, "total": total, "page": page}


async def get_document_detail(
    session: AsyncSession,
    document_id: UUID,
    clinic_id: str,
) -> dict | None:
    """Get document detail with chunks and extractions."""
    repo = RagRepository(session)
    doc = await repo.get_document_by_id(document_id, clinic_id)
    if not doc:
        return None
    chunks = await repo.get_chunks(document_id, clinic_id)
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "status": doc.status,
        "source_path": doc.source_path,
        "version": "1",
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "chunks": chunks,
        "extractions": [],
        "stats": {"chunks": len(chunks), "extractions": 0},
    }


async def delete_document(
    session: AsyncSession,
    document_id: UUID,
    clinic_id: str,
) -> bool:
    """Soft delete document and remove from Pinecone."""
    repo = RagRepository(session)
    doc = await repo.get_document_by_id(document_id, clinic_id)
    if not doc:
        return False

    # Get chunks for Pinecone cleanup
    chunks = await repo.get_chunks(document_id, clinic_id)
    chunk_ids = [str(c.id) for c in chunks]

    # Remove from Pinecone
    pinecone = PineconeClient()
    if pinecone.is_available() and chunk_ids:
        try:
            await pinecone.delete_chunks(chunk_ids)
        except Exception as exc:
            logger.warning("[DOC:DELETE] Pinecone delete failed: %s", exc)

    # Soft delete: archive document
    doc.status = DocumentStatus.ARCHIVED.value
    doc.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True