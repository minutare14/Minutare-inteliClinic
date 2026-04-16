"""Add google_calendar_token to clinic_settings

Revision ID: 010
Revises: 009
Create Date: 2026-04-16

Adds:
  - clinic_settings.google_calendar_token — JSON-encoded OAuth2 tokens
    for the Google Calendar integration. NULL = not connected.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clinic_settings",
        sa.Column("google_calendar_token", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clinic_settings", "google_calendar_token")
