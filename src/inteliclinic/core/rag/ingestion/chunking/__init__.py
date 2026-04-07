"""Text chunking strategies for RAG ingestion.

Available chunkers:
    - TextChunker     : Token-aware fixed-size chunking with overlap (fast, default)
    - SemanticChunker : Paragraph/section-boundary chunking (preferred for medical docs)

Chunking strategy choice:
    - FAQs, short docs          → TextChunker (chunk_size=256)
    - Protocols, TISS/TUSS docs → SemanticChunker (respects section boundaries)
    - Long insurance PDFs       → TextChunker (chunk_size=512, overlap=64)

Both chunkers preserve document metadata in every Chunk for traceability.
"""

from .chunkers import Chunk, TextChunker, SemanticChunker

__all__ = [
    "Chunk",
    "TextChunker",
    "SemanticChunker",
]
