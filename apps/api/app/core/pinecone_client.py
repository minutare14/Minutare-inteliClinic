"""Pinecone vector store client — dual-writes with pgvector."""
from __future__ import annotations

import logging
from typing import Any

from pinecone import Pinecone

from app.core.config import settings

logger = logging.getLogger(__name__)


class PineconeClient:
    """Pinecone vector store client — dual-writes with pgvector."""

    def __init__(self) -> None:
        self._client: Any = None
        self._index: Any = None

    @property
    def index_name(self) -> str:
        return settings.pinecone_index

    @property
    def namespace(self) -> str:
        return settings.clinic_id

    def _get_client(self) -> Pinecone:
        """Lazily initialize the Pinecone client."""
        if self._client is None:
            self._client = Pinecone(api_key=settings.pinecone_api_key)
        return self._client

    def _get_index(self) -> Any:
        """Lazily get the index reference."""
        if self._index is None:
            client = self._get_client()
            self._index = client.Index(self.index_name)
        return self._index

    async def ensure_index(self) -> None:
        """Create index if it doesn't exist (idempotent)."""
        client = self._get_client()
        try:
            client.describe_index(self.index_name)
            logger.info("Pinecone index '%s' already exists", self.index_name)
        except Exception:
            logger.info("Creating Pinecone index '%s' (dimension=384, metric=cosine)", self.index_name)
            client.create_index(
                name=self.index_name,
                dimension=384,
                metric="cosine",
                cloud=settings.pinecone_cloud or None,
                region=settings.pinecone_region or None,
            )

    async def upsert_chunk(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """Upsert a single chunk vector to Pinecone."""
        index = self._get_index()
        index.upsert(
            vectors=[{
                "id": chunk_id,
                "values": embedding,
                "metadata": metadata,
            }],
            namespace=self.namespace,
        )

    async def upsert_chunks(self, vectors: list[dict]) -> None:
        """Upsert multiple chunk vectors (batch)."""
        index = self._get_index()
        index.upsert(
            vectors=[{
                "id": v["id"],
                "values": v["values"],
                "metadata": v["metadata"],
            } for v in vectors],
            namespace=self.namespace,
        )

    async def query(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        filter_dict: dict | None = None,
    ) -> list[dict]:
        """Query Pinecone for similar vectors."""
        index = self._get_index()
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=self.namespace,
            filter=filter_dict,
        )
        return [
            {
                "id": r["id"],
                "score": r["score"],
                "metadata": r["metadata"],
            }
            for r in results["matches"]
        ]

    async def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete specific vectors by chunk_id (NOT delete_all)."""
        index = self._get_index()
        index.delete(
            ids=chunk_ids,
            namespace=self.namespace,
            delete_all=False,
        )

    def is_available(self) -> bool:
        """True if Pinecone is configured and reachable."""
        return bool(settings.pinecone_api_key and settings.pinecone_api_key != "")