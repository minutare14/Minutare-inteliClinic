"""RAG module — LlamaIndex as main framework, Qdrant as vector store, Docling for document parsing.

Architecture:
    Documents (PDF, DOCX, MD)
        → Docling Parser
        → Chunking
        → LlamaIndex Ingestion
        → Qdrant Vector Store

    Query
        → LlamaIndex Query Engine
        → Hybrid Retrieval (dense + sparse)
        → Reranking (future)
        → Response

Note: The RAG engine is GLOBAL (core).
      The indexed knowledge base is LOCAL to each clinic deploy.
      Each clinic has its own Qdrant collection or index namespace.
"""

from .ingestion.parsers import BaseParser, DoclingParser
from .ingestion.chunking import TextChunker
from .indexes import LlamaIndexStore
from .query import QueryEngine
from .stores.qdrant_store import QdrantStore, collection_name_for_clinic

__all__ = [
    "BaseParser",
    "DoclingParser",
    "TextChunker",
    "LlamaIndexStore",
    "QueryEngine",
    "QdrantStore",
    "collection_name_for_clinic",
]
