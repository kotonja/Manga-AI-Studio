"""Add project publishing metadata.

Revision ID: 0020_publishing_metadata
Revises: 0019_pacing_intelligence
Create Date: 2026-06-26 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_publishing_metadata"
down_revision = "0019_pacing_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_publishing_metadata",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("subtitle", sa.String(length=240), nullable=False),
        sa.Column("author_name", sa.String(length=240), nullable=False),
        sa.Column("publisher", sa.String(length=240), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("age_rating", sa.String(length=80), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("copyright_notice", sa.Text(), nullable=False),
        sa.Column("ai_disclosure_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_project_publishing_metadata_project_id"),
    )
    op.create_index(op.f("ix_project_publishing_metadata_project_id"), "project_publishing_metadata", ["project_id"], unique=True)
    op.create_index(op.f("ix_project_publishing_metadata_title"), "project_publishing_metadata", ["title"], unique=False)
    op.create_index(op.f("ix_project_publishing_metadata_author_name"), "project_publishing_metadata", ["author_name"], unique=False)
    op.create_index(op.f("ix_project_publishing_metadata_language"), "project_publishing_metadata", ["language"], unique=False)
    op.create_index(op.f("ix_project_publishing_metadata_age_rating"), "project_publishing_metadata", ["age_rating"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_publishing_metadata_age_rating"), table_name="project_publishing_metadata")
    op.drop_index(op.f("ix_project_publishing_metadata_language"), table_name="project_publishing_metadata")
    op.drop_index(op.f("ix_project_publishing_metadata_author_name"), table_name="project_publishing_metadata")
    op.drop_index(op.f("ix_project_publishing_metadata_title"), table_name="project_publishing_metadata")
    op.drop_index(op.f("ix_project_publishing_metadata_project_id"), table_name="project_publishing_metadata")
    op.drop_table("project_publishing_metadata")
