"""Allow long-form project descriptions.

Revision ID: 0007_long_project_description
Revises: 0006_project_exports
Create Date: 2026-06-24 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_long_project_description"
down_revision = "0006_project_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "description",
        existing_type=sa.String(length=2000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "projects",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(length=2000),
        existing_nullable=True,
    )
