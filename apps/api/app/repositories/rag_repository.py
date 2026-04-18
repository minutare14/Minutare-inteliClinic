from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagDocument


class RagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_document(
        self,
        title: str,
        category: str,
        clinic_id: str,
        source_path: str | None = None,
    ) -> RagDocument:
        doc = RagDocument(
            title=title,
            category=category,
            clinic_id=clinic_id,
            source_path=source_path,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def create_chunk(
        self,
        document_id: uuid.UUID,
        chunk_index: int,
        content: str,
        clinic_id: str,
        embedding: list[float] | None = None,
        *,
        embedded: bool = False,
        embedding_error: str | None = None,
        page: int | None = None,
        metadata_json: str | None = None,
        parent_chunk_id: uuid.UUID | None = None,
        entity_signatures: list[str] | None = None,
    ) -> RagChunk:
        chunk = RagChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            clinic_id=clinic_id,
            embedding=embedding,
            embedded=embedded,
            embedding_error=embedding_error,
            page=page,
            metadata_json=metadata_json,
            parent_chunk_id=parent_chunk_id,
            entity_signatures=entity_signatures,
        )
        self.session.add(chunk)
        await self.session.commit()
        await self.session.refresh(chunk)
        return chunk

    async def search_similar(
        self,
        query_embedding: list[float],
        clinic_id: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """Vector similarity search using pgvector cosine distance."""
        category_filter = ""
        params: dict[str, object] = {
            "embedding": "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]",
            "top_k": top_k,
            "clinic_id": clinic_id,
        }
        if category:
            category_filter = "AND d.category = :category"
            params["category"] = category

        sql = text(
            f"""
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                d.clinic_id,
                c.content,
                d.title AS document_title,
                d.category,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND c.embedded = TRUE
              AND d.status = 'active'
              AND d.clinic_id = :clinic_id
              {category_filter}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """
        )
        result = await self.session.execute(sql, params)
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def text_search(
        self,
        query_text: str,
        clinic_id: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """Keyword-based text search on chunk content."""
        words = [w for w in re.findall(r"\w+", query_text.lower()) if len(w) >= 3]
        if not words:
            return []

        search_terms: list[str] = []
        for word in words:
            if word not in search_terms:
                search_terms.append(word)
            if len(word) >= 5:
                stem = word[:5]
                if stem not in search_terms:
                    search_terms.append(stem)

        word_conditions = " OR ".join(
            f"LOWER(c.content) LIKE :word{i}" for i in range(len(search_terms))
        )
        params: dict[str, object] = {
            f"word{i}": f"%{term}%"
            for i, term in enumerate(search_terms)
        }
        params["top_k"] = top_k
        params["clinic_id"] = clinic_id

        category_filter = ""
        if category:
            category_filter = "AND d.category = :category"
            params["category"] = category

        sql = text(
            f"""
            SELECT
                c.id AS chunk_id,
                d.id AS document_id,
                d.clinic_id,
                c.content,
                d.title AS document_title,
                d.category,
                0.5 AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.status = 'active'
              AND d.clinic_id = :clinic_id
              AND ({word_conditions})
              {category_filter}
            LIMIT :top_k
        """
        )
        result = await self.session.execute(sql, params)
        rows = result.mappings().all()
        return [
            {
                "chunk_id": str(r["chunk_id"]),
                "document_id": str(r["document_id"]),
                "clinic_id": r["clinic_id"],
                "content": r["content"],
                "document_title": r["document_title"],
                "category": r["category"],
                "score": r["score"],
            }
            for r in rows
        ]

    async def has_embeddings(self, clinic_id: str, category: str | None = None) -> bool:
        stmt = (
            select(func.count())
            .select_from(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(
                RagDocument.clinic_id == clinic_id,
                RagDocument.status == "active",
                RagChunk.embedding.is_not(None),
                RagChunk.embedded.is_(True),
            )
        )
        if category:
            stmt = stmt.where(RagDocument.category == category)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def list_documents(self, clinic_id: str, category: str | None = None) -> list[RagDocument]:
        stmt = select(RagDocument).where(RagDocument.clinic_id == clinic_id)
        if category:
            stmt = stmt.where(RagDocument.category == category)
        stmt = stmt.order_by(RagDocument.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, doc_id: uuid.UUID, clinic_id: str) -> RagDocument | None:
        """Returns None if document belongs to a different clinic (isolation check)."""
        doc = await self.session.get(RagDocument, doc_id)
        if doc is None or doc.clinic_id != clinic_id:
            return None
        return doc

    async def get_chunks(self, doc_id: uuid.UUID, clinic_id: str) -> list[RagChunk]:
        """Returns chunks only if the parent document belongs to the given clinic."""
        stmt = (
            select(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(
                RagChunk.document_id == doc_id,
                RagDocument.clinic_id == clinic_id,
            )
            .order_by(RagChunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_chunks_for_reindex(
        self,
        clinic_id: str,
        doc_id: uuid.UUID | None = None,
        *,
        force: bool = False,
    ) -> list[RagChunk]:
        stmt = (
            select(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(RagDocument.clinic_id == clinic_id)
        )
        if doc_id:
            stmt = stmt.where(RagChunk.document_id == doc_id)
        if not force:
            stmt = stmt.where(
                or_(
                    RagChunk.embedding.is_(None),
                    RagChunk.embedded.is_(False),
                )
            )
        stmt = stmt.order_by(RagChunk.document_id, RagChunk.chunk_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_chunks(self, doc_id: uuid.UUID, clinic_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(
                RagChunk.document_id == doc_id,
                RagDocument.clinic_id == clinic_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_document(self, doc_id: uuid.UUID, clinic_id: str) -> bool:
        """
        Delete all chunks then the document.
        Returns True if deleted. Returns False if document does not belong
        to the given clinic (isolation check — does nothing if wrong clinic).
        """
        doc = await self.session.get(RagDocument, doc_id)
        if not doc or doc.clinic_id != clinic_id:
            return False

        chunks = await self.get_chunks(doc_id, clinic_id)
        for chunk in chunks:
            await self.session.delete(chunk)
        await self.session.delete(doc)
        await self.session.commit()
        return True

    async def get_chunks_without_embedding(
        self,
        clinic_id: str,
        doc_id: uuid.UUID | None = None,
    ) -> list[RagChunk]:
        return await self.get_chunks_for_reindex(clinic_id, doc_id, force=False)

    async def update_chunk_indexing(
        self,
        chunk_id: uuid.UUID,
        *,
        embedding: list[float] | None,
        embedded: bool,
        embedding_error: str | None,
    ) -> None:
        chunk = await self.session.get(RagChunk, chunk_id)
        if not chunk:
            return
        chunk.embedding = embedding
        chunk.embedded = embedded
        chunk.embedding_error = embedding_error
        self.session.add(chunk)
        await self.session.commit()

    async def update_chunk_embedding(self, chunk_id: uuid.UUID, embedding: list[float]) -> None:
        await self.update_chunk_indexing(
            chunk_id,
            embedding=embedding,
            embedded=True,
            embedding_error=None,
        )

    async def get_embedding_stats(self, clinic_id: str) -> dict:
        """
        Returns summary stats for the embedding index, scoped to one clinic.
        Used by admin panel to show chunk coverage.
        """
        total_docs_stmt = select(func.count()).select_from(RagDocument).where(
            RagDocument.clinic_id == clinic_id,
            RagDocument.status == "active",
        )
        total_chunks_stmt = (
            select(func.count())
            .select_from(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(RagDocument.clinic_id == clinic_id)
        )
        embedded_stmt = (
            select(func.count())
            .select_from(RagChunk)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(
                RagDocument.clinic_id == clinic_id,
                RagChunk.embedding.is_not(None),
                RagChunk.embedded.is_(True),
            )
        )

        total_docs = (await self.session.execute(total_docs_stmt)).scalar_one()
        total_chunks = (await self.session.execute(total_chunks_stmt)).scalar_one()
        embedded = (await self.session.execute(embedded_stmt)).scalar_one()

        return {
            "clinic_id": clinic_id,
            "documents": total_docs,
            "chunks_total": total_chunks,
            "chunks_with_embedding": embedded,
            "chunks_without_embedding": total_chunks - embedded,
            "coverage_pct": round(embedded / total_chunks * 100, 1) if total_chunks > 0 else 0.0,
        }
