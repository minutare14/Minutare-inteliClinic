from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagDocument


class RagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_document(
        self, title: str, category: str, source_path: str | None = None
    ) -> RagDocument:
        doc = RagDocument(title=title, category=category, source_path=source_path)
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def create_chunk(
        self,
        document_id: uuid.UUID,
        chunk_index: int,
        content: str,
        embedding: list[float] | None = None,
        page: int | None = None,
        metadata_json: str | None = None,
    ) -> RagChunk:
        chunk = RagChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
            page=page,
            metadata_json=metadata_json,
        )
        self.session.add(chunk)
        await self.session.commit()
        await self.session.refresh(chunk)
        return chunk

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """Vector similarity search using pgvector cosine distance."""
        category_filter = ""
        params: dict = {"embedding": str(query_embedding), "top_k": top_k}
        if category:
            category_filter = "AND d.category = :category"
            params["category"] = category

        sql = text(f"""
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                c.content,
                d.title AS document_title,
                d.category,
                1 - (c.embedding <=> :embedding::vector) AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND d.status = 'active'
              {category_filter}
            ORDER BY c.embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.session.execute(sql, params)
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def text_search(
        self,
        query_text: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """Keyword-based text search on chunk content (fallback when no embeddings)."""
        # Extract meaningful words (3+ chars) for ILIKE search
        words = [w for w in query_text.lower().split() if len(w) >= 3]
        if not words:
            return []

        # Build OR conditions for each word
        word_conditions = " OR ".join(
            f"LOWER(c.content) LIKE :word{i}" for i in range(len(words))
        )
        params: dict = {f"word{i}": f"%{w}%" for i, w in enumerate(words)}
        params["top_k"] = top_k

        category_filter = ""
        if category:
            category_filter = "AND d.category = :category"
            params["category"] = category

        sql = text(f"""
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                c.content,
                d.title AS document_title,
                d.category,
                0.5 AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.status = 'active'
              AND ({word_conditions})
              {category_filter}
            LIMIT :top_k
        """)
        result = await self.session.execute(sql, params)
        rows = result.mappings().all()
        return [
            {
                "chunk_id": str(r["chunk_id"]),
                "document_id": str(r["document_id"]),
                "content": r["content"],
                "document_title": r["document_title"],
                "category": r["category"],
                "score": r["score"],
            }
            for r in rows
        ]

    async def list_documents(self, category: str | None = None) -> list[RagDocument]:
        stmt = select(RagDocument)
        if category:
            stmt = stmt.where(RagDocument.category == category)
        stmt = stmt.order_by(RagDocument.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, doc_id: uuid.UUID) -> RagDocument | None:
        return await self.session.get(RagDocument, doc_id)

    async def get_chunks(self, doc_id: uuid.UUID) -> list[RagChunk]:
        stmt = (
            select(RagChunk)
            .where(RagChunk.document_id == doc_id)
            .order_by(RagChunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_chunks(self, doc_id: uuid.UUID) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(RagChunk).where(RagChunk.document_id == doc_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        """Delete all chunks then the document. Returns True if deleted."""
        doc = await self.get_document(doc_id)
        if not doc:
            return False
        # Delete chunks first (no cascade in SQLModel by default)
        chunks = await self.get_chunks(doc_id)
        for chunk in chunks:
            await self.session.delete(chunk)
        await self.session.delete(doc)
        await self.session.commit()
        return True
