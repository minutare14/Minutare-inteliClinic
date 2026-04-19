"""Add professional_service_links, service_operational_rules, extend services and service_prices.

Revision ID: 015
Revises: 014
Create Date: 2026-04-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels: tuple[str, ...] = ()
depends_on: tuple[str, ...] = ()


def upgrade() -> None:
    # ── 1. Extend services ───────────────────────────────────────────────────
    op.add_column(
        "services",
        sa.Column("requires_specific_doctor", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "services",
        sa.Column("ai_summary", sa.String(length=500), nullable=True),
    )

    # ── 2. Extend service_prices ──────────────────────────────────────────────
    op.add_column(
        "service_prices",
        sa.Column("price_changed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "service_prices",
        sa.Column("changed_by", sa.String(length=64), nullable=True),
    )

    # ── 3. professional_service_links ─────────────────────────────────────────
    op.create_table(
        "professional_service_links",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("professional_id", sa.UUID(), nullable=True),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_professional_service_links_clinic",
        "professional_service_links",
        ["clinic_id", "service_id"],
    )
    op.create_index(
        "ix_professional_service_links_professional",
        "professional_service_links",
        ["professional_id"],
    )
    op.create_foreign_key(
        "fk_professional_service_links_professional",
        "professional_service_links", "professionals",
        ["professional_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_professional_service_links_service",
        "professional_service_links", "services",
        ["service_id"], ["id"],
        ondelete="CASCADE",
    )

    # ── 4. service_operational_rules ──────────────────────────────────────────
    op.create_table(
        "service_operational_rules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_service_operational_rules_service",
        "service_operational_rules",
        ["service_id"],
    )
    op.create_foreign_key(
        "fk_service_operational_rules_service",
        "service_operational_rules", "services",
        ["service_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_service_operational_rules_service", table_name="service_operational_rules", type_="foreignkey", if_exists=True)
    op.drop_index("ix_service_operational_rules_service", table_name="service_operational_rules")
    op.drop_table("service_operational_rules")

    op.drop_constraint("fk_professional_service_links_service", table_name="professional_service_links", type_="foreignkey", if_exists=True)
    op.drop_constraint("fk_professional_service_links_professional", table_name="professional_service_links", type_="foreignkey", if_exists=True)
    op.drop_index("ix_professional_service_links_professional", table_name="professional_service_links")
    op.drop_index("ix_professional_service_links_clinic", table_name="professional_service_links")
    op.drop_table("professional_service_links")

    op.drop_column("service_prices", "changed_by")
    op.drop_column("service_prices", "price_changed_at")

    op.drop_column("services", "ai_summary")
    op.drop_column("services", "requires_specific_doctor")
