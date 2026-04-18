"""Add prompt_type column to prompt_registry for per-layer prompt governance.

Revision ID: 012
Revises: 011
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels: tuple[str, ...] = ()
depends_on: tuple[str, ...] = ()


def upgrade() -> None:
    # Add prompt_type column (nullable initially, then populate default, then enforce NOT NULL)
    op.add_column(
        "prompt_registry",
        sa.Column("prompt_type", sa.String(64), nullable=True, index=True),
    )
    # Set default value for existing rows so they can be backfilled
    op.execute(
        "UPDATE prompt_registry SET prompt_type = agent WHERE prompt_type IS NULL"
    )
    # Make NOT NULL after backfill
    op.alter_column("prompt_registry", "prompt_type", nullable=False)
    # Unique constraint: only one active version per clinic_id + prompt_type
    op.create_index(
        "ix_prompt_registry_clinic_prompt_active",
        "prompt_registry",
        ["clinic_id", "prompt_type", "active"],
        unique=False,
        postgresql_where=sa.text("active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_registry_clinic_prompt_active", table_name="prompt_registry")
    op.drop_column("prompt_registry", "prompt_type")
