"""Initial schema — all MVP tables

Revision ID: 001
Revises: None
Create Date: 2026-04-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- patients ---
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("cpf", sa.String(14), unique=True, index=True),
        sa.Column("birth_date", sa.Date()),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("telegram_user_id", sa.String(64), unique=True, index=True),
        sa.Column("telegram_chat_id", sa.String(64)),
        sa.Column("convenio_name", sa.String(128)),
        sa.Column("insurance_card_number", sa.String(64)),
        sa.Column("consented_ai", sa.Boolean(), server_default="false"),
        sa.Column("preferred_channel", sa.String(32), server_default="telegram"),
        sa.Column("operational_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- professionals ---
    op.create_table(
        "professionals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("specialty", sa.String(128), nullable=False),
        sa.Column("crm", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- schedule_slots ---
    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("professional_id", sa.Uuid(), sa.ForeignKey("professionals.id"), index=True, nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), index=True),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), server_default="available"),
        sa.Column("slot_type", sa.String(32), server_default="first_visit"),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), index=True),
        sa.Column("channel", sa.String(32), server_default="telegram"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("current_intent", sa.String(64)),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("human_assignee", sa.String(128)),
        sa.Column("last_message_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), index=True, nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- handoffs ---
    op.create_table(
        "handoffs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), index=True, nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("context_summary", sa.Text()),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- audit_events ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- rag_documents ---
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("category", sa.String(64), server_default="general"),
        sa.Column("source_path", sa.String(1024)),
        sa.Column("version", sa.String(20), server_default="1.0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- rag_chunks (embedding column via raw SQL for pgvector) ---
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("rag_documents.id"), index=True, nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # Add vector column via raw SQL (avoids pgvector Python import issues)
    op.execute("ALTER TABLE rag_chunks ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    op.drop_table("rag_chunks")
    op.drop_table("rag_documents")
    op.drop_table("audit_events")
    op.drop_table("handoffs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("schedule_slots")
    op.drop_table("professionals")
    op.drop_table("patients")
    op.execute("DROP EXTENSION IF EXISTS vector")
