"""Add prompt registry and AI task runs.

Revision ID: 0009_ai_tasks
Revises: 0008_job_events
Create Date: 2026-06-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_ai_tasks"
down_revision = "0008_job_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema_name", sa.String(length=160), nullable=False),
        sa.Column("default_options", sa.JSON(), nullable=False),
        sa.Column("safety_notes", sa.Text(), nullable=False),
        sa.Column("changelog", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prompt_templates_output_schema_name"), "prompt_templates", ["output_schema_name"], unique=False)
    op.create_index(op.f("ix_prompt_templates_task_type"), "prompt_templates", ["task_type"], unique=False)
    op.create_index(op.f("ix_prompt_templates_version"), "prompt_templates", ["version"], unique=False)

    op.create_table(
        "ai_task_runs",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=160), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("schema_name", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("raw_input", sa.JSON(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("parsed_output", sa.JSON(), nullable=True),
        sa.Column("token_metadata", sa.JSON(), nullable=False),
        sa.Column("cost_metadata", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_template_id"], ["prompt_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_task_runs_prompt_template_id"), "ai_task_runs", ["prompt_template_id"], unique=False)
    op.create_index(op.f("ix_ai_task_runs_provider"), "ai_task_runs", ["provider"], unique=False)
    op.create_index(op.f("ix_ai_task_runs_schema_name"), "ai_task_runs", ["schema_name"], unique=False)
    op.create_index(op.f("ix_ai_task_runs_status"), "ai_task_runs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_task_runs_task_type"), "ai_task_runs", ["task_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_task_runs_task_type"), table_name="ai_task_runs")
    op.drop_index(op.f("ix_ai_task_runs_status"), table_name="ai_task_runs")
    op.drop_index(op.f("ix_ai_task_runs_schema_name"), table_name="ai_task_runs")
    op.drop_index(op.f("ix_ai_task_runs_provider"), table_name="ai_task_runs")
    op.drop_index(op.f("ix_ai_task_runs_prompt_template_id"), table_name="ai_task_runs")
    op.drop_table("ai_task_runs")
    op.drop_index(op.f("ix_prompt_templates_version"), table_name="prompt_templates")
    op.drop_index(op.f("ix_prompt_templates_task_type"), table_name="prompt_templates")
    op.drop_index(op.f("ix_prompt_templates_output_schema_name"), table_name="prompt_templates")
    op.drop_table("prompt_templates")
