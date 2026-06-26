"""Add advanced layout templates.

Revision ID: 0012_layout_templates
Revises: 0011_style_dna
Create Date: 2026-06-25 15:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_layout_templates"
down_revision = "0011_style_dna"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "layout_templates",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("page_type", sa.String(length=64), nullable=False),
        sa.Column("panel_count", sa.Integer(), nullable=False),
        sa.Column("reading_direction", sa.String(length=16), nullable=False),
        sa.Column("emotional_use", sa.Text(), nullable=False),
        sa.Column("action_level", sa.String(length=64), nullable=False),
        sa.Column("density", sa.String(length=64), nullable=False),
        sa.Column("layout_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_layout_templates_action_level"), "layout_templates", ["action_level"], unique=False)
    op.create_index(op.f("ix_layout_templates_density"), "layout_templates", ["density"], unique=False)
    op.create_index(op.f("ix_layout_templates_name"), "layout_templates", ["name"], unique=False)
    op.create_index(op.f("ix_layout_templates_page_type"), "layout_templates", ["page_type"], unique=False)
    op.create_index(op.f("ix_layout_templates_panel_count"), "layout_templates", ["panel_count"], unique=False)
    op.create_index(op.f("ix_layout_templates_project_id"), "layout_templates", ["project_id"], unique=False)
    op.create_index(op.f("ix_layout_templates_reading_direction"), "layout_templates", ["reading_direction"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_layout_templates_reading_direction"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_project_id"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_panel_count"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_page_type"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_name"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_density"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_action_level"), table_name="layout_templates")
    op.drop_table("layout_templates")
