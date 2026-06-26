"""Add pacing intelligence fields to story plans.

Revision ID: 0019_pacing_intelligence
Revises: 0018_command_center
Create Date: 2026-06-26 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_pacing_intelligence"
down_revision = "0018_command_center"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("page_plans", sa.Column("page_role", sa.String(length=120), nullable=False, server_default="story_progression"))
    op.add_column("page_plans", sa.Column("emotional_intensity", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("page_plans", sa.Column("action_intensity", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("page_plans", sa.Column("dialogue_density", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("page_plans", sa.Column("silence_level", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("page_plans", sa.Column("reveal_level", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("page_plans", sa.Column("page_turn_importance", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("page_plans", sa.Column("recommended_page_type", sa.String(length=64), nullable=False, server_default="standard"))
    op.add_column("page_plans", sa.Column("pacing_notes", sa.Text(), nullable=False, server_default=""))
    op.create_index(op.f("ix_page_plans_page_role"), "page_plans", ["page_role"], unique=False)
    op.create_index(op.f("ix_page_plans_emotional_intensity"), "page_plans", ["emotional_intensity"], unique=False)
    op.create_index(op.f("ix_page_plans_action_intensity"), "page_plans", ["action_intensity"], unique=False)
    op.create_index(op.f("ix_page_plans_dialogue_density"), "page_plans", ["dialogue_density"], unique=False)
    op.create_index(op.f("ix_page_plans_silence_level"), "page_plans", ["silence_level"], unique=False)
    op.create_index(op.f("ix_page_plans_reveal_level"), "page_plans", ["reveal_level"], unique=False)
    op.create_index(op.f("ix_page_plans_page_turn_importance"), "page_plans", ["page_turn_importance"], unique=False)
    op.create_index(op.f("ix_page_plans_recommended_page_type"), "page_plans", ["recommended_page_type"], unique=False)

    op.add_column("panel_plans", sa.Column("beat_importance", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("panel_plans", sa.Column("time_duration", sa.String(length=80), nullable=False, server_default="normal"))
    op.add_column("panel_plans", sa.Column("camera_motion", sa.String(length=120), nullable=False, server_default="still"))
    op.add_column("panel_plans", sa.Column("motion_intensity", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("panel_plans", sa.Column("dialogue_weight", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("panel_plans", sa.Column("silence", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("panel_plans", sa.Column("impact_level", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("panel_plans", sa.Column("recommended_panel_size", sa.String(length=40), nullable=False, server_default="medium"))
    op.add_column("panel_plans", sa.Column("transition_type", sa.String(length=80), nullable=False, server_default="moment_to_moment"))
    op.create_index(op.f("ix_panel_plans_beat_importance"), "panel_plans", ["beat_importance"], unique=False)
    op.create_index(op.f("ix_panel_plans_time_duration"), "panel_plans", ["time_duration"], unique=False)
    op.create_index(op.f("ix_panel_plans_motion_intensity"), "panel_plans", ["motion_intensity"], unique=False)
    op.create_index(op.f("ix_panel_plans_dialogue_weight"), "panel_plans", ["dialogue_weight"], unique=False)
    op.create_index(op.f("ix_panel_plans_silence"), "panel_plans", ["silence"], unique=False)
    op.create_index(op.f("ix_panel_plans_impact_level"), "panel_plans", ["impact_level"], unique=False)
    op.create_index(op.f("ix_panel_plans_recommended_panel_size"), "panel_plans", ["recommended_panel_size"], unique=False)
    op.create_index(op.f("ix_panel_plans_transition_type"), "panel_plans", ["transition_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_panel_plans_transition_type"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_recommended_panel_size"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_impact_level"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_silence"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_dialogue_weight"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_motion_intensity"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_time_duration"), table_name="panel_plans")
    op.drop_index(op.f("ix_panel_plans_beat_importance"), table_name="panel_plans")
    op.drop_column("panel_plans", "transition_type")
    op.drop_column("panel_plans", "recommended_panel_size")
    op.drop_column("panel_plans", "impact_level")
    op.drop_column("panel_plans", "silence")
    op.drop_column("panel_plans", "dialogue_weight")
    op.drop_column("panel_plans", "motion_intensity")
    op.drop_column("panel_plans", "camera_motion")
    op.drop_column("panel_plans", "time_duration")
    op.drop_column("panel_plans", "beat_importance")

    op.drop_index(op.f("ix_page_plans_recommended_page_type"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_page_turn_importance"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_reveal_level"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_silence_level"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_dialogue_density"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_action_intensity"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_emotional_intensity"), table_name="page_plans")
    op.drop_index(op.f("ix_page_plans_page_role"), table_name="page_plans")
    op.drop_column("page_plans", "pacing_notes")
    op.drop_column("page_plans", "recommended_page_type")
    op.drop_column("page_plans", "page_turn_importance")
    op.drop_column("page_plans", "reveal_level")
    op.drop_column("page_plans", "silence_level")
    op.drop_column("page_plans", "dialogue_density")
    op.drop_column("page_plans", "action_intensity")
    op.drop_column("page_plans", "emotional_intensity")
    op.drop_column("page_plans", "page_role")
