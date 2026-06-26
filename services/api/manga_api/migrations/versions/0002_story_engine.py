"""story engine

Revision ID: 0002_story_engine
Revises: 0001_initial
Create Date: 2026-06-24 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_story_engine"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def uuid_column(name: str, *args, **kwargs):
    return sa.Column(name, postgresql.UUID(as_uuid=True), *args, **kwargs)


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "story_bibles",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("logline", sa.String(length=1000), nullable=False),
        sa.Column("synopsis", sa.String(length=8000), nullable=False),
        sa.Column("genre", sa.String(length=120), nullable=False),
        sa.Column("themes", sa.JSON(), nullable=False),
        sa.Column("target_audience", sa.String(length=240), nullable=False),
        sa.Column("tone", sa.String(length=240), nullable=False),
        sa.Column("main_conflict", sa.String(length=2000), nullable=False),
        sa.Column("world_rules", sa.JSON(), nullable=False),
        sa.Column("chapter_outline", sa.JSON(), nullable=False),
        sa.Column("continuity_rules", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_story_bibles_project_id", "story_bibles", ["project_id"])

    op.create_table(
        "characters",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("story_bible_id", sa.ForeignKey("story_bibles.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("visual_notes", sa.String(length=2000), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_characters_project_id", "characters", ["project_id"])
    op.create_index("ix_characters_story_bible_id", "characters", ["story_bible_id"])
    op.create_index("ix_characters_name", "characters", ["name"])

    op.create_table(
        "locations",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("story_bible_id", sa.ForeignKey("story_bibles.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("visual_notes", sa.String(length=2000), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_locations_project_id", "locations", ["project_id"])
    op.create_index("ix_locations_story_bible_id", "locations", ["story_bible_id"])
    op.create_index("ix_locations_name", "locations", ["name"])

    op.create_table(
        "key_objects",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("story_bible_id", sa.ForeignKey("story_bibles.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("significance", sa.String(length=2000), nullable=False),
        sa.Column("visual_notes", sa.String(length=2000), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_key_objects_project_id", "key_objects", ["project_id"])
    op.create_index("ix_key_objects_story_bible_id", "key_objects", ["story_bible_id"])
    op.create_index("ix_key_objects_name", "key_objects", ["name"])

    op.create_table(
        "style_bibles",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("story_bible_id", sa.ForeignKey("story_bibles.id"), nullable=True),
        sa.Column("visual_style", sa.String(length=2000), nullable=False),
        sa.Column("line_art", sa.String(length=1000), nullable=False),
        sa.Column("palette", sa.String(length=1000), nullable=False),
        sa.Column("paneling", sa.String(length=1000), nullable=False),
        sa.Column("lettering", sa.String(length=1000), nullable=False),
        sa.Column("negative_prompts", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_style_bibles_project_id", "style_bibles", ["project_id"])
    op.create_index("ix_style_bibles_story_bible_id", "style_bibles", ["story_bible_id"])

    op.create_table(
        "chapters",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("story_bible_id", sa.ForeignKey("story_bibles.id"), nullable=True),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.String(length=4000), nullable=False),
        sa.Column("goal", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])
    op.create_index("ix_chapters_story_bible_id", "chapters", ["story_bible_id"])
    op.create_index("ix_chapters_chapter_number", "chapters", ["chapter_number"])
    op.create_index("ix_chapters_status", "chapters", ["status"])

    op.create_table(
        "scenes",
        uuid_column("id", primary_key=True),
        uuid_column("chapter_id", sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("scene_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.String(length=3000), nullable=False),
        sa.Column("location_name", sa.String(length=160), nullable=True),
        sa.Column("emotional_turn", sa.String(length=1000), nullable=True),
        sa.Column("characters", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_scenes_chapter_id", "scenes", ["chapter_id"])
    op.create_index("ix_scenes_scene_order", "scenes", ["scene_order"])

    op.create_table(
        "page_plans",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("chapter_id", sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=3000), nullable=False),
        sa.Column("pacing", sa.String(length=1000), nullable=False),
        sa.Column("panel_count", sa.Integer(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_page_plans_project_id", "page_plans", ["project_id"])
    op.create_index("ix_page_plans_chapter_id", "page_plans", ["chapter_id"])
    op.create_index("ix_page_plans_page_number", "page_plans", ["page_number"])

    op.create_table(
        "panel_plans",
        uuid_column("id", primary_key=True),
        uuid_column("page_plan_id", sa.ForeignKey("page_plans.id"), nullable=False),
        sa.Column("panel_order", sa.Integer(), nullable=False),
        sa.Column("story_beat", sa.String(length=2000), nullable=False),
        sa.Column("shot_type", sa.String(length=160), nullable=False),
        sa.Column("camera_angle", sa.String(length=160), nullable=False),
        sa.Column("characters", sa.JSON(), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("dialogue", sa.String(length=2000), nullable=True),
        sa.Column("narration", sa.String(length=2000), nullable=True),
        sa.Column("visual_notes", sa.String(length=3000), nullable=False),
        sa.Column("emotional_intent", sa.String(length=1000), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_panel_plans_page_plan_id", "panel_plans", ["page_plan_id"])
    op.create_index("ix_panel_plans_panel_order", "panel_plans", ["panel_order"])


def downgrade() -> None:
    op.drop_table("panel_plans")
    op.drop_table("page_plans")
    op.drop_table("scenes")
    op.drop_table("chapters")
    op.drop_table("style_bibles")
    op.drop_table("key_objects")
    op.drop_table("locations")
    op.drop_table("characters")
    op.drop_table("story_bibles")
