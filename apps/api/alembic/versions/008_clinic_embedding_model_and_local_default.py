"""Persist embedding_model in clinic_settings and default provider to local.

Revision ID: 008
Revises: 007
Create Date: 2026-04-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def upgrade() -> None:
    op.add_column(
        "clinic_settings",
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
    )

    op.execute(
        """
        UPDATE clinic_settings
        SET embedding_provider = CASE
            WHEN embedding_provider IS NULL OR btrim(embedding_provider) = '' THEN 'local'
            WHEN lower(btrim(embedding_provider)) IN ('groq', 'openai') THEN 'local'
            ELSE lower(btrim(embedding_provider))
        END
        """
    )
    op.execute(
        f"""
        UPDATE clinic_settings
        SET embedding_model = CASE
            WHEN embedding_model IS NOT NULL AND btrim(embedding_model) <> '' THEN embedding_model
            WHEN lower(coalesce(embedding_provider, 'local')) = 'openai' THEN 'text-embedding-3-small'
            WHEN lower(coalesce(embedding_provider, 'local')) = 'gemini' THEN 'text-embedding-004'
            ELSE '{DEFAULT_LOCAL_MODEL}'
        END
        """
    )

    op.alter_column(
        "clinic_settings",
        "embedding_provider",
        existing_type=sa.String(length=64),
        server_default="local",
    )
    op.alter_column(
        "clinic_settings",
        "embedding_model",
        existing_type=sa.String(length=255),
        nullable=True,
        server_default=DEFAULT_LOCAL_MODEL,
    )


def downgrade() -> None:
    op.alter_column(
        "clinic_settings",
        "embedding_provider",
        existing_type=sa.String(length=64),
        server_default="openai",
    )
    op.drop_column("clinic_settings", "embedding_model")
