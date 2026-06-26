"""Add alpha feedback items.

Revision ID: 0021_alpha_feedback_auth
Revises: 0020_publishing_metadata
Create Date: 2026-06-26 03:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_alpha_feedback_auth"
down_revision = "0020_publishing_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_items",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("panel_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("browser_info", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("diagnostic_info", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"]),
        sa.ForeignKeyConstraint(["panel_id"], ["panels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_items_project_id"), "feedback_items", ["project_id"], unique=False)
    op.create_index(op.f("ix_feedback_items_page_id"), "feedback_items", ["page_id"], unique=False)
    op.create_index(op.f("ix_feedback_items_panel_id"), "feedback_items", ["panel_id"], unique=False)
    op.create_index(op.f("ix_feedback_items_category"), "feedback_items", ["category"], unique=False)
    op.create_index(op.f("ix_feedback_items_severity"), "feedback_items", ["severity"], unique=False)
    op.create_index(op.f("ix_feedback_items_status"), "feedback_items", ["status"], unique=False)
    op.create_index(op.f("ix_feedback_items_title"), "feedback_items", ["title"], unique=False)
    op.create_index(op.f("ix_feedback_items_contact_email"), "feedback_items", ["contact_email"], unique=False)
    op.create_index(op.f("ix_feedback_items_created_by"), "feedback_items", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_items_created_by"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_contact_email"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_title"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_status"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_severity"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_category"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_panel_id"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_page_id"), table_name="feedback_items")
    op.drop_index(op.f("ix_feedback_items_project_id"), table_name="feedback_items")
    op.drop_table("feedback_items")
