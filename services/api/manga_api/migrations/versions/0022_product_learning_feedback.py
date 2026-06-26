"""Add product learning feedback loop.

Revision ID: 0022_product_learning_feedback
Revises: 0021_alpha_feedback_auth
Create Date: 2026-06-26 04:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_product_learning_feedback"
down_revision = "0021_alpha_feedback_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("allow_training", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("projects", sa.Column("allow_product_improvement", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("projects", sa.Column("data_collection_notes", sa.Text(), nullable=False, server_default=""))
    op.create_index(op.f("ix_projects_allow_training"), "projects", ["allow_training"], unique=False)
    op.create_index(op.f("ix_projects_allow_product_improvement"), "projects", ["allow_product_improvement"], unique=False)

    op.create_table(
        "generation_feedback",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("user_correction", sa.Text(), nullable=False),
        sa.Column("before_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("after_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("allow_use_for_product_improvement", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("rating >= -1 AND rating <= 1", name="ck_generation_feedback_rating"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("generation_feedback", ["project_id", "target_type", "target_id", "rating", "issue_type", "before_snapshot_id", "after_snapshot_id", "allow_use_for_product_improvement"])

    op.create_table(
        "page_ratings",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("allow_use_for_product_improvement", sa.Boolean(), nullable=False),
        sa.CheckConstraint("rating >= -1 AND rating <= 1", name="ck_page_ratings_rating"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"]),
        sa.ForeignKeyConstraint(["feedback_id"], ["generation_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("page_ratings", ["project_id", "page_id", "feedback_id", "rating", "issue_type", "allow_use_for_product_improvement"])

    op.create_table(
        "panel_ratings",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("panel_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("allow_use_for_product_improvement", sa.Boolean(), nullable=False),
        sa.CheckConstraint("rating >= -1 AND rating <= 1", name="ck_panel_ratings_rating"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["panel_id"], ["panels.id"]),
        sa.ForeignKeyConstraint(["feedback_id"], ["generation_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("panel_ratings", ["project_id", "panel_id", "feedback_id", "rating", "issue_type", "allow_use_for_product_improvement"])

    op.create_table(
        "export_ratings",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("allow_use_for_product_improvement", sa.Boolean(), nullable=False),
        sa.CheckConstraint("rating >= -1 AND rating <= 1", name="ck_export_ratings_rating"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["export_id"], ["exports.id"]),
        sa.ForeignKeyConstraint(["feedback_id"], ["generation_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("export_ratings", ["project_id", "export_id", "feedback_id", "rating", "issue_type", "allow_use_for_product_improvement"])

    op.create_table(
        "user_corrections",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("correction_text", sa.Text(), nullable=False),
        sa.Column("before_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("after_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("allow_use_for_product_improvement", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["feedback_id"], ["generation_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("user_corrections", ["project_id", "feedback_id", "target_type", "target_id", "before_snapshot_id", "after_snapshot_id", "allow_use_for_product_improvement"])

    op.create_table(
        "eval_runs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("scenario", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("report_path", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("eval_runs", ["name", "scenario", "provider", "status"])

    op.create_table(
        "eval_metric_snapshots",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("eval_run_id", sa.Uuid(), nullable=True),
        sa.Column("metric_name", sa.String(length=160), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    add_feedback_indexes("eval_metric_snapshots", ["eval_run_id", "metric_name", "captured_at"])

    op.alter_column("projects", "allow_training", server_default=None)
    op.alter_column("projects", "allow_product_improvement", server_default=None)
    op.alter_column("projects", "data_collection_notes", server_default=None)


def downgrade() -> None:
    for table in [
        "eval_metric_snapshots",
        "eval_runs",
        "user_corrections",
        "export_ratings",
        "panel_ratings",
        "page_ratings",
        "generation_feedback",
    ]:
        op.drop_table(table)
    op.drop_index(op.f("ix_projects_allow_product_improvement"), table_name="projects")
    op.drop_index(op.f("ix_projects_allow_training"), table_name="projects")
    op.drop_column("projects", "data_collection_notes")
    op.drop_column("projects", "allow_product_improvement")
    op.drop_column("projects", "allow_training")


def add_feedback_indexes(table_name: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column], unique=False)
