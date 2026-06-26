"""character and style labs

Revision ID: 0004_character_style_labs
Revises: 0003_page_studio
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_character_style_labs"
down_revision = "0003_page_studio"
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
    op.add_column("projects", uuid_column("active_style_bible_id", nullable=True))
    op.create_index("ix_projects_active_style_bible_id", "projects", ["active_style_bible_id"])

    op.add_column("style_bibles", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column("style_bibles", sa.Column("linework", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("screentone", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("hatching", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("black_white_balance", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("face_language", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("anatomy_style", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("background_detail", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("panel_rhythm", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("sfx_style", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("typography_notes", sa.String(length=2000), nullable=True))
    op.add_column("style_bibles", sa.Column("forbidden_references", sa.JSON(), nullable=True))
    op.add_column("style_bibles", sa.Column("prompt_style_positive", sa.String(length=4000), nullable=True))
    op.add_column("style_bibles", sa.Column("prompt_style_negative", sa.String(length=4000), nullable=True))
    op.execute("UPDATE style_bibles SET name = 'Untitled Style Bible' WHERE name IS NULL")
    op.execute("UPDATE style_bibles SET linework = '' WHERE linework IS NULL")
    op.execute("UPDATE style_bibles SET screentone = '' WHERE screentone IS NULL")
    op.execute("UPDATE style_bibles SET hatching = '' WHERE hatching IS NULL")
    op.execute("UPDATE style_bibles SET black_white_balance = '' WHERE black_white_balance IS NULL")
    op.execute("UPDATE style_bibles SET face_language = '' WHERE face_language IS NULL")
    op.execute("UPDATE style_bibles SET anatomy_style = '' WHERE anatomy_style IS NULL")
    op.execute("UPDATE style_bibles SET background_detail = '' WHERE background_detail IS NULL")
    op.execute("UPDATE style_bibles SET panel_rhythm = '' WHERE panel_rhythm IS NULL")
    op.execute("UPDATE style_bibles SET sfx_style = '' WHERE sfx_style IS NULL")
    op.execute("UPDATE style_bibles SET typography_notes = '' WHERE typography_notes IS NULL")
    op.execute("UPDATE style_bibles SET forbidden_references = '[]' WHERE forbidden_references IS NULL")
    op.execute("UPDATE style_bibles SET prompt_style_positive = '' WHERE prompt_style_positive IS NULL")
    op.execute("UPDATE style_bibles SET prompt_style_negative = '' WHERE prompt_style_negative IS NULL")
    for column_name in [
        "name",
        "linework",
        "screentone",
        "hatching",
        "black_white_balance",
        "face_language",
        "anatomy_style",
        "background_detail",
        "panel_rhythm",
        "sfx_style",
        "typography_notes",
        "forbidden_references",
        "prompt_style_positive",
        "prompt_style_negative",
    ]:
        op.alter_column("style_bibles", column_name, nullable=False)
    op.create_index("ix_style_bibles_name", "style_bibles", ["name"])

    op.create_table(
        "character_cards",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("age_range", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=False),
        sa.Column("personality", sa.String(length=3000), nullable=False),
        sa.Column("face_description", sa.String(length=2000), nullable=False),
        sa.Column("hair_description", sa.String(length=2000), nullable=False),
        sa.Column("eye_description", sa.String(length=2000), nullable=False),
        sa.Column("body_type", sa.String(length=1000), nullable=False),
        sa.Column("outfit_default", sa.String(length=2000), nullable=False),
        sa.Column("accessories", sa.JSON(), nullable=False),
        sa.Column("scars_marks", sa.String(length=2000), nullable=False),
        sa.Column("voice_style", sa.String(length=1000), nullable=False),
        sa.Column("forbidden_changes", sa.JSON(), nullable=False),
        sa.Column("continuity_rules", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_character_cards_project_id", "character_cards", ["project_id"])
    op.create_index("ix_character_cards_name", "character_cards", ["name"])

    op.create_table(
        "character_reference_assets",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("character_card_id", sa.ForeignKey("character_cards.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_character_reference_assets_project_id", "character_reference_assets", ["project_id"])
    op.create_index("ix_character_reference_assets_character_card_id", "character_reference_assets", ["character_card_id"])
    op.create_index("ix_character_reference_assets_kind", "character_reference_assets", ["kind"])
    op.create_index("ix_character_reference_assets_storage_key", "character_reference_assets", ["storage_key"], unique=True)

    op.create_table(
        "expression_sheets",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("character_card_id", sa.ForeignKey("character_cards.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("expressions", sa.JSON(), nullable=False),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_expression_sheets_project_id", "expression_sheets", ["project_id"])
    op.create_index("ix_expression_sheets_character_card_id", "expression_sheets", ["character_card_id"])

    op.create_table(
        "outfit_variants",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("character_card_id", sa.ForeignKey("character_cards.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("accessories", sa.JSON(), nullable=False),
        sa.Column("continuity_notes", sa.String(length=2000), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_outfit_variants_project_id", "outfit_variants", ["project_id"])
    op.create_index("ix_outfit_variants_character_card_id", "outfit_variants", ["character_card_id"])

    op.create_table(
        "style_sample_assets",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        uuid_column("style_bible_id", sa.ForeignKey("style_bibles.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_style_sample_assets_project_id", "style_sample_assets", ["project_id"])
    op.create_index("ix_style_sample_assets_style_bible_id", "style_sample_assets", ["style_bible_id"])
    op.create_index("ix_style_sample_assets_kind", "style_sample_assets", ["kind"])
    op.create_index("ix_style_sample_assets_storage_key", "style_sample_assets", ["storage_key"], unique=True)


def downgrade() -> None:
    op.drop_table("style_sample_assets")
    op.drop_table("outfit_variants")
    op.drop_table("expression_sheets")
    op.drop_table("character_reference_assets")
    op.drop_table("character_cards")
    op.drop_index("ix_style_bibles_name", table_name="style_bibles")
    for column_name in [
        "prompt_style_negative",
        "prompt_style_positive",
        "forbidden_references",
        "typography_notes",
        "sfx_style",
        "panel_rhythm",
        "background_detail",
        "anatomy_style",
        "face_language",
        "black_white_balance",
        "hatching",
        "screentone",
        "linework",
        "name",
    ]:
        op.drop_column("style_bibles", column_name)
    op.drop_index("ix_projects_active_style_bible_id", table_name="projects")
    op.drop_column("projects", "active_style_bible_id")
