"""Add project ownership and private asset download settings.

Revision ID: 0023_project_owner_assets
Revises: 0022_product_learning_feedback
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0023_project_owner_assets"
down_revision = "0022_product_learning_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("owner_user_id", sa.String(length=160), nullable=False, server_default="local-dev"))
    op.create_index(op.f("ix_projects_owner_user_id"), "projects", ["owner_user_id"], unique=False)
    op.alter_column("projects", "owner_user_id", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_owner_user_id"), table_name="projects")
    op.drop_column("projects", "owner_user_id")
