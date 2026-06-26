from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class Project(TimestampMixin, table=True):
    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_user_id: str = Field(default="local-dev", max_length=160, index=True)
    name: str = Field(min_length=1, max_length=160, index=True)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    style_prompt: str | None = Field(default=None, max_length=4000)
    status: str = Field(default="draft", max_length=32, index=True)
    active_style_bible_id: uuid.UUID | None = Field(default=None, index=True)
    allow_training: bool = Field(default=False, index=True)
    allow_product_improvement: bool = Field(default=False, index=True)
    data_collection_notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class Asset(TimestampMixin, table=True):
    __tablename__ = "assets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    filename: str = Field(max_length=255)
    kind: str = Field(default="source", max_length=64, index=True)
    content_type: str = Field(max_length=128)
    size_bytes: int = Field(ge=0)
    storage_key: str = Field(max_length=1024, unique=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class AssetProvenance(TimestampMixin, table=True):
    __tablename__ = "asset_provenance"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    asset_id: uuid.UUID = Field(foreign_key="assets.id", unique=True, index=True)
    source_type: str = Field(max_length=40, index=True)
    creator_user_id: str | None = Field(default=None, max_length=160, index=True)
    provider_name: str | None = Field(default=None, max_length=120, index=True)
    model_name: str | None = Field(default=None, max_length=160)
    prompt_id: str | None = Field(default=None, max_length=160, index=True)
    generation_job_id: uuid.UUID | None = Field(default=None, foreign_key="generation_jobs.id", index=True)
    uploaded_filename: str | None = Field(default=None, max_length=255)
    declared_rights: str = Field(default="", sa_column=Column(Text, nullable=False))
    license_type: str = Field(default="project_generated", max_length=120, index=True)
    allow_training: bool = Field(default=False, index=True)
    allow_commercial_use: bool = Field(default=True, index=True)
    ai_disclosure_required: bool = Field(default=False, index=True)


class RightsDeclaration(TimestampMixin, table=True):
    __tablename__ = "rights_declarations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", unique=True, index=True)
    user_confirms_upload_rights: bool = Field(default=False, index=True)
    user_confirms_no_unlicensed_ip: bool = Field(default=False, index=True)
    user_confirms_review_required_before_publish: bool = Field(default=True, index=True)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class ProjectPublishingMetadata(TimestampMixin, table=True):
    __tablename__ = "project_publishing_metadata"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", unique=True, index=True)
    title: str = Field(default="", max_length=240, index=True)
    subtitle: str = Field(default="", max_length=240)
    author_name: str = Field(default="", max_length=240, index=True)
    publisher: str = Field(default="", max_length=240)
    language: str = Field(default="en", max_length=32, index=True)
    synopsis: str = Field(default="", sa_column=Column(Text, nullable=False))
    age_rating: str = Field(default="unrated", max_length=80, index=True)
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    copyright_notice: str = Field(default="", sa_column=Column(Text, nullable=False))
    ai_disclosure_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class FeedbackItem(TimestampMixin, table=True):
    __tablename__ = "feedback_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    page_id: uuid.UUID | None = Field(default=None, foreign_key="pages.id", index=True)
    panel_id: uuid.UUID | None = Field(default=None, foreign_key="panels.id", index=True)
    category: str = Field(default="general", max_length=80, index=True)
    severity: str = Field(default="medium", max_length=32, index=True)
    status: str = Field(default="open", max_length=32, index=True)
    title: str = Field(max_length=240, index=True)
    description: str = Field(sa_column=Column(Text, nullable=False))
    contact_email: str | None = Field(default=None, max_length=320, index=True)
    created_by: str | None = Field(default=None, max_length=160, index=True)
    browser_info: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    context: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    diagnostic_info: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class GenerationFeedback(TimestampMixin, table=True):
    __tablename__ = "generation_feedback"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    target_type: str = Field(max_length=64, index=True)
    target_id: uuid.UUID = Field(index=True)
    rating: int = Field(ge=-1, le=1, index=True)
    issue_type: str | None = Field(default=None, max_length=120, index=True)
    comment: str = Field(default="", sa_column=Column(Text, nullable=False))
    user_correction: str = Field(default="", sa_column=Column(Text, nullable=False))
    before_snapshot_id: uuid.UUID | None = Field(default=None, index=True)
    after_snapshot_id: uuid.UUID | None = Field(default=None, index=True)
    allow_use_for_product_improvement: bool = Field(default=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PageRating(TimestampMixin, table=True):
    __tablename__ = "page_ratings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    page_id: uuid.UUID = Field(foreign_key="pages.id", index=True)
    feedback_id: uuid.UUID | None = Field(default=None, foreign_key="generation_feedback.id", index=True)
    rating: int = Field(ge=-1, le=1, index=True)
    issue_type: str | None = Field(default=None, max_length=120, index=True)
    comment: str = Field(default="", sa_column=Column(Text, nullable=False))
    allow_use_for_product_improvement: bool = Field(default=False, index=True)


class PanelRating(TimestampMixin, table=True):
    __tablename__ = "panel_ratings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    panel_id: uuid.UUID = Field(foreign_key="panels.id", index=True)
    feedback_id: uuid.UUID | None = Field(default=None, foreign_key="generation_feedback.id", index=True)
    rating: int = Field(ge=-1, le=1, index=True)
    issue_type: str | None = Field(default=None, max_length=120, index=True)
    comment: str = Field(default="", sa_column=Column(Text, nullable=False))
    allow_use_for_product_improvement: bool = Field(default=False, index=True)


class ExportRating(TimestampMixin, table=True):
    __tablename__ = "export_ratings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    export_id: uuid.UUID = Field(foreign_key="exports.id", index=True)
    feedback_id: uuid.UUID | None = Field(default=None, foreign_key="generation_feedback.id", index=True)
    rating: int = Field(ge=-1, le=1, index=True)
    issue_type: str | None = Field(default=None, max_length=120, index=True)
    comment: str = Field(default="", sa_column=Column(Text, nullable=False))
    allow_use_for_product_improvement: bool = Field(default=False, index=True)


class UserCorrection(TimestampMixin, table=True):
    __tablename__ = "user_corrections"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    feedback_id: uuid.UUID | None = Field(default=None, foreign_key="generation_feedback.id", index=True)
    target_type: str = Field(max_length=64, index=True)
    target_id: uuid.UUID = Field(index=True)
    correction_text: str = Field(sa_column=Column(Text, nullable=False))
    before_snapshot_id: uuid.UUID | None = Field(default=None, index=True)
    after_snapshot_id: uuid.UUID | None = Field(default=None, index=True)
    allow_use_for_product_improvement: bool = Field(default=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class EvalRun(TimestampMixin, table=True):
    __tablename__ = "eval_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(default="manual", max_length=240, index=True)
    scenario: str = Field(default="all", max_length=160, index=True)
    provider: str = Field(default="mock", max_length=80, index=True)
    status: str = Field(default="succeeded", max_length=32, index=True)
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    completed_at: datetime | None = Field(default=None, nullable=True)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    report_path: str | None = Field(default=None, max_length=1000)


class EvalMetricSnapshot(TimestampMixin, table=True):
    __tablename__ = "eval_metric_snapshots"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    eval_run_id: uuid.UUID | None = Field(default=None, foreign_key="eval_runs.id", index=True)
    metric_name: str = Field(max_length=160, index=True)
    metric_value: float = Field(default=0.0)
    dimensions: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    captured_at: datetime = Field(default_factory=utc_now, nullable=False, index=True)


class Page(TimestampMixin, table=True):
    __tablename__ = "pages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    page_number: int = Field(ge=1, index=True)
    width: int = Field(default=1600, ge=1)
    height: int = Field(default=2400, ge=1)
    layout_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class LayoutTemplate(TimestampMixin, table=True):
    __tablename__ = "layout_templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    name: str = Field(max_length=200, index=True)
    page_type: str = Field(default="standard", max_length=64, index=True)
    panel_count: int = Field(default=1, ge=1, index=True)
    reading_direction: str = Field(default="rtl", max_length=16, index=True)
    emotional_use: str = Field(default="", sa_column=Column(Text, nullable=False))
    action_level: str = Field(default="medium", max_length=64, index=True)
    density: str = Field(default="medium", max_length=64, index=True)
    layout_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class Panel(TimestampMixin, table=True):
    __tablename__ = "panels"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    page_id: uuid.UUID = Field(foreign_key="pages.id", index=True)
    x: int = Field(default=80, ge=0)
    y: int = Field(default=80, ge=0)
    width: int = Field(default=640, ge=1)
    height: int = Field(default=480, ge=1)
    polygon: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    reading_order: int = Field(default=1, ge=1, index=True)
    prompt: str | None = Field(default=None, max_length=4000)


class Bubble(TimestampMixin, table=True):
    __tablename__ = "bubbles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    panel_id: uuid.UUID = Field(foreign_key="panels.id", index=True)
    kind: str = Field(default="speech", max_length=32, index=True)
    bubble_type: str = Field(default="speech", max_length=32, index=True)
    speaker_character_id: uuid.UUID | None = Field(default=None, foreign_key="character_cards.id", index=True)
    x: int = Field(default=120, ge=0)
    y: int = Field(default=120, ge=0)
    width: int = Field(default=260, ge=1)
    height: int = Field(default=120, ge=1)
    text: str = Field(max_length=2000)
    language: str = Field(default="en", max_length=16, index=True)
    reading_direction: str = Field(default="rtl", max_length=16, index=True)
    shape: str = Field(default="oval", max_length=64)
    position: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    size: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    tail_target: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    font_family: str = Field(default="Manga Temple", max_length=160)
    font_size: int = Field(default=24, ge=1)
    font_weight: str = Field(default="regular", max_length=40)
    text_align: str = Field(default="center", max_length=24)
    vertical_text: bool = Field(default=False, index=True)
    z_index: int = Field(default=0, index=True)
    locked: bool = Field(default=False, index=True)


class SFXElement(TimestampMixin, table=True):
    __tablename__ = "sfx_elements"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    page_id: uuid.UUID = Field(foreign_key="pages.id", index=True)
    panel_id: uuid.UUID | None = Field(default=None, foreign_key="panels.id", index=True)
    text: str = Field(max_length=1000)
    meaning: str = Field(default="", max_length=1000)
    style: str = Field(default="impact", max_length=120, index=True)
    position: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    size: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    rotation: float = Field(default=0.0)
    warp_style: str = Field(default="none", max_length=120)
    stroke_width: float = Field(default=4.0, ge=0)
    fill: str = Field(default="#ffffff", max_length=32)
    outline: str = Field(default="#111111", max_length=32)
    z_index: int = Field(default=10, index=True)
    locked: bool = Field(default=False, index=True)


class CommandHistory(TimestampMixin, table=True):
    __tablename__ = "command_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    scope_type: str = Field(max_length=32, index=True)
    scope_id: str = Field(max_length=80, index=True)
    command: str = Field(sa_column=Column(Text, nullable=False))
    intent: str = Field(default="", max_length=120, index=True)
    target_type: str = Field(default="", max_length=32, index=True)
    target_id: str = Field(default="", max_length=80, index=True)
    proposed_actions: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    executed_actions: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    requires_confirmation: bool = Field(default=False, index=True)
    confirmed: bool = Field(default=False, index=True)
    risk_level: str = Field(default="low", max_length=32, index=True)
    status: str = Field(default="interpreted", max_length=32, index=True)
    summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    version_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class GenerationJob(TimestampMixin, table=True):
    __tablename__ = "generation_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    page_id: uuid.UUID | None = Field(default=None, foreign_key="pages.id", index=True)
    panel_id: uuid.UUID | None = Field(default=None, foreign_key="panels.id", index=True)
    provider: str = Field(default="mock", max_length=64, index=True)
    job_type: str = Field(default="render_panel", max_length=64, index=True)
    status: str = Field(default="queued", max_length=32, index=True)
    input_payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, max_length=4000)


class JobEvent(TimestampMixin, table=True):
    __tablename__ = "job_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="generation_jobs.id", index=True)
    event_type: str = Field(max_length=80, index=True)
    message: str = Field(default="", max_length=1000)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PromptTemplate(TimestampMixin, table=True):
    __tablename__ = "prompt_templates"

    id: str = Field(primary_key=True, max_length=160)
    name: str = Field(max_length=240)
    version: str = Field(max_length=80, index=True)
    task_type: str = Field(max_length=80, index=True)
    system_prompt: str = Field(sa_column=Column(Text, nullable=False))
    user_prompt_template: str = Field(sa_column=Column(Text, nullable=False))
    output_schema_name: str = Field(max_length=160, index=True)
    default_options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    safety_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    changelog: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class AITaskRun(TimestampMixin, table=True):
    __tablename__ = "ai_task_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    prompt_template_id: str = Field(foreign_key="prompt_templates.id", max_length=160, index=True)
    task_type: str = Field(max_length=80, index=True)
    status: str = Field(default="queued", max_length=32, index=True)
    provider: str = Field(default="mock", max_length=80, index=True)
    model: str | None = Field(default=None, max_length=160)
    schema_name: str = Field(max_length=160, index=True)
    schema_version: str = Field(default="1", max_length=80)
    raw_input: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    raw_output: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    parsed_output: dict | list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    token_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    cost_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    attempt_count: int = Field(default=0, ge=0)


class Render(TimestampMixin, table=True):
    __tablename__ = "renders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="generation_jobs.id", unique=True, index=True)
    panel_id: uuid.UUID = Field(foreign_key="panels.id", index=True)
    asset_id: uuid.UUID | None = Field(default=None, foreign_key="assets.id", index=True)
    storage_key: str = Field(max_length=1024, index=True)
    public_url: str | None = Field(default=None, max_length=2048)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    mime_type: str = Field(default="image/png", max_length=128)


class PanelRenderPrompt(TimestampMixin, table=True):
    __tablename__ = "panel_render_prompts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    panel_id: uuid.UUID = Field(foreign_key="panels.id", index=True)
    prompt_version: str = Field(default="panel-render-director-v1", max_length=120, index=True)
    provider_name: str = Field(default="mock", max_length=64, index=True)
    positive_prompt: str = Field(sa_column=Column(Text, nullable=False))
    negative_prompt: str = Field(default="", sa_column=Column(Text, nullable=False))
    structured_context: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    reference_pack: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    size: str = Field(max_length=32)
    seed: int | None = Field(default=None, index=True)
    quality_mode: str = Field(default="draft", max_length=32, index=True)


class QAReport(TimestampMixin, table=True):
    __tablename__ = "qa_reports"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    target_type: str = Field(max_length=32, index=True)
    target_id: uuid.UUID = Field(index=True)
    issue_code: str | None = Field(default=None, max_length=120, index=True)
    issue_category: str | None = Field(default=None, max_length=64, index=True)
    severity: str | None = Field(default=None, max_length=32, index=True)
    confidence: float = Field(default=1.0, ge=0, le=1)
    page_id: uuid.UUID | None = Field(default=None, foreign_key="pages.id", index=True)
    panel_id: uuid.UUID | None = Field(default=None, foreign_key="panels.id", index=True)
    auto_fix_available: bool = Field(default=False, index=True)
    auto_fix_action: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    overall_score: int = Field(default=0, ge=0, le=100)
    scores: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    issues: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    recommendations: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    blocking: bool = Field(default=False, index=True)


class ProjectExport(TimestampMixin, table=True):
    __tablename__ = "exports"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    format: str = Field(max_length=32, index=True)
    status: str = Field(default="queued", max_length=32, index=True)
    file_asset_id: uuid.UUID | None = Field(default=None, foreign_key="assets.id", index=True)
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, max_length=4000)


class VersionRecordBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    parent_id: uuid.UUID | None = Field(default=None, index=True)
    entity_type: str = Field(max_length=64, index=True)
    entity_id: uuid.UUID = Field(index=True)
    snapshot_json: dict = Field(default_factory=dict, sa_type=JSON, nullable=False)
    asset_ids: list[str] = Field(default_factory=list, sa_type=JSON, nullable=False)
    label: str = Field(default="", max_length=240, index=True)
    created_by: str = Field(default="system", max_length=160, index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False, index=True)
    reason: str = Field(default="", sa_type=Text, nullable=False)
    is_checkpoint: bool = Field(default=False, index=True)


class ProjectVersion(VersionRecordBase, table=True):
    __tablename__ = "project_versions"


class PageVersion(VersionRecordBase, table=True):
    __tablename__ = "page_versions"


class PanelVersion(VersionRecordBase, table=True):
    __tablename__ = "panel_versions"


class LayoutVersion(VersionRecordBase, table=True):
    __tablename__ = "layout_versions"


class RenderVersion(VersionRecordBase, table=True):
    __tablename__ = "render_versions"


class LetteringVersion(VersionRecordBase, table=True):
    __tablename__ = "lettering_versions"


class StoryBibleVersion(VersionRecordBase, table=True):
    __tablename__ = "story_bible_versions"


class StyleBibleVersion(VersionRecordBase, table=True):
    __tablename__ = "style_bible_versions"


class CharacterCardVersion(VersionRecordBase, table=True):
    __tablename__ = "character_card_versions"


class ExportVersion(VersionRecordBase, table=True):
    __tablename__ = "export_versions"


class StoryBible(TimestampMixin, table=True):
    __tablename__ = "story_bibles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    logline: str = Field(max_length=1000)
    synopsis: str = Field(max_length=8000)
    genre: str = Field(max_length=120)
    themes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    target_audience: str = Field(max_length=240)
    tone: str = Field(max_length=240)
    main_conflict: str = Field(max_length=2000)
    world_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    chapter_outline: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    continuity_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class Character(TimestampMixin, table=True):
    __tablename__ = "characters"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    story_bible_id: uuid.UUID | None = Field(default=None, foreign_key="story_bibles.id", index=True)
    name: str = Field(max_length=160, index=True)
    role: str = Field(max_length=160)
    description: str = Field(max_length=2000)
    traits: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    visual_notes: str | None = Field(default=None, max_length=2000)


class CharacterCard(TimestampMixin, table=True):
    __tablename__ = "character_cards"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    name: str = Field(max_length=160, index=True)
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    age_range: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=160)
    personality: str = Field(default="", max_length=3000)
    face_description: str = Field(default="", max_length=2000)
    hair_description: str = Field(default="", max_length=2000)
    eye_description: str = Field(default="", max_length=2000)
    body_type: str = Field(default="", max_length=1000)
    outfit_default: str = Field(default="", max_length=2000)
    accessories: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    scars_marks: str = Field(default="", max_length=2000)
    voice_style: str = Field(default="", max_length=1000)
    forbidden_changes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    continuity_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    canonical_visual_summary: str = Field(default="", max_length=4000)
    silhouette_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    face_anchor_description: str = Field(default="", max_length=2000)
    hair_anchor_description: str = Field(default="", max_length=2000)
    eye_anchor_description: str = Field(default="", max_length=2000)
    body_anchor_description: str = Field(default="", max_length=2000)
    outfit_anchor_description: str = Field(default="", max_length=2000)
    color_notes_even_for_bw: str = Field(default="", max_length=2000)
    recurring_props: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    allowed_variations: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    forbidden_variations: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    current_story_state: str = Field(default="", max_length=2000)
    injury_state: str = Field(default="", max_length=2000)
    emotional_baseline: str = Field(default="", max_length=2000)
    reference_asset_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    approved_panel_asset_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class CharacterState(TimestampMixin, table=True):
    __tablename__ = "character_states"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    character_id: uuid.UUID = Field(foreign_key="character_cards.id", index=True)
    chapter_id: uuid.UUID = Field(foreign_key="chapters.id", index=True)
    scene_id: uuid.UUID = Field(foreign_key="scenes.id", index=True)
    page_id: uuid.UUID | None = Field(default=None, foreign_key="pages.id", index=True)
    outfit_state: str = Field(default="", max_length=2000)
    injury_state: str = Field(default="", max_length=2000)
    emotional_state: str = Field(default="", max_length=2000)
    prop_state: str = Field(default="", max_length=2000)
    visibility_notes: str = Field(default="", max_length=2000)
    continuity_notes: str = Field(default="", max_length=3000)


class CharacterReferenceAsset(TimestampMixin, table=True):
    __tablename__ = "character_reference_assets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    character_card_id: uuid.UUID = Field(foreign_key="character_cards.id", index=True)
    filename: str = Field(max_length=255)
    kind: str = Field(default="reference", max_length=64, index=True)
    content_type: str = Field(max_length=128)
    size_bytes: int = Field(default=0, ge=0)
    storage_key: str = Field(max_length=1024, unique=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class ExpressionSheet(TimestampMixin, table=True):
    __tablename__ = "expression_sheets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    character_card_id: uuid.UUID = Field(foreign_key="character_cards.id", index=True)
    name: str = Field(default="Default Expression Sheet", max_length=200)
    expressions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    asset_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class OutfitVariant(TimestampMixin, table=True):
    __tablename__ = "outfit_variants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    character_card_id: uuid.UUID = Field(foreign_key="character_cards.id", index=True)
    name: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    accessories: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    continuity_notes: str = Field(default="", max_length=2000)


class Location(TimestampMixin, table=True):
    __tablename__ = "locations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    story_bible_id: uuid.UUID | None = Field(default=None, foreign_key="story_bibles.id", index=True)
    name: str = Field(max_length=160, index=True)
    description: str = Field(max_length=2000)
    visual_notes: str | None = Field(default=None, max_length=2000)
    rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class KeyObject(TimestampMixin, table=True):
    __tablename__ = "key_objects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    story_bible_id: uuid.UUID | None = Field(default=None, foreign_key="story_bibles.id", index=True)
    name: str = Field(max_length=160, index=True)
    description: str = Field(max_length=2000)
    significance: str = Field(max_length=2000)
    visual_notes: str | None = Field(default=None, max_length=2000)


class StyleBible(TimestampMixin, table=True):
    __tablename__ = "style_bibles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    story_bible_id: uuid.UUID | None = Field(default=None, foreign_key="story_bibles.id", index=True)
    name: str = Field(default="Untitled Style Bible", max_length=200, index=True)
    style_name: str = Field(default="", max_length=200, index=True)
    style_intent: str = Field(default="", max_length=3000)
    line_weight: str = Field(default="", max_length=1000)
    line_variation: str = Field(default="", max_length=1000)
    line_texture: str = Field(default="", max_length=1000)
    face_shape_language: str = Field(default="", max_length=2000)
    eye_design_language: str = Field(default="", max_length=2000)
    nose_mouth_simplification: str = Field(default="", max_length=2000)
    anatomy_proportions: str = Field(default="", max_length=2000)
    hair_rendering: str = Field(default="", max_length=2000)
    clothing_fold_style: str = Field(default="", max_length=2000)
    background_density: str = Field(default="", max_length=2000)
    architecture_detail: str = Field(default="", max_length=2000)
    shadow_strategy: str = Field(default="", max_length=2000)
    screentone_strategy: str = Field(default="", max_length=2000)
    hatching_strategy: str = Field(default="", max_length=2000)
    black_fill_ratio: str = Field(default="", max_length=1000)
    speedline_style: str = Field(default="", max_length=2000)
    impact_frame_style: str = Field(default="", max_length=2000)
    panel_border_style: str = Field(default="", max_length=2000)
    gutter_style: str = Field(default="", max_length=2000)
    sfx_shape_language: str = Field(default="", max_length=2000)
    bubble_style: str = Field(default="", max_length=2000)
    emotional_visual_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    positive_prompt_fragments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    negative_prompt_fragments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    forbidden_artist_references: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    forbidden_franchise_references: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    linework: str = Field(default="", max_length=2000)
    screentone: str = Field(default="", max_length=2000)
    hatching: str = Field(default="", max_length=2000)
    black_white_balance: str = Field(default="", max_length=2000)
    face_language: str = Field(default="", max_length=2000)
    anatomy_style: str = Field(default="", max_length=2000)
    background_detail: str = Field(default="", max_length=2000)
    panel_rhythm: str = Field(default="", max_length=2000)
    sfx_style: str = Field(default="", max_length=2000)
    typography_notes: str = Field(default="", max_length=2000)
    forbidden_references: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    prompt_style_positive: str = Field(default="", max_length=4000)
    prompt_style_negative: str = Field(default="", max_length=4000)
    visual_style: str = Field(default="", max_length=2000)
    line_art: str = Field(default="", max_length=1000)
    palette: str = Field(default="", max_length=1000)
    paneling: str = Field(default="", max_length=1000)
    lettering: str = Field(default="", max_length=1000)
    negative_prompts: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class StyleSampleAsset(TimestampMixin, table=True):
    __tablename__ = "style_sample_assets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    style_bible_id: uuid.UUID = Field(foreign_key="style_bibles.id", index=True)
    filename: str = Field(max_length=255)
    kind: str = Field(default="style_sample", max_length=64, index=True)
    content_type: str = Field(max_length=128)
    size_bytes: int = Field(default=0, ge=0)
    storage_key: str = Field(max_length=1024, unique=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class Chapter(TimestampMixin, table=True):
    __tablename__ = "chapters"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    story_bible_id: uuid.UUID | None = Field(default=None, foreign_key="story_bibles.id", index=True)
    chapter_number: int = Field(ge=1, index=True)
    title: str = Field(max_length=240)
    summary: str = Field(max_length=4000)
    goal: str = Field(max_length=2000)
    status: str = Field(default="planned", max_length=32, index=True)


class Scene(TimestampMixin, table=True):
    __tablename__ = "scenes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chapter_id: uuid.UUID = Field(foreign_key="chapters.id", index=True)
    scene_order: int = Field(ge=1, index=True)
    title: str = Field(max_length=240)
    summary: str = Field(max_length=3000)
    location_name: str | None = Field(default=None, max_length=160)
    emotional_turn: str | None = Field(default=None, max_length=1000)
    characters: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class PagePlan(TimestampMixin, table=True):
    __tablename__ = "page_plans"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    chapter_id: uuid.UUID = Field(foreign_key="chapters.id", index=True)
    page_number: int = Field(ge=1, index=True)
    summary: str = Field(max_length=3000)
    pacing: str = Field(max_length=1000)
    panel_count: int = Field(default=0, ge=0)
    page_role: str = Field(default="story_progression", max_length=120, index=True)
    emotional_intensity: int = Field(default=50, ge=0, le=100, index=True)
    action_intensity: int = Field(default=30, ge=0, le=100, index=True)
    dialogue_density: int = Field(default=30, ge=0, le=100, index=True)
    silence_level: int = Field(default=20, ge=0, le=100, index=True)
    reveal_level: int = Field(default=20, ge=0, le=100, index=True)
    page_turn_importance: int = Field(default=20, ge=0, le=100, index=True)
    recommended_page_type: str = Field(default="standard", max_length=64, index=True)
    pacing_notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class PanelPlan(TimestampMixin, table=True):
    __tablename__ = "panel_plans"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    page_plan_id: uuid.UUID = Field(foreign_key="page_plans.id", index=True)
    panel_order: int = Field(ge=1, index=True)
    story_beat: str = Field(max_length=2000)
    shot_type: str = Field(max_length=160)
    camera_angle: str = Field(max_length=160)
    characters: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    location: str | None = Field(default=None, max_length=160)
    dialogue: str | None = Field(default=None, max_length=2000)
    narration: str | None = Field(default=None, max_length=2000)
    visual_notes: str = Field(max_length=3000)
    emotional_intent: str = Field(max_length=1000)
    beat_importance: int = Field(default=50, ge=0, le=100, index=True)
    time_duration: str = Field(default="normal", max_length=80, index=True)
    camera_motion: str = Field(default="still", max_length=120)
    motion_intensity: int = Field(default=20, ge=0, le=100, index=True)
    dialogue_weight: int = Field(default=0, ge=0, le=100, index=True)
    silence: bool = Field(default=False, index=True)
    impact_level: int = Field(default=20, ge=0, le=100, index=True)
    recommended_panel_size: str = Field(default="medium", max_length=40, index=True)
    transition_type: str = Field(default="moment_to_moment", max_length=80, index=True)
