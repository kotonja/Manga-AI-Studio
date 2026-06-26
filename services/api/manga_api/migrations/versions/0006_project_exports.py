"""project exports

Revision ID: 0006_project_exports
Revises: 0005_manga_qa
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_project_exports"
down_revision = "0005_manga_qa"
branch_labels = None
depends_on = None


def uuid_column(name: str, *args, **kwargs):
    return sa.Column(name, postgresql.UUID(as_uuid=True), *args, **kwargs)


def upgrade() -> None:
    op.create_table(
        "exports",
        uuid_column("id", primary_key=True),
        uuid_column("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        uuid_column("file_asset_id", sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exports_project_id", "exports", ["project_id"])
    op.create_index("ix_exports_format", "exports", ["format"])
    op.create_index("ix_exports_status", "exports", ["status"])
    op.create_index("ix_exports_file_asset_id", "exports", ["file_asset_id"])


def downgrade() -> None:
    op.drop_index("ix_exports_file_asset_id", table_name="exports")
    op.drop_index("ix_exports_status", table_name="exports")
    op.drop_index("ix_exports_format", table_name="exports")
    op.drop_index("ix_exports_project_id", table_name="exports")
    op.drop_table("exports")
