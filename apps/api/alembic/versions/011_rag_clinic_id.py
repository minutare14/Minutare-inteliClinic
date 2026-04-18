"""Add clinic_id to rag_documents and rag_chunks for multi-tenant isolation.

Revision ID: 011
Revises: 009
Create Date: 2026-04-18

This migration adds a clinic_id column to both RAG tables to enforce
tenant isolation at the database level.

IMPORTANT: After running this migration, existing documents will belong
to "clinic01" (the default). If your deployment serves multiple clinics
with data already in the database, you must backfill the correct clinic_id
for each document before this migration is safe to run in production.

The clinic_id column is added as NOT NULL with a default to avoid the
need for a multi-step migration. All existing rows are backfilled with
"clinic01" (the value of settings.clinic_id at the time of migration).

Downgrade note: downgrade does NOT restore the original data — this is a
one-way migration for simplicity. In a real multi-tenant deployment, a
proper data migration plan is required before applying this migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CLINIC_ID = "clinic01"


def upgrade() -> None:
    # ── rag_documents ──────────────────────────────────────────────────────────
    # Add nullable first, backfill all existing rows, then make NOT NULL.
    # Adding directly as NOT NULL with server_default would require all existing
    # rows to have a value at constraint-creation time, which is not guaranteed.
    op.add_column(
        "rag_documents",
        sa.Column("clinic_id", sa.String(length=64), nullable=True),
    )
    # Backfill all existing documents to the default clinic (single-tenant default)
    op.execute(
        f"UPDATE rag_documents SET clinic_id = '{DEFAULT_CLINIC_ID}' WHERE clinic_id IS NULL"
    )
    # Now make it NOT NULL and add the default + index
    op.alter_column("rag_documents", "clinic_id", nullable=False, server_default=DEFAULT_CLINIC_ID)
    op.create_index("ix_rag_documents_clinic_id", "rag_documents", ["clinic_id"])

    # ── rag_chunks ─────────────────────────────────────────────────────────────
    op.add_column(
        "rag_chunks",
        sa.Column("clinic_id", sa.String(length=64), nullable=True),
    )
    # Backfill from the parent document via JOIN so each chunk inherits its doc's clinic
    op.execute(
        f"""
        UPDATE rag_chunks
        SET clinic_id = d.clinic_id
        FROM rag_documents d
        WHERE d.id = rag_chunks.document_id
          AND rag_chunks.clinic_id IS NULL
        """
    )
    # Any chunks whose document was already deleted (orphan chunks) get the default
    op.execute(
        f"UPDATE rag_chunks SET clinic_id = '{DEFAULT_CLINIC_ID}' WHERE clinic_id IS NULL"
    )
    op.alter_column("rag_chunks", "clinic_id", nullable=False, server_default=DEFAULT_CLINIC_ID)
    op.create_index("ix_rag_chunks_clinic_id", "rag_chunks", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_clinic_id", table_name="rag_chunks")
    op.drop_column("rag_chunks", "clinic_id")
    op.drop_index("ix_rag_documents_clinic_id", table_name="rag_documents")
    op.drop_column("rag_documents", "clinic_id")
