"""GraphRAG — Phase 2 knowledge graph for complex relational queries.

STATUS: Not active in Phase 1. Interface defined for future implementation.

When to use GraphRAG vs Vector RAG
------------------------------------
Vector RAG (Phase 1 — active):
    Best for: semantic similarity, FAQ answers, protocol descriptions,
    administrative documents, free-text patient questions.

GraphRAG (Phase 2 — planned):
    Best for: complex relational queries spanning multiple entities.

    Examples where GraphRAG outperforms vector RAG:
    - "Quais convênios cobrem procedimentos de ortopedia realizados pelo Dr. Silva?"
    - "Quais protocolos se aplicam quando o paciente tem plano X e condição Y?"
    - "Qual é a relação entre o código TUSS 40301167 e os convênios que autorizam?"
    - "Detectar padrões de glosa entre procedimentos similares de múltiplos médicos"

Implementation Plan (Phase 2):
    Repository: microsoft/graphrag — https://github.com/microsoft/graphrag
    Graph store: Neo4j or Amazon Neptune
    Entities: Procedure, Professional, Insurance, Protocol, CID, TUSS
    Relations: COVERS, AUTHORIZES, APPLIES_TO, PERFORMED_BY, REQUIRES

    GraphRAG will complement (not replace) vector RAG.
    A router will decide which retrieval method to use based on query type.
"""

from .interface import GraphRAGInterface, NotImplementedGraphRAG

__all__ = ["GraphRAGInterface", "NotImplementedGraphRAG"]
