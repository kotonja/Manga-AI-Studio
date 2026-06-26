"""Add original style DNA fields.

Revision ID: 0011_style_dna
Revises: 0010_character_consistency
Create Date: 2026-06-25 13:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_style_dna"
down_revision = "0010_character_consistency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    text_columns = [
        ("style_name", 200),
        ("style_intent", 3000),
        ("line_weight", 1000),
        ("line_variation", 1000),
        ("line_texture", 1000),
        ("face_shape_language", 2000),
        ("eye_design_language", 2000),
        ("nose_mouth_simplification", 2000),
        ("anatomy_proportions", 2000),
        ("hair_rendering", 2000),
        ("clothing_fold_style", 2000),
        ("background_density", 2000),
        ("architecture_detail", 2000),
        ("shadow_strategy", 2000),
        ("screentone_strategy", 2000),
        ("hatching_strategy", 2000),
        ("black_fill_ratio", 1000),
        ("speedline_style", 2000),
        ("impact_frame_style", 2000),
        ("panel_border_style", 2000),
        ("gutter_style", 2000),
        ("sfx_shape_language", 2000),
        ("bubble_style", 2000),
    ]
    for name, length in text_columns:
        op.add_column("style_bibles", sa.Column(name, sa.String(length=length), nullable=False, server_default=""))

    for name in [
        "emotional_visual_rules",
        "positive_prompt_fragments",
        "negative_prompt_fragments",
        "forbidden_artist_references",
        "forbidden_franchise_references",
    ]:
        op.add_column("style_bibles", sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))

    op.create_index(op.f("ix_style_bibles_style_name"), "style_bibles", ["style_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_style_bibles_style_name"), table_name="style_bibles")
    for name in [
        "forbidden_franchise_references",
        "forbidden_artist_references",
        "negative_prompt_fragments",
        "positive_prompt_fragments",
        "emotional_visual_rules",
        "bubble_style",
        "sfx_shape_language",
        "gutter_style",
        "panel_border_style",
        "impact_frame_style",
        "speedline_style",
        "black_fill_ratio",
        "hatching_strategy",
        "screentone_strategy",
        "shadow_strategy",
        "architecture_detail",
        "background_density",
        "clothing_fold_style",
        "hair_rendering",
        "anatomy_proportions",
        "nose_mouth_simplification",
        "eye_design_language",
        "face_shape_language",
        "line_texture",
        "line_variation",
        "line_weight",
        "style_intent",
        "style_name",
    ]:
        op.drop_column("style_bibles", name)
