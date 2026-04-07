"""GraphRAG interface contract — implemented in Phase 2.

All Phase 2 implementations must inherit from GraphRAGInterface.
Phase 1 code uses NotImplementedGraphRAG as a placeholder.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class GraphRAGInterface(ABC):
    """Abstract interface for knowledge graph retrieval.

    Concrete implementations:
    - Phase 2: MicrosoftGraphRAG (wraps microsoft/graphrag)
    - Testing:  InMemoryGraphRAG
    """

    @abstractmethod
    async def build_graph(self, documents: list) -> None:
        """Extract entities and relations from documents and build the graph.

        Args:
            documents: List of ParsedDocument or LlamaIndex Document objects.
        """
        ...

    @abstractmethod
    async def query(
        self,
        question: str,
        entities: list[str] | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        """Query the knowledge graph.

        Args:
            question: Natural language question.
            entities: Known entities to anchor the query (e.g. insurance name, CID).
            max_hops: Graph traversal depth.

        Returns:
            List of relevant subgraph contexts with content and metadata.
        """
        ...

    @abstractmethod
    async def get_entity_relations(self, entity: str) -> dict:
        """Return all known relations for a given entity.

        Args:
            entity: Entity name or ID (e.g. "Unimed Nacional", "40301167").

        Returns:
            Dict with entity details and its relations.
        """
        ...

    @abstractmethod
    async def list_entities(self, entity_type: str | None = None) -> list[dict]:
        """List all entities in the graph, optionally filtered by type."""
        ...


class NotImplementedGraphRAG(GraphRAGInterface):
    """Placeholder used in Phase 1 when GraphRAG is not yet active.

    Raises NotImplementedError with a helpful message pointing to Phase 2 docs.
    """

    PHASE2_MESSAGE = (
        "GraphRAG is not yet implemented (Phase 2). "
        "See docs/architecture/core-vs-clinic.md for the implementation roadmap. "
        "Use ClinicQueryEngine (vector RAG) for current queries."
    )

    async def build_graph(self, documents: list) -> None:
        raise NotImplementedError(self.PHASE2_MESSAGE)

    async def query(
        self,
        question: str,
        entities: list[str] | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        raise NotImplementedError(self.PHASE2_MESSAGE)

    async def get_entity_relations(self, entity: str) -> dict:
        raise NotImplementedError(self.PHASE2_MESSAGE)

    async def list_entities(self, entity_type: str | None = None) -> list[dict]:
        raise NotImplementedError(self.PHASE2_MESSAGE)
