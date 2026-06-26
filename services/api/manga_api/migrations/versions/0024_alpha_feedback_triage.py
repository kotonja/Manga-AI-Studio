"""Add private alpha feedback triage fields.

Revision ID: 0024_alpha_feedback_triage
Revises: 0023_project_owner_assets
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0024_alpha_feedback_triage"
down_revision = "0023_project_owner_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feedback_items", sa.Column("internal_notes", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE feedback_items SET status = 'new' WHERE status = 'open'")
    op.alter_column("feedback_items", "internal_notes", server_default=None)


def downgrade() -> None:
    op.execute("UPDATE feedback_items SET status = 'open' WHERE status = 'new'")
    op.drop_column("feedback_items", "internal_notes")
