"""Admin domain — clinic_settings, insurance_catalog, prompt_registry

Revision ID: 003
Revises: 002
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- clinic_settings ---
    op.create_table(
        "clinic_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, server_default="Clínica"),
        sa.Column("short_name", sa.String(64)),
        sa.Column("chatbot_name", sa.String(128), server_default="Assistente"),
        sa.Column("cnpj", sa.String(18)),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("website", sa.String(512)),
        sa.Column("address", sa.String(512)),
        sa.Column("city", sa.String(128)),
        sa.Column("state", sa.String(2)),
        sa.Column("zip_code", sa.String(9)),
        sa.Column("working_hours", sa.String(512)),
        sa.Column("emergency_phone", sa.String(20)),
        sa.Column("logo_url", sa.String(1024)),
        sa.Column("primary_color", sa.String(16), server_default="#2563eb"),
        sa.Column("secondary_color", sa.String(16), server_default="#64748b"),
        sa.Column("accent_color", sa.String(16)),
        sa.Column("ai_provider", sa.String(64)),
        sa.Column("ai_model", sa.String(128)),
        sa.Column("embedding_provider", sa.String(64), server_default="openai"),
        sa.Column("rag_confidence_threshold", sa.Float(), server_default="0.75"),
        sa.Column("rag_top_k", sa.Integer(), server_default="5"),
        sa.Column("rag_chunk_size", sa.Integer(), server_default="500"),
        sa.Column("rag_chunk_overlap", sa.Integer(), server_default="100"),
        sa.Column("handoff_enabled", sa.Boolean(), server_default="true"),
        sa.Column("handoff_confidence_threshold", sa.Float(), server_default="0.55"),
        sa.Column("clinical_questions_block", sa.Boolean(), server_default="true"),
        sa.Column("bot_persona", sa.Text()),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- insurance_catalog ---
    op.create_table(
        "insurance_catalog",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64)),
        sa.Column("plan_types", sa.String(512)),
        sa.Column("notes", sa.String(512)),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- prompt_registry ---
    op.create_table(
        "prompt_registry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.String(64), nullable=False, index=True),
        sa.Column("agent", sa.String(64), nullable=False, index=True),
        sa.Column("scope", sa.String(32), server_default="global"),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("prompt_registry")
    op.drop_table("insurance_catalog")
    op.drop_table("clinic_settings")
