from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


JobStatus = Literal["queued", "running", "succeeded", "failed"]
ReadingDirection = Literal["rtl", "ltr", "vertical-rl"]
BubbleKind = Literal["speech", "thought", "narration", "shout", "whisper", "radio", "monster", "offscreen"]
TextAlign = Literal["left", "center", "right"]
PageType = Literal[
    "standard",
    "splash",
    "double_spread_left",
    "double_spread_right",
    "silent_page",
    "action_sequence",
    "dialogue_scene",
    "reveal_page",
    "comedy_reaction",
    "horror_build",
    "romantic_pause",
    "exposition_page",
]
QATargetType = Literal["project", "page", "panel"]
QAIssueSeverity = Literal["info", "warning", "blocking", "error"]
QAIssueCategory = Literal["layout", "render", "lettering", "continuity", "story", "export", "safety", "style"]
QAExportPreset = Literal["draft", "web", "print"]
ExportFormat = Literal["zip", "pdf", "epub", "layered", "png_sequence", "webtoon", "archive"]
ExportStatus = Literal["queued", "running", "succeeded", "failed"]
AITaskStatus = Literal["queued", "running", "succeeded", "failed"]
AssetSourceType = Literal["user_upload", "ai_generated", "stock_licensed", "internal_mock", "imported"]
LearningTargetType = Literal["story", "character", "panel_render", "page_layout", "export", "style", "page", "panel"]
LearningIssueType = Literal[
    "wrong character",
    "bad hands",
    "bad face",
    "confusing layout",
    "unreadable text",
    "inconsistent style",
    "weak story",
    "wrong tone",
    "export problem",
    "other",
]
SafetyCheckTarget = Literal["text_prompt", "uploaded_image_metadata", "generated_output_metadata", "style_request"]
SafetySeverity = Literal["safe", "warning", "blocked"]
PanelRenderMode = Literal["storyboard", "draft", "final", "ultra"]
PanelRerenderControl = Literal[
    "same_seed",
    "new_seed",
    "preserve_layout",
    "change_camera",
    "change_expression",
    "additional_instruction",
]
CommandScopeType = Literal["project", "chapter", "page", "panel", "bubble", "character", "style"]
CommandRiskLevel = Literal["low", "medium", "high"]
CommandStatus = Literal["interpreted", "executed", "blocked", "failed"]
CommandActionType = Literal[
    "update_story_bible",
    "update_character_state",
    "update_style_dna",
    "suggest_layout",
    "update_layout",
    "update_panel_prompt",
    "rerender_panel",
    "update_bubble_text",
    "move_bubble",
    "run_qa",
    "apply_qa_fixes",
    "compose_page",
    "create_export",
]
AITaskType = Literal[
    "generate_story_bible",
    "generate_character_cards",
    "generate_location_cards",
    "generate_style_bible",
    "generate_style_dna",
    "generate_chapter_plan",
    "generate_page_plan",
    "generate_panel_plan",
    "generate_layout_plan",
    "generate_panel_prompt",
    "generate_bubble_plan",
    "critique_page",
    "critique_panel",
    "repair_invalid_json",
]
DirectorProgressEvent = Literal[
    "queued",
    "generating_story_bible",
    "generating_characters",
    "generating_style",
    "planning_pages",
    "creating_layouts",
    "rendering_panels",
    "composing_pages",
    "running_qa",
    "exporting",
    "creating_project",
    "writing_story_bible",
    "designing_characters",
    "creating_style_dna",
    "drawing_layouts",
    "lettering_pages",
    "composing_final_pages",
    "checking_quality",
    "exporting_files",
    "complete",
    "failed",
]
DirectorQualityMode = Literal["fast", "balanced", "high"]
LONG_FORM_TEXT_MAX_LENGTH = 50_000


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=LONG_FORM_TEXT_MAX_LENGTH)
    style_prompt: str | None = Field(default=None, max_length=4000)
    allow_training: bool | None = None
    allow_product_improvement: bool | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_user_id: str = "local-dev"
    name: str
    description: str | None
    style_prompt: str | None
    status: str
    active_style_bible_id: uuid.UUID | None
    allow_training: bool = False
    allow_product_improvement: bool = False
    data_collection_notes: str = ""
    created_at: datetime
    updated_at: datetime


class ProjectDataControlsUpdate(BaseModel):
    allow_training: bool = False
    allow_product_improvement: bool = False
    data_collection_notes: str = Field(default="", max_length=5000)


class ProjectDataControlsRead(ProjectDataControlsUpdate):
    project_id: uuid.UUID
    collected_by_default: bool = False
    explanation: str


class PageCreate(BaseModel):
    page_number: int | None = Field(default=None, ge=1)
    width: int = Field(default=1600, ge=1)
    height: int = Field(default=2400, ge=1)


class PageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    page_number: int
    width: int
    height: int
    created_at: datetime
    updated_at: datetime


class PanelCreate(BaseModel):
    x: int = Field(default=80, ge=0)
    y: int = Field(default=80, ge=0)
    width: int = Field(default=640, ge=1)
    height: int = Field(default=480, ge=1)
    reading_order: int | None = Field(default=None, ge=1)
    prompt: str | None = Field(default=None, max_length=4000)


class PanelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    x: int
    y: int
    width: int
    height: int
    polygon: list[dict[str, float]]
    reading_order: int
    prompt: str | None
    created_at: datetime
    updated_at: datetime


class PageWithPanels(PageRead):
    panels: list[PanelRead] = Field(default_factory=list)


class ProjectDetail(ProjectRead):
    pages: list[PageWithPanels] = Field(default_factory=list)


class ProjectWorkspaceSummary(BaseModel):
    project_id: uuid.UUID
    active_chapter_title: str | None = None
    page_count: int = 0
    panel_count: int = 0
    rendered_panel_count: int = 0
    render_progress: float = Field(default=0, ge=0, le=1)
    qa_score: int | None = None
    qa_blocking: bool = False
    export_status: str | None = None
    active_job_count: int = 0
    status_chip: str = "Draft"


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    filename: str
    kind: str
    content_type: str
    size_bytes: int
    storage_key: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AssetProvenanceCreate(BaseModel):
    source_type: AssetSourceType
    creator_user_id: str | None = Field(default=None, max_length=160)
    provider_name: str | None = Field(default=None, max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    prompt_id: str | None = Field(default=None, max_length=160)
    generation_job_id: uuid.UUID | None = None
    uploaded_filename: str | None = Field(default=None, max_length=255)
    declared_rights: str = Field(default="", max_length=10_000)
    license_type: str = Field(default="project_generated", max_length=120)
    allow_training: bool = False
    allow_commercial_use: bool = True
    ai_disclosure_required: bool = False


class AssetProvenanceUpdate(BaseModel):
    source_type: AssetSourceType | None = None
    creator_user_id: str | None = Field(default=None, max_length=160)
    provider_name: str | None = Field(default=None, max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    prompt_id: str | None = Field(default=None, max_length=160)
    generation_job_id: uuid.UUID | None = None
    uploaded_filename: str | None = Field(default=None, max_length=255)
    declared_rights: str | None = Field(default=None, max_length=10_000)
    license_type: str | None = Field(default=None, max_length=120)
    allow_training: bool | None = None
    allow_commercial_use: bool | None = None
    ai_disclosure_required: bool | None = None


class AssetProvenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    source_type: AssetSourceType | str
    creator_user_id: str | None
    provider_name: str | None
    model_name: str | None
    prompt_id: str | None
    generation_job_id: uuid.UUID | None
    uploaded_filename: str | None
    declared_rights: str
    license_type: str
    allow_training: bool
    allow_commercial_use: bool
    ai_disclosure_required: bool
    created_at: datetime
    updated_at: datetime


class RightsDeclarationUpsert(BaseModel):
    user_confirms_upload_rights: bool = False
    user_confirms_no_unlicensed_ip: bool = False
    user_confirms_review_required_before_publish: bool = True
    notes: str = Field(default="", max_length=10_000)


class RightsDeclarationRead(RightsDeclarationUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProvenanceAssetRead(BaseModel):
    asset: AssetRead
    provenance: AssetProvenanceRead | None = None


class ProvenanceSummaryRead(BaseModel):
    total_assets: int = 0
    assets_with_provenance: int = 0
    ai_disclosure_required: bool = False
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    missing_provenance_asset_ids: list[uuid.UUID] = Field(default_factory=list)


class ProjectProvenanceRead(BaseModel):
    project_id: uuid.UUID
    rights_declaration: RightsDeclarationRead | None = None
    summary: ProvenanceSummaryRead
    assets: list[ProvenanceAssetRead] = Field(default_factory=list)


class SafetyIssueRead(BaseModel):
    severity: Literal["warning", "error"]
    code: str
    message: str
    field: str | None = None
    matched_text: str | None = None


class SafetyCheckRequest(BaseModel):
    target: SafetyCheckTarget = "text_prompt"
    text: str = Field(default="", max_length=50_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SafetyCheckResult(BaseModel):
    allowed: bool
    severity: SafetySeverity
    issues: list[SafetyIssueRead] = Field(default_factory=list)
    suggested_text: str | None = None
    suggested_metadata: dict[str, Any] = Field(default_factory=dict)


class CompositePageRead(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    project_id: uuid.UUID | None
    filename: str
    storage_key: str
    public_url: str | None
    content_type: str
    size_bytes: int
    width: int
    height: int
    reading_direction: ReadingDirection | str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RenderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    panel_id: uuid.UUID
    asset_id: uuid.UUID | None
    storage_key: str
    public_url: str | None
    width: int
    height: int
    mime_type: str
    created_at: datetime


class PanelRenderPromptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    panel_id: uuid.UUID
    prompt_version: str
    provider_name: str
    positive_prompt: str
    negative_prompt: str
    structured_context: dict[str, Any]
    reference_pack: dict[str, Any]
    size: str
    seed: int | None
    quality_mode: str
    created_at: datetime
    updated_at: datetime


class MockRenderPanelRequest(BaseModel):
    panel_id: uuid.UUID


class RenderPanelRequest(BaseModel):
    panel_id: uuid.UUID
    provider_name: str = Field(default="mock", min_length=1, max_length=64)
    options: dict[str, Any] = Field(default_factory=dict)


class ProviderCapabilitiesRead(BaseModel):
    supports_image_generation: bool
    supports_image_editing: bool
    supports_references: bool
    supports_seeds: bool
    supports_async_jobs: bool


class ProviderResolutionRead(BaseModel):
    width: int
    height: int


class ProviderRead(BaseModel):
    name: str
    display_name: str
    model_name: str | None
    capabilities: ProviderCapabilitiesRead
    max_resolution: ProviderResolutionRead
    requires_env_vars: list[str] = Field(default_factory=list)
    configured: bool
    missing_env_vars: list[str] = Field(default_factory=list)
    cost_warning: str
    notes: str


class ProviderHealthRead(BaseModel):
    name: str
    status: str
    configured: bool
    message: str
    checked_at: str
    details: dict[str, Any] = Field(default_factory=dict)


class PanelRenderRequest(BaseModel):
    provider_name: str = Field(default="mock", min_length=1, max_length=64)
    render_mode: PanelRenderMode = "draft"
    seed: int | None = None
    advanced_prompt_override: str | None = Field(default=None, max_length=50_000)
    additional_user_instruction: str | None = Field(default=None, max_length=5000)
    provider_options: dict[str, Any] = Field(default_factory=dict)


class PanelRerenderRequest(PanelRenderRequest):
    control: PanelRerenderControl = "same_seed"
    camera_instruction: str | None = Field(default=None, max_length=2000)
    expression_instruction: str | None = Field(default=None, max_length=2000)


class PanelRenderDryRunResult(BaseModel):
    panel_id: uuid.UUID
    provider: ProviderRead
    provider_configured: bool
    can_render: bool
    requested_size: str
    quality_mode: str
    estimated_cost: dict[str, Any]
    cost_metadata: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    prompt: PanelRenderPromptRead


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    page_id: uuid.UUID | None
    panel_id: uuid.UUID | None
    provider: str
    job_type: str
    status: JobStatus | str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class GenerationJobDetail(GenerationJobRead):
    render: RenderRead | None = None


class JobRetryRequest(BaseModel):
    provider_name: str | None = Field(default=None, max_length=64)
    use_mock_fallback: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class GenerationJobRetryResult(BaseModel):
    source_job_id: uuid.UUID
    job: GenerationJobRead
    message: str


class PanelRenderStartResult(BaseModel):
    job: GenerationJobRead
    prompt: PanelRenderPromptRead


class PanelRenderHistoryItem(BaseModel):
    render: RenderRead
    job: GenerationJobRead
    prompt: PanelRenderPromptRead | None = None
    asset: AssetRead | None = None
    approved: bool = False


class JobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    event_type: DirectorProgressEvent | str
    message: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PromptTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    task_type: AITaskType | str
    system_prompt: str
    user_prompt_template: str
    output_schema_name: str
    default_options: dict[str, Any]
    safety_notes: str
    changelog: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class AITaskRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prompt_template_id: str
    task_type: AITaskType | str
    status: AITaskStatus | str
    provider: str
    model: str | None
    schema_name: str
    schema_version: str
    raw_input: dict[str, Any]
    raw_output: str | None
    parsed_output: dict[str, Any] | list[Any] | None
    token_metadata: dict[str, Any]
    cost_metadata: dict[str, Any]
    error_message: str | None
    attempt_count: int
    created_at: datetime
    updated_at: datetime


class QARequest(BaseModel):
    provider_name: str = Field(default="mock", min_length=1, max_length=64)
    export_preset: QAExportPreset | str = "draft"
    max_bubble_panel_coverage: float | None = Field(default=None, gt=0, le=1)


class QAIssue(BaseModel):
    id: str
    code: str
    issue_code: str | None = None
    category: QAIssueCategory | str = "layout"
    issue_category: QAIssueCategory | str = "layout"
    severity: QAIssueSeverity | str
    confidence: float = Field(default=1.0, ge=0, le=1)
    message: str
    target_type: str
    target_id: uuid.UUID | None = None
    page_id: uuid.UUID | None = None
    panel_id: uuid.UUID | None = None
    bubble_id: uuid.UUID | None = None
    blocking: bool = False
    auto_fix_available: bool = False
    auto_fix_action: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


class QARecommendation(BaseModel):
    id: str
    message: str
    target_type: str
    target_id: uuid.UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class QAReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: QATargetType | str
    target_id: uuid.UUID
    issue_code: str | None = None
    issue_category: QAIssueCategory | str | None = None
    severity: QAIssueSeverity | str | None = None
    confidence: float = 1.0
    page_id: uuid.UUID | None = None
    panel_id: uuid.UUID | None = None
    auto_fix_available: bool = False
    auto_fix_action: dict[str, Any] = Field(default_factory=dict)
    overall_score: int
    scores: dict[str, Any]
    issues: list[QAIssue]
    recommendations: list[QARecommendation]
    blocking: bool
    created_at: datetime
    updated_at: datetime


class QAAutoFixRequest(BaseModel):
    issue_id: str | None = None
    issue_code: str | None = None
    safe_only: bool = True


class QAAutoFixResult(BaseModel):
    report_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    page_id: uuid.UUID | None = None
    applied: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    before_report: QAReportRead | None = None
    after_report: QAReportRead | None = None
    page_reports: list[QAReportRead] = Field(default_factory=list)
    project_report: QAReportRead | None = None


class QAProjectRunResult(BaseModel):
    project_report: QAReportRead
    page_reports: list[QAReportRead] = Field(default_factory=list)


class ExportCreate(BaseModel):
    format: ExportFormat | str = Field(default="zip")
    force: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class ExportPresetRead(BaseModel):
    id: str
    name: str
    description: str
    page_width: int = Field(ge=1)
    page_height: int = Field(ge=0)
    dpi: int = Field(ge=1)
    bleed: int = Field(ge=0)
    safe_margin: int = Field(ge=0)
    color_mode: str
    reading_direction: ReadingDirection | str
    file_format: ExportFormat | str
    compression_quality: int = Field(ge=1, le=100)
    required_qa_gates: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class ProjectPublishingMetadataUpsert(BaseModel):
    title: str = Field(default="", max_length=240)
    subtitle: str = Field(default="", max_length=240)
    author_name: str = Field(default="", max_length=240)
    publisher: str = Field(default="", max_length=240)
    language: str = Field(default="en", max_length=32)
    synopsis: str = Field(default="", max_length=20_000)
    age_rating: str = Field(default="unrated", max_length=80)
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    copyright_notice: str = Field(default="", max_length=4000)
    ai_disclosure_text: str = Field(default="", max_length=10_000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProjectPublishingMetadataRead(ProjectPublishingMetadataUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class FeedbackCreate(BaseModel):
    project_id: uuid.UUID | None = None
    page_id: uuid.UUID | None = None
    panel_id: uuid.UUID | None = None
    category: str = Field(default="general", max_length=80)
    severity: Literal["low", "medium", "high", "blocking"] = "medium"
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=20_000)
    contact_email: str | None = Field(default=None, max_length=320)
    browser_info: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    diagnostic_info: dict[str, Any] = Field(default_factory=dict)


class FeedbackRead(FeedbackCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class GenerationFeedbackCreate(BaseModel):
    project_id: uuid.UUID | None = None
    target_type: LearningTargetType | str
    target_id: uuid.UUID
    rating: int = Field(ge=-1, le=1)
    issue_type: LearningIssueType | str | None = None
    comment: str = Field(default="", max_length=20_000)
    user_correction: str = Field(default="", max_length=20_000)
    before_snapshot_id: uuid.UUID | None = None
    after_snapshot_id: uuid.UUID | None = None
    allow_use_for_product_improvement: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class GenerationFeedbackRead(GenerationFeedbackCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None = None
    allow_use_for_product_improvement: bool
    created_at: datetime
    updated_at: datetime


class LearningIssueOption(BaseModel):
    id: str
    label: str


class LearningFeedbackOptions(BaseModel):
    issue_tags: list[LearningIssueOption]
    default_allow_use_for_product_improvement: bool = False
    collection_explanation: str


class AlphaOnboardingInfo(BaseModel):
    auth: dict[str, Any]
    welcome_title: str
    welcome_message: str
    first_demo_premise: str
    provider_modes: list[dict[str, Any]]
    suggested_first_steps: list[str]
    safety_rules: list[str]
    docs: list[dict[str, str]]


class AlphaDashboardMetric(BaseModel):
    label: str
    value: int | float | str
    detail: str = ""


class AlphaDashboardRead(BaseModel):
    metrics: list[AlphaDashboardMetric]
    failed_jobs: list[GenerationJobRead]
    provider_errors: list[GenerationJobRead]
    feedback_items: list[FeedbackRead]
    recent_qa_failures: list[QAReportRead]


class ImprovementReportMetric(BaseModel):
    name: str
    value: float | int | str
    detail: str = ""


class ImprovementReportRead(BaseModel):
    generated_at: datetime
    privacy_note: str
    generation_success_rate: float
    retry_rate: float
    provider_failure_rate: dict[str, float]
    qa_failure_categories: dict[str, int]
    average_page_qa_score: float | None
    export_success_rate: float
    most_common_failures: list[dict[str, Any]]
    worst_performing_pipeline_stage: str
    best_performing_style_or_preset: str | None
    qa_trends: dict[str, Any]
    provider_reliability: list[dict[str, Any]]
    recommended_engineering_priorities: list[str]


class ExportReadinessItem(BaseModel):
    key: str
    label: str
    passed: bool
    severity: Literal["info", "warning", "blocking"] = "blocking"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExportReadinessResult(BaseModel):
    project_id: uuid.UUID
    preset: ExportPresetRead
    ready: bool
    force_required: bool
    checklist: list[ExportReadinessItem]
    page_count: int
    blocking_issue_count: int
    metadata: ProjectPublishingMetadataRead | None = None


class ExportPreviewResult(BaseModel):
    project_id: uuid.UUID
    preset: ExportPresetRead
    readiness: ExportReadinessResult
    estimated_files: list[str]
    estimated_size_bytes: int
    warnings: list[str] = Field(default_factory=list)
    metadata_preview: dict[str, Any] = Field(default_factory=dict)


class ExportCreateAdvanced(BaseModel):
    preset_id: str = Field(default="archive_package", max_length=120)
    force: bool = False
    metadata: ProjectPublishingMetadataUpsert | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    format: ExportFormat | str
    status: ExportStatus | str
    file_asset_id: uuid.UUID | None
    options: dict[str, Any]
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    file_asset: AssetRead | None = None


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    snapshot_json: dict[str, Any]
    asset_ids: list[str]
    label: str
    created_by: str
    created_at: datetime
    reason: str
    is_checkpoint: bool


class CheckpointCreate(BaseModel):
    label: str = Field(default="Manual checkpoint", min_length=1, max_length=240)
    created_by: str = Field(default="user", min_length=1, max_length=160)
    reason: str = Field(default="manual_checkpoint", max_length=1000)


class VersionRestoreResult(BaseModel):
    restored_version: VersionRead


class VersionDiffResult(BaseModel):
    version_a: dict[str, Any]
    version_b: dict[str, Any]
    added: dict[str, Any]
    removed: dict[str, Any]
    changed: dict[str, Any]


class CommandScope(BaseModel):
    type: CommandScopeType
    id: uuid.UUID


class CommandAction(BaseModel):
    action_type: CommandActionType | str
    target_type: CommandScopeType | str
    target_id: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    destructive: bool = False


class CommandInterpretRequest(BaseModel):
    project_id: uuid.UUID
    scope: CommandScope
    command: str = Field(min_length=1, max_length=5000)


class CommandInterpretResult(BaseModel):
    command_id: uuid.UUID | None = None
    project_id: uuid.UUID
    intent: str
    target_type: str
    target_id: str
    proposed_actions: list[CommandAction] = Field(default_factory=list)
    requires_confirmation: bool
    risk_level: CommandRiskLevel | str
    summary: str


class CommandExecuteRequest(CommandInterpretRequest):
    confirmed: bool = False


class CommandExecuteResult(CommandInterpretResult):
    command_id: uuid.UUID
    status: CommandStatus | str
    executed_actions: list[dict[str, Any]] = Field(default_factory=list)
    version_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None


class CommandHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    scope_type: str
    scope_id: str
    command: str
    intent: str
    target_type: str
    target_id: str
    proposed_actions: list[dict[str, Any]]
    executed_actions: list[dict[str, Any]]
    requires_confirmation: bool
    confirmed: bool
    risk_level: str
    status: str
    summary: str
    error_message: str | None
    version_ids: list[str]
    created_at: datetime
    updated_at: datetime


class DemoPipelineResult(BaseModel):
    project: ProjectRead
    story_bible_id: uuid.UUID
    chapter_id: uuid.UUID
    page_ids: list[uuid.UUID]
    panel_ids: list[uuid.UUID]
    render_job_ids: list[uuid.UUID]
    composite_asset_ids: list[uuid.UUID]
    qa_report_ids: list[uuid.UUID]
    exports: dict[str, uuid.UUID]


class EvalScenarioRead(BaseModel):
    id: str
    name: str
    premise: str
    genre: list[str]
    tone: str
    target_audience: str
    page_count: int
    expected_character_count: int
    expected_location_count: int
    expected_key_beats: list[str]
    expected_page_types: list[str]
    export_requirements: list[str]
    reading_direction: ReadingDirection | str = "rtl"
    expected_panel_count: int


class EvalRunRequest(BaseModel):
    scenario: str = Field(default="all", max_length=120)
    provider: str = Field(default="mock", min_length=1, max_length=64)
    quality_mode: DirectorQualityMode = "fast"
    write_reports: bool = True


class EvalScenarioReport(BaseModel):
    scenario: dict[str, Any]
    project_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    duration_seconds: float
    scores: dict[str, Any]
    metrics: dict[str, Any]
    counts: dict[str, int]
    generated: dict[str, Any]
    failures: list[str]
    links: dict[str, str]


class EvalRunReport(BaseModel):
    run_id: uuid.UUID
    created_at: datetime
    completed_at: datetime
    provider: str
    quality_mode: str
    scenario_selector: str
    scenario_count: int
    metrics: dict[str, Any]
    scenarios: list[EvalScenarioReport]


class DirectorGenerateDraftRequest(BaseModel):
    premise: str = Field(min_length=1, max_length=LONG_FORM_TEXT_MAX_LENGTH)
    chapter_count: int = Field(default=1, ge=1, le=24)
    page_count: int = Field(default=4, ge=1, le=64)
    target_audience: str = Field(default="Teen and young adult manga readers", min_length=1, max_length=240)
    genre: list[str] = Field(default_factory=list, max_length=8)
    tone: str = Field(default="Cinematic and emotional", min_length=1, max_length=240)
    reading_direction: ReadingDirection = "rtl"
    render_provider: str = Field(default="mock", min_length=1, max_length=64)
    quality_mode: DirectorQualityMode = "balanced"
    allow_mock_assets: bool = True

    @field_validator("genre")
    @classmethod
    def clean_genres(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        return cleaned or ["drama"]


class DirectorGenerateDraftResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID


class FounderDemoRunRequest(BaseModel):
    premise: str = Field(
        default="A lonely swordsman protects a ghost child in a ruined city.",
        min_length=1,
        max_length=LONG_FORM_TEXT_MAX_LENGTH,
    )
    style_option: str = Field(default="ruined_ink_elegy", min_length=1, max_length=80)
    page_count: int = Field(default=4, ge=1, le=12)
    reading_direction: ReadingDirection = "rtl"
    render_provider: str = Field(default="mock", min_length=1, max_length=64)
    quality_mode: DirectorQualityMode = "fast"
    allow_mock_assets: bool = True


class FounderDemoRunResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID


class StoryBibleCreate(BaseModel):
    premise: str | None = Field(default=None, max_length=LONG_FORM_TEXT_MAX_LENGTH)
    genre: str | None = Field(default=None, max_length=120)
    tone: str | None = Field(default=None, max_length=240)
    target_audience: str | None = Field(default=None, max_length=240)
    chapter_count: int = Field(default=3, ge=1, le=24)


class StoryCharacterResult(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    traits: list[str] = Field(default_factory=list)
    visual_notes: str | None = Field(default=None, max_length=2000)


class StoryLocationResult(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    visual_notes: str | None = Field(default=None, max_length=2000)
    rules: list[str] = Field(default_factory=list)


class StoryKeyObjectResult(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    significance: str = Field(min_length=1, max_length=2000)
    visual_notes: str | None = Field(default=None, max_length=2000)


class ChapterOutlineItem(BaseModel):
    chapter_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=3000)


class StyleBibleResult(BaseModel):
    id: uuid.UUID | None = None
    visual_style: str = Field(min_length=1, max_length=2000)
    line_art: str = Field(min_length=1, max_length=1000)
    palette: str = Field(min_length=1, max_length=1000)
    paneling: str = Field(min_length=1, max_length=1000)
    lettering: str = Field(min_length=1, max_length=1000)
    negative_prompts: list[str] = Field(default_factory=list)


class StoryBibleResult(BaseModel):
    id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    logline: str = Field(min_length=1, max_length=1000)
    synopsis: str = Field(min_length=1, max_length=8000)
    genre: str = Field(min_length=1, max_length=120)
    themes: list[str] = Field(min_length=1)
    target_audience: str = Field(min_length=1, max_length=240)
    tone: str = Field(min_length=1, max_length=240)
    main_conflict: str = Field(min_length=1, max_length=2000)
    world_rules: list[str] = Field(min_length=1)
    characters: list[StoryCharacterResult] = Field(min_length=1)
    locations: list[StoryLocationResult] = Field(min_length=1)
    key_objects: list[StoryKeyObjectResult] = Field(min_length=1)
    chapter_outline: list[ChapterOutlineItem] = Field(min_length=1)
    continuity_rules: list[str] = Field(min_length=1)
    style_bible: StyleBibleResult | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScenePlanResult(BaseModel):
    id: uuid.UUID | None = None
    scene_order: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=3000)
    location_name: str | None = Field(default=None, max_length=160)
    emotional_turn: str | None = Field(default=None, max_length=1000)
    characters: list[str] = Field(default_factory=list)


class ChapterPlanResult(BaseModel):
    id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    story_bible_id: uuid.UUID | None = None
    chapter_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=4000)
    goal: str = Field(min_length=1, max_length=2000)
    scenes: list[ScenePlanResult] = Field(default_factory=list)


class PanelPlanResult(BaseModel):
    id: uuid.UUID | None = None
    page_plan_id: uuid.UUID | None = None
    panel_order: int = Field(ge=1)
    story_beat: str = Field(min_length=1, max_length=2000)
    shot_type: str = Field(min_length=1, max_length=160)
    camera_angle: str = Field(min_length=1, max_length=160)
    characters: list[str] = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=160)
    dialogue: str | None = Field(default=None, max_length=2000)
    narration: str | None = Field(default=None, max_length=2000)
    visual_notes: str = Field(min_length=1, max_length=3000)
    emotional_intent: str = Field(min_length=1, max_length=1000)
    beat_importance: int = Field(default=50, ge=0, le=100)
    time_duration: str = Field(default="normal", max_length=80)
    camera_motion: str = Field(default="still", max_length=120)
    motion_intensity: int = Field(default=20, ge=0, le=100)
    dialogue_weight: int = Field(default=0, ge=0, le=100)
    silence: bool = False
    impact_level: int = Field(default=20, ge=0, le=100)
    recommended_panel_size: str = Field(default="medium", max_length=40)
    transition_type: str = Field(default="moment_to_moment", max_length=80)


class PagePlanResult(BaseModel):
    id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    page_number: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=3000)
    pacing: str = Field(min_length=1, max_length=1000)
    page_role: str = Field(default="story_progression", max_length=120)
    emotional_intensity: int = Field(default=50, ge=0, le=100)
    action_intensity: int = Field(default=30, ge=0, le=100)
    dialogue_density: int = Field(default=30, ge=0, le=100)
    silence_level: int = Field(default=20, ge=0, le=100)
    reveal_level: int = Field(default=20, ge=0, le=100)
    page_turn_importance: int = Field(default=20, ge=0, le=100)
    recommended_page_type: PageType | str = "standard"
    pacing_notes: str = Field(default="", max_length=5000)
    panels: list[PanelPlanResult] = Field(default_factory=list)


class CharacterCardTaskResult(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list)
    age_range: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=160)
    personality: str = Field(default="", max_length=3000)
    face_description: str = Field(default="", max_length=2000)
    hair_description: str = Field(default="", max_length=2000)
    eye_description: str = Field(default="", max_length=2000)
    body_type: str = Field(default="", max_length=1000)
    outfit_default: str = Field(default="", max_length=2000)
    accessories: list[str] = Field(default_factory=list)
    scars_marks: str = Field(default="", max_length=2000)
    voice_style: str = Field(default="", max_length=1000)
    forbidden_changes: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    canonical_visual_summary: str = Field(default="", max_length=4000)
    silhouette_keywords: list[str] = Field(default_factory=list)
    face_anchor_description: str = Field(default="", max_length=2000)
    hair_anchor_description: str = Field(default="", max_length=2000)
    eye_anchor_description: str = Field(default="", max_length=2000)
    body_anchor_description: str = Field(default="", max_length=2000)
    outfit_anchor_description: str = Field(default="", max_length=2000)
    color_notes_even_for_bw: str = Field(default="", max_length=2000)
    recurring_props: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_variations: list[str] = Field(default_factory=list)
    current_story_state: str = Field(default="", max_length=2000)
    injury_state: str = Field(default="", max_length=2000)
    emotional_baseline: str = Field(default="", max_length=2000)


class CharacterCardsResult(BaseModel):
    characters: list[CharacterCardTaskResult] = Field(min_length=1)


class LocationObjectCardsResult(BaseModel):
    locations: list[StoryLocationResult] = Field(min_length=1)
    key_objects: list[StoryKeyObjectResult] = Field(default_factory=list)


class StyleDNABase(BaseModel):
    style_name: str = Field(default="", max_length=200)
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
    typography_notes: str = Field(default="", max_length=2000)
    emotional_visual_rules: list[str] = Field(default_factory=list)
    positive_prompt_fragments: list[str] = Field(default_factory=list)
    negative_prompt_fragments: list[str] = Field(default_factory=list)
    forbidden_artist_references: list[str] = Field(default_factory=list)
    forbidden_franchise_references: list[str] = Field(default_factory=list)


class StyleDNAOption(StyleDNABase):
    preview_prompt: str = Field(min_length=1, max_length=4000)


class StyleDNAOptionsResult(BaseModel):
    options: list[StyleDNAOption] = Field(min_length=3, max_length=6)


class StyleDNAGenerateRequest(BaseModel):
    genre: str = Field(default="", max_length=240)
    tone: str = Field(default="", max_length=240)
    audience: str = Field(default="", max_length=240)
    visual_keywords: list[str] = Field(default_factory=list)
    avoid_keywords: list[str] = Field(default_factory=list)
    sample_story_summary: str = Field(default="", max_length=5000)


class StyleGuardIssue(BaseModel):
    severity: Literal["warning", "error"]
    code: str
    message: str
    field: str | None = None
    matched_text: str | None = None


class StyleGuardResult(BaseModel):
    allowed: bool
    severity: Literal["safe", "warning", "blocked"]
    issues: list[StyleGuardIssue] = Field(default_factory=list)
    suggested_style: dict[str, Any] = Field(default_factory=dict)


class StylePreviewResult(BaseModel):
    asset: AssetRead
    public_url: str
    preview_prompt: str
    safety: StyleGuardResult


class StyleBibleTaskResult(StyleDNABase):
    name: str = Field(min_length=1, max_length=200)
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
    forbidden_references: list[str] = Field(default_factory=list)
    prompt_style_positive: str = Field(default="", max_length=4000)
    prompt_style_negative: str = Field(default="", max_length=4000)


class PanelPlanBatchResult(BaseModel):
    panels: list[PanelPlanResult] = Field(min_length=1)


class TaskLayoutPoint(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class LayoutPanelResult(BaseModel):
    panel_order: int = Field(ge=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    polygon: list[TaskLayoutPoint] = Field(min_length=4)
    visual_notes: str | None = Field(default=None, max_length=3000)


class LayoutPlanResult(BaseModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bleed: int = Field(ge=0)
    safe_margin: int = Field(ge=0)
    reading_direction: ReadingDirection
    panels: list[LayoutPanelResult] = Field(min_length=1)

    @model_validator(mode="after")
    def layout_panel_order_must_be_unique(self) -> "LayoutPlanResult":
        orders = [panel.panel_order for panel in self.panels]
        if len(orders) != len(set(orders)):
            raise ValueError("Layout panel order must be unique")
        return self


class PanelPromptResult(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    references: list[dict[str, Any]] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class BubblePlanItemResult(BaseModel):
    panel_order: int = Field(ge=1)
    kind: BubbleKind = "speech"
    text: str = Field(min_length=1, max_length=2000)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class BubblePlanResult(BaseModel):
    bubbles: list[BubblePlanItemResult] = Field(min_length=1)


class CritiqueResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    scores: dict[str, Any] = Field(default_factory=dict)
    issues: list[QAIssue] = Field(default_factory=list)
    recommendations: list[QARecommendation] = Field(default_factory=list)
    blocking: bool = False


class RepairInvalidJsonResult(BaseModel):
    repaired_json: dict[str, Any]
    notes: str = Field(default="", max_length=2000)


class ChapterPlanBatchResult(BaseModel):
    chapters: list[ChapterPlanResult] = Field(min_length=1)


class PagePlanBatchResult(BaseModel):
    pages: list[PagePlanResult] = Field(min_length=1)


class PacingPanelAnalysis(BaseModel):
    panel_plan_id: uuid.UUID
    panel_order: int
    beat_importance: int = Field(ge=0, le=100)
    time_duration: str
    camera_motion: str
    motion_intensity: int = Field(ge=0, le=100)
    dialogue_weight: int = Field(ge=0, le=100)
    silence: bool
    impact_level: int = Field(ge=0, le=100)
    recommended_panel_size: str
    transition_type: str
    notes: list[str] = Field(default_factory=list)


class PacingPageAnalysis(BaseModel):
    page_plan_id: uuid.UUID
    page_number: int
    page_role: str
    emotional_intensity: int = Field(ge=0, le=100)
    action_intensity: int = Field(ge=0, le=100)
    dialogue_density: int = Field(ge=0, le=100)
    silence_level: int = Field(ge=0, le=100)
    reveal_level: int = Field(ge=0, le=100)
    page_turn_importance: int = Field(ge=0, le=100)
    recommended_page_type: PageType | str
    pacing_notes: str
    panel_count: int
    panels: list[PacingPanelAnalysis] = Field(default_factory=list)


class PacingRecommendation(BaseModel):
    code: str = Field(max_length=120)
    severity: Literal["info", "warning", "blocking"] = "info"
    target_type: Literal["chapter", "page_plan", "panel_plan"] | str
    target_id: uuid.UUID
    page_number: int | None = None
    message: str = Field(max_length=1000)
    suggested_action: str = Field(max_length=120)
    details: dict[str, Any] = Field(default_factory=dict)


class PacingAnalysisResult(BaseModel):
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    pages: list[PacingPageAnalysis] = Field(default_factory=list)
    recommendations: list[PacingRecommendation] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PacingRebalanceResult(PacingAnalysisResult):
    updated_page_plan_ids: list[uuid.UUID] = Field(default_factory=list)
    updated_panel_plan_ids: list[uuid.UUID] = Field(default_factory=list)
    version_ids: list[uuid.UUID] = Field(default_factory=list)


class LayoutPoint(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class PanelLayoutInput(BaseModel):
    id: uuid.UUID | None = None
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    polygon: list[LayoutPoint] = Field(min_length=4)
    reading_order: int = Field(ge=1)
    prompt: str | None = Field(default=None, max_length=4000)


class BubbleCreate(BaseModel):
    kind: BubbleKind = "speech"
    bubble_type: BubbleKind | None = None
    speaker_character_id: uuid.UUID | None = None
    x: int = Field(default=120, ge=0)
    y: int = Field(default=120, ge=0)
    width: int = Field(default=260, ge=1)
    height: int = Field(default=120, ge=1)
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en", max_length=16)
    reading_direction: ReadingDirection = "rtl"
    shape: str = Field(default="oval", max_length=64)
    position: dict[str, Any] = Field(default_factory=dict)
    size: dict[str, Any] = Field(default_factory=dict)
    tail_target: dict[str, Any] = Field(default_factory=dict)
    font_family: str = Field(default="Manga Temple", max_length=160)
    font_size: int = Field(default=24, ge=6, le=160)
    font_weight: str = Field(default="regular", max_length=40)
    text_align: TextAlign = "center"
    vertical_text: bool = False
    z_index: int = 0
    locked: bool = False

    @field_validator("text")
    @classmethod
    def text_cannot_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Bubble text cannot be empty")
        return stripped


class BubbleUpdate(BaseModel):
    kind: BubbleKind | None = None
    bubble_type: BubbleKind | None = None
    speaker_character_id: uuid.UUID | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    language: str | None = Field(default=None, max_length=16)
    reading_direction: ReadingDirection | None = None
    shape: str | None = Field(default=None, max_length=64)
    position: dict[str, Any] | None = None
    size: dict[str, Any] | None = None
    tail_target: dict[str, Any] | None = None
    font_family: str | None = Field(default=None, max_length=160)
    font_size: int | None = Field(default=None, ge=6, le=160)
    font_weight: str | None = Field(default=None, max_length=40)
    text_align: TextAlign | None = None
    vertical_text: bool | None = None
    z_index: int | None = None
    locked: bool | None = None

    @field_validator("text")
    @classmethod
    def text_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Bubble text cannot be empty")
        return stripped


class BubbleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    panel_id: uuid.UUID
    kind: str
    bubble_type: str
    speaker_character_id: uuid.UUID | None
    x: int
    y: int
    width: int
    height: int
    text: str
    language: str
    reading_direction: str
    shape: str
    position: dict[str, Any]
    size: dict[str, Any]
    tail_target: dict[str, Any]
    font_family: str
    font_size: int
    font_weight: str
    text_align: str
    vertical_text: bool
    z_index: int
    locked: bool
    created_at: datetime
    updated_at: datetime


class SFXElementCreate(BaseModel):
    panel_id: uuid.UUID | None = None
    text: str = Field(min_length=1, max_length=1000)
    meaning: str = Field(default="", max_length=1000)
    style: str = Field(default="impact", max_length=120)
    position: dict[str, Any] = Field(default_factory=lambda: {"x": 120, "y": 120})
    size: dict[str, Any] = Field(default_factory=lambda: {"width": 280, "height": 120})
    rotation: float = 0.0
    warp_style: str = Field(default="none", max_length=120)
    stroke_width: float = Field(default=4.0, ge=0)
    fill: str = Field(default="#ffffff", max_length=32)
    outline: str = Field(default="#111111", max_length=32)
    z_index: int = 10
    locked: bool = False

    @field_validator("text")
    @classmethod
    def sfx_text_cannot_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SFX text cannot be empty")
        return stripped


class SFXElementUpdate(BaseModel):
    panel_id: uuid.UUID | None = None
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    meaning: str | None = Field(default=None, max_length=1000)
    style: str | None = Field(default=None, max_length=120)
    position: dict[str, Any] | None = None
    size: dict[str, Any] | None = None
    rotation: float | None = None
    warp_style: str | None = Field(default=None, max_length=120)
    stroke_width: float | None = Field(default=None, ge=0)
    fill: str | None = Field(default=None, max_length=32)
    outline: str | None = Field(default=None, max_length=32)
    z_index: int | None = None
    locked: bool | None = None

    @field_validator("text")
    @classmethod
    def sfx_text_update_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("SFX text cannot be empty")
        return stripped


class SFXElementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    panel_id: uuid.UUID | None
    text: str
    meaning: str
    style: str
    position: dict[str, Any]
    size: dict[str, Any]
    rotation: float
    warp_style: str
    stroke_width: float
    fill: str
    outline: str
    z_index: int
    locked: bool
    created_at: datetime
    updated_at: datetime


class TextFitResult(BaseModel):
    text: str
    font_size: int
    lines: list[str]
    warning: str | None = None
    overflow: bool = False


class LetteringPageRead(BaseModel):
    page_id: uuid.UUID
    bubbles: list[BubbleRead] = Field(default_factory=list)
    sfx: list[SFXElementRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LetteringGenerateResult(LetteringPageRead):
    created_bubble_ids: list[uuid.UUID] = Field(default_factory=list)
    created_sfx_ids: list[uuid.UUID] = Field(default_factory=list)


class PanelLayoutRead(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    x: int
    y: int
    width: int
    height: int
    polygon: list[LayoutPoint]
    reading_order: int
    prompt: str | None
    bubbles: list[BubbleRead] = Field(default_factory=list)


class PageLayoutRead(BaseModel):
    page_id: uuid.UUID
    width: int
    height: int
    bleed: int = Field(ge=0)
    safe_margin: int = Field(ge=0)
    reading_direction: ReadingDirection
    qa_overlay_enabled: bool = False
    panels: list[PanelLayoutRead] = Field(default_factory=list)


class PageLayoutUpdate(BaseModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bleed: int = Field(ge=0)
    safe_margin: int = Field(ge=0)
    reading_direction: ReadingDirection
    qa_overlay_enabled: bool = False
    panels: list[PanelLayoutInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def panel_order_must_be_unique(self) -> "PageLayoutUpdate":
        orders = [panel.reading_order for panel in self.panels]
        if len(orders) != len(set(orders)):
            raise ValueError("Panel reading order must be unique per page")
        return self


class LayoutTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    page_type: PageType = "standard"
    panel_count: int = Field(default=1, ge=1, le=24)
    reading_direction: ReadingDirection = "rtl"
    emotional_use: str = Field(default="", max_length=5000)
    action_level: str = Field(default="medium", max_length=64)
    density: str = Field(default="medium", max_length=64)
    layout_json: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=5000)


class LayoutTemplateCreate(LayoutTemplateBase):
    pass


class LayoutTemplateRead(LayoutTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LayoutSlot(BaseModel):
    kind: str = Field(max_length=64)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    text: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)


class SuggestedPanelLayout(BaseModel):
    id: uuid.UUID | None = None
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    polygon: list[LayoutPoint] = Field(min_length=4)
    reading_order: int = Field(ge=1)
    prompt: str | None = Field(default=None, max_length=4000)
    story_beat: str | None = Field(default=None, max_length=2000)
    emotional_beat: str | None = Field(default=None, max_length=1000)
    importance: float = Field(default=1.0, ge=0)
    locked: bool = False
    bubble_slots: list[LayoutSlot] = Field(default_factory=list)
    sfx_slots: list[LayoutSlot] = Field(default_factory=list)


class LayoutValidationIssue(BaseModel):
    severity: QAIssueSeverity = "error"
    code: str = Field(max_length=120)
    message: str = Field(max_length=1000)
    panel_order: int | None = Field(default=None, ge=1)


class LayoutSuggestRequest(BaseModel):
    page_type: PageType | None = None
    template_id: uuid.UUID | None = None
    reading_direction: ReadingDirection | None = None
    locked_panel_ids: list[uuid.UUID] = Field(default_factory=list)
    safe_margin: int | None = Field(default=None, ge=0)
    bleed: int | None = Field(default=None, ge=0)
    min_gutter: int = Field(default=12, ge=0, le=200)


class LayoutSuggestionRead(BaseModel):
    page_id: uuid.UUID
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bleed: int = Field(ge=0)
    safe_margin: int = Field(ge=0)
    reading_direction: ReadingDirection
    page_type: PageType
    template_id: uuid.UUID | None = None
    layout_reasoning: list[str] = Field(default_factory=list)
    validation_issues: list[LayoutValidationIssue] = Field(default_factory=list)
    panels: list[SuggestedPanelLayout] = Field(min_length=1)


class CharacterCardBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list)
    age_range: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=160)
    personality: str = Field(default="", max_length=3000)
    face_description: str = Field(default="", max_length=2000)
    hair_description: str = Field(default="", max_length=2000)
    eye_description: str = Field(default="", max_length=2000)
    body_type: str = Field(default="", max_length=1000)
    outfit_default: str = Field(default="", max_length=2000)
    accessories: list[str] = Field(default_factory=list)
    scars_marks: str = Field(default="", max_length=2000)
    voice_style: str = Field(default="", max_length=1000)
    forbidden_changes: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    canonical_visual_summary: str = Field(default="", max_length=4000)
    silhouette_keywords: list[str] = Field(default_factory=list)
    face_anchor_description: str = Field(default="", max_length=2000)
    hair_anchor_description: str = Field(default="", max_length=2000)
    eye_anchor_description: str = Field(default="", max_length=2000)
    body_anchor_description: str = Field(default="", max_length=2000)
    outfit_anchor_description: str = Field(default="", max_length=2000)
    color_notes_even_for_bw: str = Field(default="", max_length=2000)
    recurring_props: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_variations: list[str] = Field(default_factory=list)
    current_story_state: str = Field(default="", max_length=2000)
    injury_state: str = Field(default="", max_length=2000)
    emotional_baseline: str = Field(default="", max_length=2000)
    reference_asset_ids: list[str] = Field(default_factory=list)
    approved_panel_asset_ids: list[str] = Field(default_factory=list)


class CharacterCardCreate(CharacterCardBase):
    pass


class CharacterCardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    aliases: list[str] | None = None
    age_range: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=160)
    personality: str | None = Field(default=None, max_length=3000)
    face_description: str | None = Field(default=None, max_length=2000)
    hair_description: str | None = Field(default=None, max_length=2000)
    eye_description: str | None = Field(default=None, max_length=2000)
    body_type: str | None = Field(default=None, max_length=1000)
    outfit_default: str | None = Field(default=None, max_length=2000)
    accessories: list[str] | None = None
    scars_marks: str | None = Field(default=None, max_length=2000)
    voice_style: str | None = Field(default=None, max_length=1000)
    forbidden_changes: list[str] | None = None
    continuity_rules: list[str] | None = None
    canonical_visual_summary: str | None = Field(default=None, max_length=4000)
    silhouette_keywords: list[str] | None = None
    face_anchor_description: str | None = Field(default=None, max_length=2000)
    hair_anchor_description: str | None = Field(default=None, max_length=2000)
    eye_anchor_description: str | None = Field(default=None, max_length=2000)
    body_anchor_description: str | None = Field(default=None, max_length=2000)
    outfit_anchor_description: str | None = Field(default=None, max_length=2000)
    color_notes_even_for_bw: str | None = Field(default=None, max_length=2000)
    recurring_props: list[str] | None = None
    allowed_variations: list[str] | None = None
    forbidden_variations: list[str] | None = None
    current_story_state: str | None = Field(default=None, max_length=2000)
    injury_state: str | None = Field(default=None, max_length=2000)
    emotional_baseline: str | None = Field(default=None, max_length=2000)
    reference_asset_ids: list[str] | None = None
    approved_panel_asset_ids: list[str] | None = None


class CharacterCardRead(CharacterCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ReferenceAssetCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="reference", max_length=64)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(default=0, ge=0)
    storage_key: str | None = Field(default=None, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CharacterReferenceAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    character_card_id: uuid.UUID
    filename: str
    kind: str
    content_type: str
    size_bytes: int
    storage_key: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CharacterStateBase(BaseModel):
    chapter_id: uuid.UUID
    scene_id: uuid.UUID
    page_id: uuid.UUID | None = None
    outfit_state: str = Field(default="", max_length=2000)
    injury_state: str = Field(default="", max_length=2000)
    emotional_state: str = Field(default="", max_length=2000)
    prop_state: str = Field(default="", max_length=2000)
    visibility_notes: str = Field(default="", max_length=2000)
    continuity_notes: str = Field(default="", max_length=3000)


class CharacterStateCreate(CharacterStateBase):
    pass


class CharacterStateUpdate(BaseModel):
    chapter_id: uuid.UUID | None = None
    scene_id: uuid.UUID | None = None
    page_id: uuid.UUID | None = None
    outfit_state: str | None = Field(default=None, max_length=2000)
    injury_state: str | None = Field(default=None, max_length=2000)
    emotional_state: str | None = Field(default=None, max_length=2000)
    prop_state: str | None = Field(default=None, max_length=2000)
    visibility_notes: str | None = Field(default=None, max_length=2000)
    continuity_notes: str | None = Field(default=None, max_length=3000)


class CharacterStateRead(CharacterStateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    character_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ReferencePackPanelSummary(BaseModel):
    panel_id: uuid.UUID
    reading_order: int
    prompt: str | None = None
    summary: str | None = None


class ReferencePackCharacterRead(BaseModel):
    card: CharacterCardRead
    state: CharacterStateRead | None = None
    reference_assets: list[CharacterReferenceAssetRead] = Field(default_factory=list)
    approved_panel_assets: list[AssetRead] = Field(default_factory=list)
    missing_state: bool = False


class ReferencePackRead(BaseModel):
    panel_id: uuid.UUID
    page_id: uuid.UUID
    project_id: uuid.UUID
    style_bible: dict[str, Any] | None = None
    story_memory: dict[str, Any] = Field(default_factory=dict)
    characters: list[ReferencePackCharacterRead] = Field(default_factory=list)
    character_states: list[CharacterStateRead] = Field(default_factory=list)
    locations: list[StoryLocationResult] = Field(default_factory=list)
    key_objects: list[StoryKeyObjectResult] = Field(default_factory=list)
    approved_visual_references: list[dict[str, Any]] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    previous_summaries: list[ReferencePackPanelSummary] = Field(default_factory=list)
    required_anchor_names: list[str] = Field(default_factory=list)
    missing_character_state_ids: list[uuid.UUID] = Field(default_factory=list)


class PagePanelReferencePackSummary(BaseModel):
    panel_id: uuid.UUID
    reading_order: int
    characters: list[str] = Field(default_factory=list)
    active_states: list[CharacterStateRead] = Field(default_factory=list)
    missing_state_character_ids: list[uuid.UUID] = Field(default_factory=list)
    warning: str | None = None


class PageReferencePacksRead(BaseModel):
    page_id: uuid.UUID
    panels: list[PagePanelReferencePackSummary] = Field(default_factory=list)


class ExpressionSheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    character_card_id: uuid.UUID
    name: str
    expressions: list[str]
    asset_ids: list[str]
    created_at: datetime
    updated_at: datetime


class OutfitVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    character_card_id: uuid.UUID
    name: str
    description: str
    accessories: list[str]
    continuity_notes: str
    created_at: datetime
    updated_at: datetime


class GenerateCharacterSheetResult(BaseModel):
    job: GenerationJobRead
    assets: list[CharacterReferenceAssetRead]
    expression_sheet: ExpressionSheetRead


class StyleBibleLabBase(StyleDNABase):
    name: str = Field(min_length=1, max_length=200)
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
    forbidden_references: list[str] = Field(default_factory=list)
    prompt_style_positive: str = Field(default="", max_length=4000)
    prompt_style_negative: str = Field(default="", max_length=4000)


class StyleBibleLabCreate(StyleBibleLabBase):
    pass


class StyleBibleLabUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    style_name: str | None = Field(default=None, max_length=200)
    style_intent: str | None = Field(default=None, max_length=3000)
    line_weight: str | None = Field(default=None, max_length=1000)
    line_variation: str | None = Field(default=None, max_length=1000)
    line_texture: str | None = Field(default=None, max_length=1000)
    face_shape_language: str | None = Field(default=None, max_length=2000)
    eye_design_language: str | None = Field(default=None, max_length=2000)
    nose_mouth_simplification: str | None = Field(default=None, max_length=2000)
    anatomy_proportions: str | None = Field(default=None, max_length=2000)
    hair_rendering: str | None = Field(default=None, max_length=2000)
    clothing_fold_style: str | None = Field(default=None, max_length=2000)
    background_density: str | None = Field(default=None, max_length=2000)
    architecture_detail: str | None = Field(default=None, max_length=2000)
    shadow_strategy: str | None = Field(default=None, max_length=2000)
    screentone_strategy: str | None = Field(default=None, max_length=2000)
    hatching_strategy: str | None = Field(default=None, max_length=2000)
    black_fill_ratio: str | None = Field(default=None, max_length=1000)
    speedline_style: str | None = Field(default=None, max_length=2000)
    impact_frame_style: str | None = Field(default=None, max_length=2000)
    panel_border_style: str | None = Field(default=None, max_length=2000)
    gutter_style: str | None = Field(default=None, max_length=2000)
    sfx_shape_language: str | None = Field(default=None, max_length=2000)
    bubble_style: str | None = Field(default=None, max_length=2000)
    emotional_visual_rules: list[str] | None = None
    positive_prompt_fragments: list[str] | None = None
    negative_prompt_fragments: list[str] | None = None
    forbidden_artist_references: list[str] | None = None
    forbidden_franchise_references: list[str] | None = None
    linework: str | None = Field(default=None, max_length=2000)
    screentone: str | None = Field(default=None, max_length=2000)
    hatching: str | None = Field(default=None, max_length=2000)
    black_white_balance: str | None = Field(default=None, max_length=2000)
    face_language: str | None = Field(default=None, max_length=2000)
    anatomy_style: str | None = Field(default=None, max_length=2000)
    background_detail: str | None = Field(default=None, max_length=2000)
    panel_rhythm: str | None = Field(default=None, max_length=2000)
    sfx_style: str | None = Field(default=None, max_length=2000)
    typography_notes: str | None = Field(default=None, max_length=2000)
    forbidden_references: list[str] | None = None
    prompt_style_positive: str | None = Field(default=None, max_length=4000)
    prompt_style_negative: str | None = Field(default=None, max_length=4000)


class StyleBibleLabRead(StyleBibleLabBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    story_bible_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class StyleSampleAssetCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="style_sample", max_length=64)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(default=0, ge=0)
    storage_key: str | None = Field(default=None, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class StyleSampleAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    style_bible_id: uuid.UUID
    filename: str
    kind: str
    content_type: str
    size_bytes: int
    storage_key: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ActiveStyleUpdate(BaseModel):
    style_bible_id: uuid.UUID
