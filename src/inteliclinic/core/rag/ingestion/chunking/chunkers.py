"""Text chunking strategies for RAG ingestion.

Provides fixed-size and semantic chunkers for splitting documents
before embedding and indexing into the vector store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..parsers.base_parser import ParsedDocument


@dataclass
class Chunk:
    """A single text chunk ready for embedding."""

    text: str
    metadata: dict
    index: int
    total_chunks: int
    char_start: int = 0
    char_end: int = 0


class TextChunker:
    """Fixed-size text chunker with character overlap.

    Splits on sentence boundaries when possible to avoid mid-sentence cuts.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        """Split text into overlapping chunks."""
        meta = metadata or {}
        if not text.strip():
            return []

        pieces: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                pieces.append(text[start:])
                break
            # Try to cut at sentence boundary
            cut = text.rfind(".", start, end)
            if cut == -1 or cut - start < self.min_chunk_size:
                cut = end
            else:
                cut += 1  # include the period
            pieces.append(text[start:cut].strip())
            start = cut - self.chunk_overlap

        chunks = [
            Chunk(
                text=p,
                metadata={**meta, "chunk_strategy": "fixed_size"},
                index=i,
                total_chunks=len(pieces),
                char_start=0,
                char_end=len(p),
            )
            for i, p in enumerate(pieces)
            if len(p) >= self.min_chunk_size
        ]
        return chunks

    def chunk_document(self, doc: "ParsedDocument") -> list[Chunk]:
        """Chunk a ParsedDocument, preserving document metadata."""
        base_meta = {
            "source": doc.source_path,
            "title": doc.title,
            "doc_type": doc.doc_type,
            **doc.metadata,
        }
        return self.chunk(doc.content, base_meta)


class SemanticChunker:
    """Semantic chunker that respects paragraph and section boundaries.

    Preferred over fixed-size chunking for medical documents where context
    within a paragraph is critical (e.g., TISS tables, protocols).
    """

    def __init__(self, max_chunk_size: int = 800, min_chunk_size: int = 150):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        """Split by semantic boundaries: sections (##) and paragraphs (blank lines)."""
        meta = metadata or {}
        # Split on section headers or double newlines
        import re

        raw_blocks = re.split(r"\n{2,}|(?=^#{1,3} )", text, flags=re.MULTILINE)
        blocks = [b.strip() for b in raw_blocks if b.strip()]

        # Merge small blocks and split oversized ones
        merged: list[str] = []
        buffer = ""
        for block in blocks:
            if len(buffer) + len(block) < self.max_chunk_size:
                buffer = (buffer + "\n\n" + block).strip()
            else:
                if buffer:
                    merged.append(buffer)
                # If block itself is too large, hard split
                if len(block) > self.max_chunk_size:
                    for i in range(0, len(block), self.max_chunk_size):
                        part = block[i : i + self.max_chunk_size].strip()
                        if part:
                            merged.append(part)
                    buffer = ""
                else:
                    buffer = block

        if buffer:
            merged.append(buffer)

        chunks = [
            Chunk(
                text=p,
                metadata={**meta, "chunk_strategy": "semantic"},
                index=i,
                total_chunks=len(merged),
            )
            for i, p in enumerate(merged)
            if len(p) >= self.min_chunk_size
        ]
        return chunks

    def chunk_document(self, doc: "ParsedDocument") -> list[Chunk]:
        base_meta = {
            "source": doc.source_path,
            "title": doc.title,
            "doc_type": doc.doc_type,
            **doc.metadata,
        }
        return self.chunk(doc.content, base_meta)
