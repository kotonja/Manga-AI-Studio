"""Add creator rights and asset provenance tables.

Revision ID: 0017_creator_rights_provenance
Revises: 0016_versioning
Create Date: 2026-06-25 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_creator_rights_provenance"
down_revision = "0016_versioning"
branch_labels = None
depends_on = None


ASSET_SOURCE_TYPES = (
    "user_upload",
    "ai_generated",
    "stock_licensed",
    "internal_mock",
    "imported",
)


def upgrade() -> None:
    op.create_table(
        "asset_provenance",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("creator_user_id", sa.String(length=160), nullable=True),
        sa.Column("provider_name", sa.String(length=120), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("prompt_id", sa.String(length=160), nullable=True),
        sa.Column("generation_job_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_filename", sa.String(length=255), nullable=True),
        sa.Column("declared_rights", sa.Text(), nullable=False),
        sa.Column("license_type", sa.String(length=120), nullable=False),
        sa.Column("allow_training", sa.Boolean(), nullable=False),
        sa.Column("allow_commercial_use", sa.Boolean(), nullable=False),
        sa.Column("ai_disclosure_required", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            f"source_type IN {ASSET_SOURCE_TYPES!r}",
            name="ck_asset_provenance_source_type",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", name="uq_asset_provenance_asset_id"),
    )
    op.create_index(op.f("ix_asset_provenance_asset_id"), "asset_provenance", ["asset_id"], unique=True)
    op.create_index(op.f("ix_asset_provenance_source_type"), "asset_provenance", ["source_type"], unique=False)
    op.create_index(op.f("ix_asset_provenance_creator_user_id"), "asset_provenance", ["creator_user_id"], unique=False)
    op.create_index(op.f("ix_asset_provenance_provider_name"), "asset_provenance", ["provider_name"], unique=False)
    op.create_index(op.f("ix_asset_provenance_prompt_id"), "asset_provenance", ["prompt_id"], unique=False)
    op.create_index(op.f("ix_asset_provenance_generation_job_id"), "asset_provenance", ["generation_job_id"], unique=False)
    op.create_index(op.f("ix_asset_provenance_license_type"), "asset_provenance", ["license_type"], unique=False)
    op.create_index(op.f("ix_asset_provenance_allow_training"), "asset_provenance", ["allow_training"], unique=False)
    op.create_index(op.f("ix_asset_provenance_allow_commercial_use"), "asset_provenance", ["allow_commercial_use"], unique=False)
    op.create_index(op.f("ix_asset_provenance_ai_disclosure_required"), "asset_provenance", ["ai_disclosure_required"], unique=False)

    op.create_table(
        "rights_declarations",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_confirms_upload_rights", sa.Boolean(), nullable=False),
        sa.Column("user_confirms_no_unlicensed_ip", sa.Boolean(), nullable=False),
        sa.Column("user_confirms_review_required_before_publish", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_rights_declarations_project_id"),
    )
    op.create_index(op.f("ix_rights_declarations_project_id"), "rights_declarations", ["project_id"], unique=True)
    op.create_index(
        op.f("ix_rights_declarations_user_confirms_upload_rights"),
        "rights_declarations",
        ["user_confirms_upload_rights"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rights_declarations_user_confirms_no_unlicensed_ip"),
        "rights_declarations",
        ["user_confirms_no_unlicensed_ip"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rights_declarations_user_confirms_review_required_before_publish"),
        "rights_declarations",
        ["user_confirms_review_required_before_publish"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rights_declarations_user_confirms_review_required_before_publish"), table_name="rights_declarations")
    op.drop_index(op.f("ix_rights_declarations_user_confirms_no_unlicensed_ip"), table_name="rights_declarations")
    op.drop_index(op.f("ix_rights_declarations_user_confirms_upload_rights"), table_name="rights_declarations")
    op.drop_index(op.f("ix_rights_declarations_project_id"), table_name="rights_declarations")
    op.drop_table("rights_declarations")

    op.drop_index(op.f("ix_asset_provenance_ai_disclosure_required"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_allow_commercial_use"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_allow_training"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_license_type"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_generation_job_id"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_prompt_id"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_provider_name"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_creator_user_id"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_source_type"), table_name="asset_provenance")
    op.drop_index(op.f("ix_asset_provenance_asset_id"), table_name="asset_provenance")
    op.drop_table("asset_provenance")
