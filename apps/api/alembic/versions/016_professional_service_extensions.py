"""Add professional extensions, service_code, insurance rules, and human overrides.

Revision ID: 016
Revises: 015
Create Date: 2026-04-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels: tuple[str, ...] = ()
depends_on: tuple[str, ...] = ()


def upgrade() -> None:
    # ── 1. Extend professionals ────────────────────────────────────────────────
    op.add_column(
        "professionals",
        sa.Column("specialties_secondary", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "professionals",
        sa.Column("allows_teleconsultation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "professionals",
        sa.Column("accepts_insurance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "professionals",
        sa.Column("insurance_plans", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "professionals",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "professionals",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── 2. Add service_code to services ─────────────────────────────────────────
    op.add_column(
        "services",
        sa.Column("service_code", sa.String(length=32), nullable=True, index=True),
    )

    # ── 3. service_insurance_rules ────────────────────────────────────────────
    op.create_table(
        "service_insurance_rules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("insurance_name", sa.String(length=255), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_service_insurance_rules_service",
        "service_insurance_rules",
        ["service_id"],
    )
    op.create_foreign_key(
        "fk_service_insurance_rules_service",
        "service_insurance_rules", "services",
        ["service_id"], ["id"],
        ondelete="CASCADE",
    )

    # ── 4. human_overrides ─────────────────────────────────────────────────────
    op.create_table(
        "human_overrides",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("clinic_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True, index=True),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index(
        "ix_human_overrides_entity",
        "human_overrides",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_human_overrides_entity", table_name="human_overrides")
    op.drop_table("human_overrides")

    op.drop_constraint(
        "fk_service_insurance_rules_service",
        table_name="service_insurance_rules",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_index("ix_service_insurance_rules_service", table_name="service_insurance_rules")
    op.drop_table("service_insurance_rules")

    op.drop_column("services", "service_code")

    op.drop_column("professionals", "updated_at")
    op.drop_column("professionals", "notes")
    op.drop_column("professionals", "insurance_plans")
    op.drop_column("professionals", "accepts_insurance")
    op.drop_column("professionals", "allows_teleconsultation")
    op.drop_column("professionals", "specialties_secondary")
