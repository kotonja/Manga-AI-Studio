"""Add professional lettering layers.

Revision ID: 0014_professional_lettering
Revises: 0013_panel_render_prompts
Create Date: 2026-06-25 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_professional_lettering"
down_revision = "0013_panel_render_prompts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bubbles", sa.Column("bubble_type", sa.String(length=32), nullable=False, server_default="speech"))
    op.add_column("bubbles", sa.Column("speaker_character_id", sa.Uuid(), nullable=True))
    op.add_column("bubbles", sa.Column("language", sa.String(length=16), nullable=False, server_default="en"))
    op.add_column("bubbles", sa.Column("reading_direction", sa.String(length=16), nullable=False, server_default="rtl"))
    op.add_column("bubbles", sa.Column("shape", sa.String(length=64), nullable=False, server_default="oval"))
    op.add_column("bubbles", sa.Column("position", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("bubbles", sa.Column("size", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("bubbles", sa.Column("tail_target", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("bubbles", sa.Column("font_family", sa.String(length=160), nullable=False, server_default="Manga Temple"))
    op.add_column("bubbles", sa.Column("font_size", sa.Integer(), nullable=False, server_default="24"))
    op.add_column("bubbles", sa.Column("font_weight", sa.String(length=40), nullable=False, server_default="regular"))
    op.add_column("bubbles", sa.Column("text_align", sa.String(length=24), nullable=False, server_default="center"))
    op.add_column("bubbles", sa.Column("vertical_text", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("bubbles", sa.Column("z_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bubbles", sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE bubbles SET bubble_type = kind WHERE bubble_type = 'speech'")
    op.execute("UPDATE bubbles SET position = json_build_object('x', x, 'y', y)")
    op.execute("UPDATE bubbles SET size = json_build_object('width', width, 'height', height)")
    op.create_foreign_key("fk_bubbles_speaker_character_id", "bubbles", "character_cards", ["speaker_character_id"], ["id"])
    op.create_index(op.f("ix_bubbles_bubble_type"), "bubbles", ["bubble_type"], unique=False)
    op.create_index(op.f("ix_bubbles_speaker_character_id"), "bubbles", ["speaker_character_id"], unique=False)
    op.create_index(op.f("ix_bubbles_language"), "bubbles", ["language"], unique=False)
    op.create_index(op.f("ix_bubbles_reading_direction"), "bubbles", ["reading_direction"], unique=False)
    op.create_index(op.f("ix_bubbles_vertical_text"), "bubbles", ["vertical_text"], unique=False)
    op.create_index(op.f("ix_bubbles_z_index"), "bubbles", ["z_index"], unique=False)
    op.create_index(op.f("ix_bubbles_locked"), "bubbles", ["locked"], unique=False)

    op.create_table(
        "sfx_elements",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("panel_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("meaning", sa.String(length=1000), nullable=False),
        sa.Column("style", sa.String(length=120), nullable=False),
        sa.Column("position", sa.JSON(), nullable=False),
        sa.Column("size", sa.JSON(), nullable=False),
        sa.Column("rotation", sa.Float(), nullable=False),
        sa.Column("warp_style", sa.String(length=120), nullable=False),
        sa.Column("stroke_width", sa.Float(), nullable=False),
        sa.Column("fill", sa.String(length=32), nullable=False),
        sa.Column("outline", sa.String(length=32), nullable=False),
        sa.Column("z_index", sa.Integer(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"]),
        sa.ForeignKeyConstraint(["panel_id"], ["panels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sfx_elements_page_id"), "sfx_elements", ["page_id"], unique=False)
    op.create_index(op.f("ix_sfx_elements_panel_id"), "sfx_elements", ["panel_id"], unique=False)
    op.create_index(op.f("ix_sfx_elements_style"), "sfx_elements", ["style"], unique=False)
    op.create_index(op.f("ix_sfx_elements_z_index"), "sfx_elements", ["z_index"], unique=False)
    op.create_index(op.f("ix_sfx_elements_locked"), "sfx_elements", ["locked"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sfx_elements_locked"), table_name="sfx_elements")
    op.drop_index(op.f("ix_sfx_elements_z_index"), table_name="sfx_elements")
    op.drop_index(op.f("ix_sfx_elements_style"), table_name="sfx_elements")
    op.drop_index(op.f("ix_sfx_elements_panel_id"), table_name="sfx_elements")
    op.drop_index(op.f("ix_sfx_elements_page_id"), table_name="sfx_elements")
    op.drop_table("sfx_elements")
    op.drop_index(op.f("ix_bubbles_locked"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_z_index"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_vertical_text"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_reading_direction"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_language"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_speaker_character_id"), table_name="bubbles")
    op.drop_index(op.f("ix_bubbles_bubble_type"), table_name="bubbles")
    op.drop_constraint("fk_bubbles_speaker_character_id", "bubbles", type_="foreignkey")
    for name in [
        "locked",
        "z_index",
        "vertical_text",
        "text_align",
        "font_weight",
        "font_size",
        "font_family",
        "tail_target",
        "size",
        "position",
        "shape",
        "reading_direction",
        "language",
        "speaker_character_id",
        "bubble_type",
    ]:
        op.drop_column("bubbles", name)
