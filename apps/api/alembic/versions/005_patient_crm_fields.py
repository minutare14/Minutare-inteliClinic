"""Add CRM fields to patients (tags, crm_notes, stage, source)

Revision ID: 005
Revises: 004
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("tags", sa.String(512)))
    op.add_column("patients", sa.Column("crm_notes", sa.Text()))
    op.add_column("patients", sa.Column("stage", sa.String(32), server_default="lead"))
    op.add_column("patients", sa.Column("source", sa.String(64)))


def downgrade() -> None:
    op.drop_column("patients", "source")
    op.drop_column("patients", "stage")
    op.drop_column("patients", "crm_notes")
    op.drop_column("patients", "tags")
