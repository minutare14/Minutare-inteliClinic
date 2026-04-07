"""LlamaIndex vector store backed by Qdrant.

LlamaIndex is the main RAG framework for InteliClinic.
Qdrant is the recommended vector database.

Isolation rule:
    Each clinic deploy has its own Qdrant collection.
    Collection name is derived from clinic_id, preventing any cross-clinic
    data leakage even when running multiple deploys on the same Qdrant instance.

    collection_name = f"inteliclinic_{clinic_id}"

References:
    LlamaIndex: https://github.com/run-llama/llama_index
    Qdrant: https://github.com/qdrant/qdrant
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CLINIC_COLLECTION_PREFIX = "inteliclinic_"


def collection_name_for_clinic(clinic_id: str) -> str:
    """Return the Qdrant collection name for a given clinic deploy."""
    safe_id = clinic_id.lower().replace("-", "_").replace(" ", "_")
    return f"{CLINIC_COLLECTION_PREFIX}{safe_id}"


class LlamaIndexStore:
    """Manages a LlamaIndex VectorStoreIndex backed by Qdrant.

    One instance per clinic deploy. The collection_name guarantees
    complete isolation between clinic deployments.
    """

    def __init__(
        self,
        qdrant_url: str,
        collection_name: str,
        embed_model: str = "text-embedding-3-small",
        vector_size: int = 1536,
    ):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.embed_model = embed_model
        self.vector_size = vector_size
        self._index = None
        self._client = None

    # ------------------------------------------------------------------
    # Client / index lifecycle
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            import qdrant_client

            self._client = qdrant_client.QdrantClient(url=self.qdrant_url)
        return self._client

    def get_index(self):
        """Get or lazily create the LlamaIndex VectorStoreIndex."""
        if self._index is None:
            from llama_index.core import Settings, VectorStoreIndex
            from llama_index.core.storage import StorageContext
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.vector_stores.qdrant import QdrantVectorStore

            client = self._get_client()
            self._ensure_collection(client)

            vector_store = QdrantVectorStore(
                client=client,
                collection_name=self.collection_name,
            )
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # Configure embedding model globally for this index
            Settings.embed_model = OpenAIEmbedding(model=self.embed_model)

            self._index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                storage_context=storage_context,
            )
            logger.info("LlamaIndex index ready — collection: %s", self.collection_name)
        return self._index

    def _ensure_collection(self, client) -> None:
        """Create Qdrant collection if it does not exist."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in client.get_collections().collections}
        if self.collection_name not in existing:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection_name)

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    def add_documents(self, documents: list) -> None:
        """Insert LlamaIndex Document objects into the index."""
        index = self.get_index()
        for doc in documents:
            index.insert(doc)
        logger.info("Inserted %d documents into %s", len(documents), self.collection_name)

    def delete_document(self, doc_id: str) -> None:
        """Remove a document from the index by its ID."""
        index = self.get_index()
        index.delete_ref_doc(doc_id, delete_from_docstore=True)

    def as_query_engine(self, similarity_top_k: int = 5, filters=None):
        """Return a LlamaIndex query engine for this index."""
        index = self.get_index()
        kwargs = {"similarity_top_k": similarity_top_k}
        if filters:
            kwargs["filters"] = filters
        return index.as_query_engine(**kwargs)

    def as_retriever(self, similarity_top_k: int = 5):
        """Return a LlamaIndex retriever for hybrid use."""
        index = self.get_index()
        return index.as_retriever(similarity_top_k=similarity_top_k)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict) -> "LlamaIndexStore":
        """Build store from clinic configuration dict.

        Required keys: qdrant_url, clinic_id
        Optional keys: embed_model, vector_size
        """
        clinic_id = config["clinic_id"]
        return cls(
            qdrant_url=config.get("qdrant_url", "http://localhost:6333"),
            collection_name=collection_name_for_clinic(clinic_id),
            embed_model=config.get("embed_model", "text-embedding-3-small"),
            vector_size=config.get("vector_size", 1536),
        )
