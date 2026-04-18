"""Add parent_chunk_id and entity_signatures to rag_chunks for GraphRAG.

Revision ID: 013
Revises: 012
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels: tuple[str, ...] = ()
depends_on: tuple[str, ...] = ()


def upgrade() -> None:
    # parent_chunk_id: links to previous chunk in same document (enables sibling graph traversal)
    op.add_column(
        "rag_chunks",
        sa.Column("parent_chunk_id", sa.UUID(), nullable=True, index=True),
    )
    op.create_foreign_key(
        "fk_rag_chunks_parent",
        "rag_chunks", "rag_chunks",
        ["parent_chunk_id"], ["id"],
        ondelete="SET NULL",
    )

    # entity_signatures: JSON array of entity mentions for GraphRAG traversal
    # e.g. ["Dr. Carlos", "Cardiologia", "Consulta"] — enables filtering by entity
    # NOTE: no index on entity_signatures JSON column — btree requires an operator
    # class which JSON doesn't have. The column can be filtered with a seq scan
    # or GIN index later if performance requires it.
    op.add_column(
        "rag_chunks",
        sa.Column("entity_signatures", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rag_chunks", "entity_signatures")
    op.drop_column("rag_chunks", "parent_chunk_id")
    op.drop_constraint("fk_rag_chunks_parent", table_name="rag_chunks", type_="foreignkey", if_exists=True)
