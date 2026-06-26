"""Add command center history.

Revision ID: 0018_command_center
Revises: 0017_creator_rights_provenance
Create Date: 2026-06-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_command_center"
down_revision = "0017_creator_rights_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "command_history",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=80), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=80), nullable=False),
        sa.Column("proposed_actions", sa.JSON(), nullable=False),
        sa.Column("executed_actions", sa.JSON(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_command_history_project_id"), "command_history", ["project_id"], unique=False)
    op.create_index(op.f("ix_command_history_scope_type"), "command_history", ["scope_type"], unique=False)
    op.create_index(op.f("ix_command_history_scope_id"), "command_history", ["scope_id"], unique=False)
    op.create_index(op.f("ix_command_history_intent"), "command_history", ["intent"], unique=False)
    op.create_index(op.f("ix_command_history_target_type"), "command_history", ["target_type"], unique=False)
    op.create_index(op.f("ix_command_history_target_id"), "command_history", ["target_id"], unique=False)
    op.create_index(op.f("ix_command_history_requires_confirmation"), "command_history", ["requires_confirmation"], unique=False)
    op.create_index(op.f("ix_command_history_confirmed"), "command_history", ["confirmed"], unique=False)
    op.create_index(op.f("ix_command_history_risk_level"), "command_history", ["risk_level"], unique=False)
    op.create_index(op.f("ix_command_history_status"), "command_history", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_command_history_status"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_risk_level"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_confirmed"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_requires_confirmation"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_target_id"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_target_type"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_intent"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_scope_id"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_scope_type"), table_name="command_history")
    op.drop_index(op.f("ix_command_history_project_id"), table_name="command_history")
    op.drop_table("command_history")
