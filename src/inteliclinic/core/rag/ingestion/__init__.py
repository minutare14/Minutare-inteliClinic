"""Ingestion pipeline — transforms raw documents into indexed, queryable knowledge.

Stages:
    1. Parse    — Docling (PDF, DOCX, PPTX) or MarkdownParser (.md, .txt)
    2. Clean    — strip boilerplate, normalize whitespace, fix encoding
    3. Chunk    — token-aware or semantic splitting
    4. Embed    — OpenAI / local embedding model
    5. Store    — Qdrant vector store under clinic-scoped collection

Each clinic triggers ingestion when its knowledge base is updated.
Re-ingestion is idempotent: existing doc IDs are overwritten, not duplicated.
"""

from .parsers import BaseParser, DoclingParser
from .chunking import TextChunker
from .pipelines.ingest_pipeline import IngestPipeline, IngestResult

__all__ = [
    "BaseParser",
    "DoclingParser",
    "TextChunker",
    "IngestPipeline",
    "IngestResult",
]
