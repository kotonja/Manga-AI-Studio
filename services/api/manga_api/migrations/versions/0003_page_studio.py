"""page studio layout

Revision ID: 0003_page_studio
Revises: 0002_story_engine
Create Date: 2026-06-24 23:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_page_studio"
down_revision = "0002_story_engine"
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
    op.add_column("pages", sa.Column("layout_json", sa.JSON(), nullable=True))
    op.execute("UPDATE pages SET layout_json = '{}' WHERE layout_json IS NULL")
    op.alter_column("pages", "layout_json", nullable=False)

    op.add_column("panels", sa.Column("polygon", sa.JSON(), nullable=True))
    op.add_column("panels", sa.Column("reading_order", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE panels
        SET polygon = json_build_array(
            json_build_object('x', x, 'y', y),
            json_build_object('x', x + width, 'y', y),
            json_build_object('x', x + width, 'y', y + height),
            json_build_object('x', x, 'y', y + height)
        )
        WHERE polygon IS NULL
        """
    )
    op.execute("UPDATE panels SET reading_order = 1 WHERE reading_order IS NULL")
    op.alter_column("panels", "polygon", nullable=False)
    op.alter_column("panels", "reading_order", nullable=False)
    op.create_index("ix_panels_reading_order", "panels", ["reading_order"])

    op.create_table(
        "bubbles",
        uuid_column("id", primary_key=True),
        uuid_column("panel_id", sa.ForeignKey("panels.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_bubbles_panel_id", "bubbles", ["panel_id"])
    op.create_index("ix_bubbles_kind", "bubbles", ["kind"])


def downgrade() -> None:
    op.drop_table("bubbles")
    op.drop_index("ix_panels_reading_order", table_name="panels")
    op.drop_column("panels", "reading_order")
    op.drop_column("panels", "polygon")
    op.drop_column("pages", "layout_json")
