"""Add panel render prompt history.

Revision ID: 0013_panel_render_prompts
Revises: 0012_layout_templates
Create Date: 2026-06-25 17:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_panel_render_prompts"
down_revision = "0012_layout_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "panel_render_prompts",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("panel_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("structured_context", sa.JSON(), nullable=False),
        sa.Column("reference_pack", sa.JSON(), nullable=False),
        sa.Column("size", sa.String(length=32), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("quality_mode", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["panel_id"], ["panels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_panel_render_prompts_panel_id"), "panel_render_prompts", ["panel_id"], unique=False)
    op.create_index(op.f("ix_panel_render_prompts_prompt_version"), "panel_render_prompts", ["prompt_version"], unique=False)
    op.create_index(op.f("ix_panel_render_prompts_provider_name"), "panel_render_prompts", ["provider_name"], unique=False)
    op.create_index(op.f("ix_panel_render_prompts_quality_mode"), "panel_render_prompts", ["quality_mode"], unique=False)
    op.create_index(op.f("ix_panel_render_prompts_seed"), "panel_render_prompts", ["seed"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_panel_render_prompts_seed"), table_name="panel_render_prompts")
    op.drop_index(op.f("ix_panel_render_prompts_quality_mode"), table_name="panel_render_prompts")
    op.drop_index(op.f("ix_panel_render_prompts_provider_name"), table_name="panel_render_prompts")
    op.drop_index(op.f("ix_panel_render_prompts_prompt_version"), table_name="panel_render_prompts")
    op.drop_index(op.f("ix_panel_render_prompts_panel_id"), table_name="panel_render_prompts")
    op.drop_table("panel_render_prompts")
