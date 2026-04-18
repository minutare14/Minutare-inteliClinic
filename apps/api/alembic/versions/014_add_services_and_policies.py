"""Add services, service_prices, clinic_policies, document_extractions tables.

Revision ID: 014
Revises: 013
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels: tuple[str, ...] = ()
depends_on: tuple[str, ...] = ()


def upgrade() -> None:
    # ── 1. service_categories ──────────────────────────────────────────────────
    op.create_table(
        "service_categories",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # ── 2. services ───────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_min", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_services_clinic_category", "services", ["clinic_id", "category_id"])
    op.create_foreign_key(
        "fk_services_category",
        "services", "service_categories",
        ["category_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── 3. service_prices ─────────────────────────────────────────────────────
    op.create_table(
        "service_prices",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("insurance_plan_id", sa.UUID(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("copay", sa.Numeric(10, 2), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_foreign_key(
        "fk_service_prices_service",
        "service_prices", "services",
        ["service_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_service_prices_insurance",
        "service_prices", "insurance_catalog",
        ["insurance_plan_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── 4. clinic_policies ────────────────────────────────────────────────────
    op.create_table(
        "clinic_policies",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # ── 5. document_extractions ────────────────────────────────────────────────
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_to", sa.String(length=64), nullable=True),
        sa.Column("published_entity_id", sa.UUID(), nullable=True),
        sa.Column("superseded_by", sa.UUID(), nullable=True),
        sa.Column("source_extraction_id", sa.UUID(), nullable=True),
        sa.Column("orphaned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_document_extractions_document_id", "document_extractions", ["document_id"])
    op.create_index("ix_document_extractions_status", "document_extractions", ["status"])
    op.create_index("ix_document_extractions_entity_type", "document_extractions", ["entity_type"])
    op.create_foreign_key(
        "fk_document_extractions_document",
        "document_extractions", "rag_documents",
        ["document_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_document_extractions_superseded",
        "document_extractions", "document_extractions",
        ["superseded_by"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_document_extractions_source",
        "document_extractions", "document_extractions",
        ["source_extraction_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_document_extractions_source", table_name="document_extractions", type_="foreignkey", if_exists=True)
    op.drop_constraint("fk_document_extractions_superseded", table_name="document_extractions", type_="foreignkey", if_exists=True)
    op.drop_constraint("fk_document_extractions_document", table_name="document_extractions", type_="foreignkey", if_exists=True)
    op.drop_index("ix_document_extractions_entity_type", table_name="document_extractions")
    op.drop_index("ix_document_extractions_status", table_name="document_extractions")
    op.drop_index("ix_document_extractions_document_id", table_name="document_extractions")
    op.drop_table("document_extractions")

    op.drop_table("clinic_policies")

    op.drop_constraint("fk_service_prices_insurance", table_name="service_prices", type_="foreignkey", if_exists=True)
    op.drop_constraint("fk_service_prices_service", table_name="service_prices", type_="foreignkey", if_exists=True)
    op.drop_table("service_prices")

    op.drop_index("ix_services_clinic_category", table_name="services")
    op.drop_constraint("fk_services_category", table_name="services", type_="foreignkey", if_exists=True)
    op.drop_table("services")

    op.drop_table("service_categories")
