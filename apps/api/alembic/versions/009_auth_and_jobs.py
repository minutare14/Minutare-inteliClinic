"""Auth users + Jobs tables (follow_ups, alerts)

Revision ID: 009
Revises: 008
Create Date: 2026-04-16

Adds:
  - users         — clinic staff with role-based access (admin/manager/reception/handoff_operator)
  - follow_ups    — scheduled follow-up tasks (post-appointment, lead nurture, reminders)
  - alerts        — operational alerts requiring human attention
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="reception"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── follow_ups ────────────────────────────────────────────────────────────
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("followup_type", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_follow_ups_patient_id", "follow_ups", ["patient_id"])
    op.create_index("ix_follow_ups_scheduled_at", "follow_ups", ["scheduled_at"])
    op.create_index(
        "ix_follow_ups_pending",
        "follow_ups",
        ["scheduled_at", "completed"],
    )

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True, index=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("alert_type", sa.String(64), nullable=False, server_default="general"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_patient_id", "alerts", ["patient_id"])
    op.create_index("ix_alerts_open", "alerts", ["resolved", "created_at"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("follow_ups")
    op.drop_table("users")
