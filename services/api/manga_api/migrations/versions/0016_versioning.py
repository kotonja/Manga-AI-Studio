"""Add non-destructive version history tables.

Revision ID: 0016_versioning
Revises: 0015_advanced_qa_autofix
Create Date: 2026-06-25 20:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_versioning"
down_revision = "0015_advanced_qa_autofix"
branch_labels = None
depends_on = None


VERSION_TABLES = [
    "project_versions",
    "page_versions",
    "panel_versions",
    "layout_versions",
    "render_versions",
    "lettering_versions",
    "story_bible_versions",
    "style_bible_versions",
    "character_card_versions",
    "export_versions",
]


def upgrade() -> None:
    for table_name in VERSION_TABLES:
        op.create_table(
            table_name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=True),
            sa.Column("parent_id", sa.Uuid(), nullable=True),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Uuid(), nullable=False),
            sa.Column("snapshot_json", sa.JSON(), nullable=False),
            sa.Column("asset_ids", sa.JSON(), nullable=False),
            sa.Column("label", sa.String(length=240), nullable=False),
            sa.Column("created_by", sa.String(length=160), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("is_checkpoint", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f(f"ix_{table_name}_project_id"), table_name, ["project_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_parent_id"), table_name, ["parent_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_entity_type"), table_name, ["entity_type"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_entity_id"), table_name, ["entity_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_label"), table_name, ["label"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_created_by"), table_name, ["created_by"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_created_at"), table_name, ["created_at"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_is_checkpoint"), table_name, ["is_checkpoint"], unique=False)


def downgrade() -> None:
    for table_name in reversed(VERSION_TABLES):
        op.drop_index(op.f(f"ix_{table_name}_is_checkpoint"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_created_at"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_created_by"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_label"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_entity_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_entity_type"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_parent_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_project_id"), table_name=table_name)
        op.drop_table(table_name)
