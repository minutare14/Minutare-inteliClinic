"""Add explicit embedding status fields to rag_chunks.

Revision ID: 007
Revises: 006
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rag_chunks",
        sa.Column("embedded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "rag_chunks",
        sa.Column("embedding_error", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE rag_chunks
        SET embedded = CASE
            WHEN embedding IS NOT NULL THEN TRUE
            ELSE FALSE
        END
        """
    )
    op.alter_column("rag_chunks", "embedded", server_default=None)


def downgrade() -> None:
    op.drop_column("rag_chunks", "embedding_error")
    op.drop_column("rag_chunks", "embedded")
