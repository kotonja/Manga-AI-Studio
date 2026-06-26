"""Add character consistency fields and states.

Revision ID: 0010_character_consistency
Revises: 0009_ai_tasks
Create Date: 2026-06-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_character_consistency"
down_revision = "0009_ai_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_cards", sa.Column("canonical_visual_summary", sa.String(length=4000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("silhouette_keywords", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("character_cards", sa.Column("face_anchor_description", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("hair_anchor_description", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("eye_anchor_description", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("body_anchor_description", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("outfit_anchor_description", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("color_notes_even_for_bw", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("recurring_props", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("character_cards", sa.Column("allowed_variations", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("character_cards", sa.Column("forbidden_variations", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("character_cards", sa.Column("current_story_state", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("injury_state", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("emotional_baseline", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("character_cards", sa.Column("reference_asset_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("character_cards", sa.Column("approved_panel_asset_ids", sa.JSON(), nullable=False, server_default="[]"))

    op.create_table(
        "character_states",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("character_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("outfit_state", sa.String(length=2000), nullable=False),
        sa.Column("injury_state", sa.String(length=2000), nullable=False),
        sa.Column("emotional_state", sa.String(length=2000), nullable=False),
        sa.Column("prop_state", sa.String(length=2000), nullable=False),
        sa.Column("visibility_notes", sa.String(length=2000), nullable=False),
        sa.Column("continuity_notes", sa.String(length=3000), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["character_cards.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_states_chapter_id"), "character_states", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_character_states_character_id"), "character_states", ["character_id"], unique=False)
    op.create_index(op.f("ix_character_states_page_id"), "character_states", ["page_id"], unique=False)
    op.create_index(op.f("ix_character_states_scene_id"), "character_states", ["scene_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_character_states_scene_id"), table_name="character_states")
    op.drop_index(op.f("ix_character_states_page_id"), table_name="character_states")
    op.drop_index(op.f("ix_character_states_character_id"), table_name="character_states")
    op.drop_index(op.f("ix_character_states_chapter_id"), table_name="character_states")
    op.drop_table("character_states")

    op.drop_column("character_cards", "approved_panel_asset_ids")
    op.drop_column("character_cards", "reference_asset_ids")
    op.drop_column("character_cards", "emotional_baseline")
    op.drop_column("character_cards", "injury_state")
    op.drop_column("character_cards", "current_story_state")
    op.drop_column("character_cards", "forbidden_variations")
    op.drop_column("character_cards", "allowed_variations")
    op.drop_column("character_cards", "recurring_props")
    op.drop_column("character_cards", "color_notes_even_for_bw")
    op.drop_column("character_cards", "outfit_anchor_description")
    op.drop_column("character_cards", "body_anchor_description")
    op.drop_column("character_cards", "eye_anchor_description")
    op.drop_column("character_cards", "hair_anchor_description")
    op.drop_column("character_cards", "face_anchor_description")
    op.drop_column("character_cards", "silhouette_keywords")
    op.drop_column("character_cards", "canonical_visual_summary")
