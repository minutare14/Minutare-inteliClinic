"""Qdrant vector store — thin client wrapper for InteliClinic.

Each clinic deploy uses its own collection, ensuring data isolation
even when multiple clinics share the same Qdrant instance.

Collection naming convention:
    inteliclinic_{clinic_id}

References:
    Qdrant: https://github.com/qdrant/qdrant
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CLINIC_COLLECTION_PREFIX = "inteliclinic_"


def collection_name_for_clinic(clinic_id: str) -> str:
    """Return the canonical Qdrant collection name for a clinic deploy."""
    safe = clinic_id.lower().replace("-", "_").replace(" ", "_")
    return f"{CLINIC_COLLECTION_PREFIX}{safe}"


class QdrantStore:
    """Low-level Qdrant operations for InteliClinic.

    Prefer using LlamaIndexStore (which wraps this) for most RAG operations.
    Use QdrantStore directly only for administrative tasks:
    - Collection management
    - Bulk upserts
    - Direct vector search (bypassing LlamaIndex)
    """

    def __init__(self, url: str, collection_name: str, vector_size: int = 1536):
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._client = None

    def _get_client(self):
        if self._client is None:
            import qdrant_client

            self._client = qdrant_client.QdrantClient(url=self.url)
        return self._client

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(self, recreate: bool = False) -> None:
        """Create the Qdrant collection for this clinic."""
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()
        existing = {c.name for c in client.get_collections().collections}

        if self.collection_name in existing:
            if recreate:
                client.delete_collection(self.collection_name)
                logger.warning("Deleted existing collection: %s", self.collection_name)
            else:
                logger.info("Collection already exists: %s", self.collection_name)
                return

        client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        logger.info("Created collection: %s", self.collection_name)

    def delete_collection(self) -> None:
        """Delete the clinic's collection. Irreversible — use with care."""
        client = self._get_client()
        client.delete_collection(self.collection_name)
        logger.warning("Deleted collection: %s", self.collection_name)

    def collection_info(self) -> dict[str, Any]:
        """Return collection stats: points count, vector size, status."""
        client = self._get_client()
        info = client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "vector_size": self.vector_size,
            "status": str(info.status),
        }

    # ------------------------------------------------------------------
    # Vector operations
    # ------------------------------------------------------------------

    def upsert_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        """Bulk upsert vectors with payloads into the collection."""
        from qdrant_client.models import PointStruct

        client = self._get_client()
        points = [
            PointStruct(id=id_, vector=vec, payload=payload)
            for id_, vec, payload in zip(ids, vectors, payloads)
        ]
        client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Upserted %d vectors into %s", len(points), self.collection_name)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """Direct vector similarity search."""
        from qdrant_client.models import Filter

        client = self._get_client()
        q_filter = None
        if filter_payload:
            from qdrant_client.models import FieldCondition, MatchValue

            q_filter = Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_payload.items()
                ]
            )

        hits = client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=q_filter,
            with_payload=True,
        )
        return [
            {"id": h.id, "score": h.score, "payload": h.payload}
            for h in hits
        ]

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_clinic(cls, clinic_id: str, url: str, vector_size: int = 1536) -> "QdrantStore":
        """Create a QdrantStore for a specific clinic deploy."""
        return cls(
            url=url,
            collection_name=collection_name_for_clinic(clinic_id),
            vector_size=vector_size,
        )
