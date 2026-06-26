"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-24 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
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
        "projects",
        uuid_column("id", primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("style_prompt", sa.String(length=4000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "assets",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_kind", "assets", ["kind"])
    op.create_index("ix_assets_storage_key", "assets", ["storage_key"], unique=True)

    op.create_table(
        "pages",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_pages_project_id", "pages", ["project_id"])
    op.create_index("ix_pages_page_number", "pages", ["page_number"])

    op.create_table(
        "panels",
        uuid_column("id", primary_key=True),
        uuid_column("page_id", sa.ForeignKey("pages.id"), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.String(length=4000), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_panels_page_id", "panels", ["page_id"])

    op.create_table(
        "generation_jobs",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=True),
        uuid_column("page_id", sa.ForeignKey("pages.id"), nullable=True),
        uuid_column("panel_id", sa.ForeignKey("panels.id"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=4000), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_generation_jobs_project_id", "generation_jobs", ["project_id"])
    op.create_index("ix_generation_jobs_page_id", "generation_jobs", ["page_id"])
    op.create_index("ix_generation_jobs_panel_id", "generation_jobs", ["panel_id"])
    op.create_index("ix_generation_jobs_provider", "generation_jobs", ["provider"])
    op.create_index("ix_generation_jobs_job_type", "generation_jobs", ["job_type"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    op.create_table(
        "renders",
        uuid_column("id", primary_key=True),
        uuid_column("job_id", sa.ForeignKey("generation_jobs.id"), nullable=False),
        uuid_column("panel_id", sa.ForeignKey("panels.id"), nullable=False),
        uuid_column("asset_id", sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_renders_job_id", "renders", ["job_id"], unique=True)
    op.create_index("ix_renders_panel_id", "renders", ["panel_id"])
    op.create_index("ix_renders_asset_id", "renders", ["asset_id"])
    op.create_index("ix_renders_storage_key", "renders", ["storage_key"])


def downgrade() -> None:
    op.drop_table("renders")
    op.drop_table("generation_jobs")
    op.drop_table("panels")
    op.drop_table("pages")
    op.drop_table("assets")
    op.drop_table("projects")
