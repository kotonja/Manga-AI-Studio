"""manga qa reports

Revision ID: 0005_manga_qa
Revises: 0004_character_style_labs
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_manga_qa"
down_revision = "0004_character_style_labs"
branch_labels = None
depends_on = None


def uuid_column(name: str, *args, **kwargs):
    return sa.Column(name, postgresql.UUID(as_uuid=True), *args, **kwargs)


def upgrade() -> None:
    op.create_table(
        "qa_reports",
        uuid_column("id", primary_key=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        uuid_column("target_id", nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_qa_reports_target_type", "qa_reports", ["target_type"])
    op.create_index("ix_qa_reports_target_id", "qa_reports", ["target_id"])
    op.create_index("ix_qa_reports_blocking", "qa_reports", ["blocking"])


def downgrade() -> None:
    op.drop_index("ix_qa_reports_blocking", table_name="qa_reports")
    op.drop_index("ix_qa_reports_target_id", table_name="qa_reports")
    op.drop_index("ix_qa_reports_target_type", table_name="qa_reports")
    op.drop_table("qa_reports")
