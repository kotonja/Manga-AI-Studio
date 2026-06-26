"""Add advanced QA issue metadata.

Revision ID: 0015_advanced_qa_autofix
Revises: 0014_professional_lettering
Create Date: 2026-06-25 19:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_advanced_qa_autofix"
down_revision = "0014_professional_lettering"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("qa_reports", sa.Column("issue_code", sa.String(length=120), nullable=True))
    op.add_column("qa_reports", sa.Column("issue_category", sa.String(length=64), nullable=True))
    op.add_column("qa_reports", sa.Column("severity", sa.String(length=32), nullable=True))
    op.add_column("qa_reports", sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("qa_reports", sa.Column("page_id", sa.Uuid(), nullable=True))
    op.add_column("qa_reports", sa.Column("panel_id", sa.Uuid(), nullable=True))
    op.add_column("qa_reports", sa.Column("auto_fix_available", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("qa_reports", sa.Column("auto_fix_action", sa.JSON(), nullable=False, server_default="{}"))
    op.create_foreign_key("fk_qa_reports_page_id", "qa_reports", "pages", ["page_id"], ["id"])
    op.create_foreign_key("fk_qa_reports_panel_id", "qa_reports", "panels", ["panel_id"], ["id"])
    op.create_index(op.f("ix_qa_reports_issue_code"), "qa_reports", ["issue_code"], unique=False)
    op.create_index(op.f("ix_qa_reports_issue_category"), "qa_reports", ["issue_category"], unique=False)
    op.create_index(op.f("ix_qa_reports_severity"), "qa_reports", ["severity"], unique=False)
    op.create_index(op.f("ix_qa_reports_page_id"), "qa_reports", ["page_id"], unique=False)
    op.create_index(op.f("ix_qa_reports_panel_id"), "qa_reports", ["panel_id"], unique=False)
    op.create_index(op.f("ix_qa_reports_auto_fix_available"), "qa_reports", ["auto_fix_available"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_qa_reports_auto_fix_available"), table_name="qa_reports")
    op.drop_index(op.f("ix_qa_reports_panel_id"), table_name="qa_reports")
    op.drop_index(op.f("ix_qa_reports_page_id"), table_name="qa_reports")
    op.drop_index(op.f("ix_qa_reports_severity"), table_name="qa_reports")
    op.drop_index(op.f("ix_qa_reports_issue_category"), table_name="qa_reports")
    op.drop_index(op.f("ix_qa_reports_issue_code"), table_name="qa_reports")
    op.drop_constraint("fk_qa_reports_panel_id", "qa_reports", type_="foreignkey")
    op.drop_constraint("fk_qa_reports_page_id", "qa_reports", type_="foreignkey")
    op.drop_column("qa_reports", "auto_fix_action")
    op.drop_column("qa_reports", "auto_fix_available")
    op.drop_column("qa_reports", "panel_id")
    op.drop_column("qa_reports", "page_id")
    op.drop_column("qa_reports", "confidence")
    op.drop_column("qa_reports", "severity")
    op.drop_column("qa_reports", "issue_category")
    op.drop_column("qa_reports", "issue_code")
