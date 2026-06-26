export type Id = string;

export type ProjectStatus = "draft" | "archived";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type JobType = "render_panel";
export type ProviderName = "mock" | "openai" | "comfyui" | string;
export type AITaskStatus = "queued" | "running" | "succeeded" | "failed";
export type AITaskType =
  | "generate_story_bible"
  | "generate_character_cards"
  | "generate_location_cards"
  | "generate_style_bible"
  | "generate_style_dna"
  | "generate_chapter_plan"
  | "generate_page_plan"
  | "generate_panel_plan"
  | "generate_layout_plan"
  | "generate_panel_prompt"
  | "generate_bubble_plan"
  | "critique_page"
  | "critique_panel"
  | "repair_invalid_json";
export type DirectorProgressEvent =
  | "queued"
  | "generating_story_bible"
  | "generating_characters"
  | "generating_style"
  | "planning_pages"
  | "creating_layouts"
  | "rendering_panels"
  | "composing_pages"
  | "running_qa"
  | "exporting"
  | "creating_project"
  | "writing_story_bible"
  | "designing_characters"
  | "creating_style_dna"
  | "drawing_layouts"
  | "lettering_pages"
  | "composing_final_pages"
  | "checking_quality"
  | "exporting_files"
  | "complete"
  | "failed";
export type DirectorQualityMode = "fast" | "balanced" | "high";
export type QAExportPreset = "draft" | "web" | "print";
export type QAIssueSeverity = "info" | "warning" | "blocking" | "error";
export type ExportFormat = "zip" | "pdf" | "epub" | "layered" | "png_sequence" | "webtoon" | "archive";
export type ExportStatus = "queued" | "running" | "succeeded" | "failed";
export type AssetSourceType = "user_upload" | "ai_generated" | "stock_licensed" | "internal_mock" | "imported";
export type SafetyCheckTarget = "text_prompt" | "uploaded_image_metadata" | "generated_output_metadata" | "style_request";
export type SafetySeverity = "safe" | "warning" | "blocked";
export type LearningTargetType = "story" | "character" | "panel_render" | "page_layout" | "export" | "style" | "page" | "panel" | string;
export type LearningIssueType =
  | "wrong character"
  | "bad hands"
  | "bad face"
  | "confusing layout"
  | "unreadable text"
  | "inconsistent style"
  | "weak story"
  | "wrong tone"
  | "export problem"
  | "other"
  | string;
export type PanelRenderMode = "storyboard" | "draft" | "final" | "ultra";
export type PanelRerenderControl =
  | "same_seed"
  | "new_seed"
  | "preserve_layout"
  | "change_camera"
  | "change_expression"
  | "additional_instruction";
export type CommandScopeType = "project" | "chapter" | "page" | "panel" | "bubble" | "character" | "style";
export type CommandRiskLevel = "low" | "medium" | "high";
export type CommandStatus = "interpreted" | "executed" | "blocked" | "failed";
export type CommandActionType =
  | "update_story_bible"
  | "update_character_state"
  | "update_style_dna"
  | "suggest_layout"
  | "update_layout"
  | "update_panel_prompt"
  | "rerender_panel"
  | "update_bubble_text"
  | "move_bubble"
  | "run_qa"
  | "apply_qa_fixes"
  | "compose_page"
  | "create_export";

export interface Project {
  id: Id;
  name: string;
  description: string | null;
  style_prompt: string | null;
  status: ProjectStatus | string;
  active_style_bible_id: Id | null;
  allow_training: boolean;
  allow_product_improvement: boolean;
  data_collection_notes: string;
  created_at: string;
  updated_at: string;
}

export interface Page {
  id: Id;
  project_id: Id;
  page_number: number;
  width: number;
  height: number;
  layout_json?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Panel {
  id: Id;
  page_id: Id;
  x: number;
  y: number;
  width: number;
  height: number;
  polygon: LayoutPoint[];
  reading_order: number;
  prompt: string | null;
  created_at: string;
  updated_at: string;
}

export interface PageWithPanels extends Page {
  panels: Panel[];
}

export interface ProjectDetail extends Project {
  pages: PageWithPanels[];
}

export interface ProjectWorkspaceSummary {
  project_id: Id;
  active_chapter_title: string | null;
  page_count: number;
  panel_count: number;
  rendered_panel_count: number;
  render_progress: number;
  qa_score: number | null;
  qa_blocking: boolean;
  export_status: string | null;
  active_job_count: number;
  status_chip: string;
}

export interface CommandScope {
  type: CommandScopeType;
  id: Id;
}

export interface CommandAction {
  action_type: CommandActionType | string;
  target_type: CommandScopeType | string;
  target_id: Id | string;
  summary: string;
  payload: Record<string, unknown>;
  destructive: boolean;
}

export interface CommandInterpretRequest {
  project_id: Id;
  scope: CommandScope;
  command: string;
}

export interface CommandInterpretResult {
  command_id: Id | null;
  project_id: Id;
  intent: string;
  target_type: string;
  target_id: Id | string;
  proposed_actions: CommandAction[];
  requires_confirmation: boolean;
  risk_level: CommandRiskLevel | string;
  summary: string;
}

export interface CommandExecuteRequest extends CommandInterpretRequest {
  confirmed: boolean;
}

export interface CommandExecuteResult extends CommandInterpretResult {
  command_id: Id;
  status: CommandStatus | string;
  executed_actions: Array<Record<string, unknown>>;
  version_ids: Id[];
  error_message: string | null;
}

export interface CommandHistory {
  id: Id;
  project_id: Id;
  scope_type: string;
  scope_id: Id | string;
  command: string;
  intent: string;
  target_type: string;
  target_id: Id | string;
  proposed_actions: CommandAction[];
  executed_actions: Array<Record<string, unknown>>;
  requires_confirmation: boolean;
  confirmed: boolean;
  risk_level: string;
  status: string;
  summary: string;
  error_message: string | null;
  version_ids: Id[];
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: Id;
  project_id: Id | null;
  filename: string;
  kind: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AssetProvenance {
  id: Id;
  asset_id: Id;
  source_type: AssetSourceType | string;
  creator_user_id: string | null;
  provider_name: string | null;
  model_name: string | null;
  prompt_id: string | null;
  generation_job_id: Id | null;
  uploaded_filename: string | null;
  declared_rights: string;
  license_type: string;
  allow_training: boolean;
  allow_commercial_use: boolean;
  ai_disclosure_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface RightsDeclaration {
  id: Id;
  project_id: Id;
  user_confirms_upload_rights: boolean;
  user_confirms_no_unlicensed_ip: boolean;
  user_confirms_review_required_before_publish: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface RightsDeclarationDraft {
  user_confirms_upload_rights: boolean;
  user_confirms_no_unlicensed_ip: boolean;
  user_confirms_review_required_before_publish: boolean;
  notes: string;
}

export interface ProvenanceAsset {
  asset: Asset;
  provenance: AssetProvenance | null;
}

export interface ProvenanceSummary {
  total_assets: number;
  assets_with_provenance: number;
  ai_disclosure_required: boolean;
  source_type_counts: Record<string, number>;
  missing_provenance_asset_ids: Id[];
}

export interface ProjectProvenance {
  project_id: Id;
  rights_declaration: RightsDeclaration | null;
  summary: ProvenanceSummary;
  assets: ProvenanceAsset[];
}

export interface SafetyIssue {
  severity: "warning" | "error";
  code: string;
  message: string;
  field: string | null;
  matched_text: string | null;
}

export interface SafetyCheckResult {
  allowed: boolean;
  severity: SafetySeverity;
  issues: SafetyIssue[];
  suggested_text: string | null;
  suggested_metadata: Record<string, unknown>;
}

export interface CompositePage {
  id: Id;
  page_id: Id;
  project_id: Id | null;
  filename: string;
  storage_key: string;
  public_url: string | null;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  reading_direction: ReadingDirection | string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Render {
  id: Id;
  job_id: Id;
  panel_id: Id;
  asset_id: Id | null;
  storage_key: string;
  public_url: string | null;
  width: number;
  height: number;
  mime_type: string;
  created_at: string;
}

export interface GenerationJob {
  id: Id;
  project_id: Id | null;
  page_id: Id | null;
  panel_id: Id | null;
  provider: ProviderName;
  job_type: JobType | string;
  status: JobStatus;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  render?: Render | null;
}

export interface GenerationJobRetryResult {
  source_job_id: Id;
  job: GenerationJob;
  message: string;
}

export interface PanelRenderPrompt {
  id: Id;
  panel_id: Id;
  prompt_version: string;
  provider_name: string;
  positive_prompt: string;
  negative_prompt: string;
  structured_context: Record<string, unknown>;
  reference_pack: Record<string, unknown>;
  size: string;
  seed: number | null;
  quality_mode: string;
  created_at: string;
  updated_at: string;
}

export interface PanelRenderStartResult {
  job: GenerationJob;
  prompt: PanelRenderPrompt;
}

export interface ProviderCapabilities {
  supports_image_generation: boolean;
  supports_image_editing: boolean;
  supports_references: boolean;
  supports_seeds: boolean;
  supports_async_jobs: boolean;
}

export interface ProviderResolution {
  width: number;
  height: number;
}

export interface ImageProviderStatus {
  name: ProviderName;
  display_name: string;
  model_name: string | null;
  capabilities: ProviderCapabilities;
  max_resolution: ProviderResolution;
  requires_env_vars: string[];
  configured: boolean;
  missing_env_vars: string[];
  cost_warning: string;
  notes: string;
}

export interface ProviderHealth {
  name: ProviderName;
  status: string;
  configured: boolean;
  message: string;
  checked_at: string;
  details: Record<string, unknown>;
}

export interface PanelRenderDryRunResult {
  panel_id: Id;
  provider: ImageProviderStatus;
  provider_configured: boolean;
  can_render: boolean;
  requested_size: string;
  quality_mode: string;
  estimated_cost: Record<string, unknown>;
  cost_metadata: Record<string, unknown>;
  warnings: string[];
  prompt: PanelRenderPrompt;
}

export interface PanelRenderHistoryItem {
  render: Render;
  job: GenerationJob;
  prompt: PanelRenderPrompt | null;
  asset: Asset | null;
  approved: boolean;
}

export interface JobEvent {
  id: Id;
  job_id: Id;
  event_type: DirectorProgressEvent | string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DirectorGenerateDraftRequest {
  premise: string;
  chapter_count: number;
  page_count: number;
  target_audience: string;
  genre: string[];
  tone: string;
  reading_direction: ReadingDirection;
  render_provider: ProviderName;
  quality_mode: DirectorQualityMode;
  allow_mock_assets: boolean;
}

export interface DirectorGenerateDraftResponse {
  job_id: Id;
  project_id: Id;
}

export interface FounderDemoRunRequest {
  premise: string;
  style_option: string;
  page_count: number;
  reading_direction: ReadingDirection;
  render_provider: ProviderName;
  quality_mode: DirectorQualityMode;
  allow_mock_assets: boolean;
}

export interface FounderDemoRunResponse {
  job_id: Id;
  project_id: Id;
}

export interface AITaskRun {
  id: Id;
  prompt_template_id: string;
  task_type: AITaskType | string;
  status: AITaskStatus | string;
  provider: string;
  model: string | null;
  schema_name: string;
  schema_version: string;
  raw_input: Record<string, unknown>;
  raw_output: string | null;
  parsed_output: Record<string, unknown> | unknown[] | null;
  token_metadata: Record<string, unknown>;
  cost_metadata: Record<string, unknown>;
  error_message: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
}

export interface QAIssue {
  id: Id;
  code: string;
  issue_code?: string | null;
  category: string;
  issue_category: string;
  severity: QAIssueSeverity | string;
  confidence: number;
  message: string;
  target_type: string;
  target_id: Id | null;
  page_id: Id | null;
  panel_id: Id | null;
  bubble_id: Id | null;
  blocking: boolean;
  auto_fix_available: boolean;
  auto_fix_action: Record<string, unknown>;
  details: Record<string, unknown>;
}

export interface QARecommendation {
  id: Id;
  message: string;
  target_type: string;
  target_id: Id | null;
  details: Record<string, unknown>;
}

export interface QAReport {
  id: Id;
  target_type: "project" | "page" | "panel" | string;
  target_id: Id;
  issue_code: string | null;
  issue_category: string | null;
  severity: QAIssueSeverity | string | null;
  confidence: number;
  page_id: Id | null;
  panel_id: Id | null;
  auto_fix_available: boolean;
  auto_fix_action: Record<string, unknown>;
  overall_score: number;
  scores: Record<string, number | unknown>;
  issues: QAIssue[];
  recommendations: QARecommendation[];
  blocking: boolean;
  created_at: string;
  updated_at: string;
}

export interface QAAutoFixResult {
  report_id: Id | null;
  project_id: Id | null;
  page_id: Id | null;
  applied: Array<Record<string, unknown>>;
  skipped: Array<Record<string, unknown>>;
  before_report: QAReport | null;
  after_report: QAReport | null;
  page_reports: QAReport[];
  project_report: QAReport | null;
}

export interface QAProjectRunResult {
  project_report: QAReport;
  page_reports: QAReport[];
}

export interface ProjectExport {
  id: Id;
  project_id: Id;
  format: ExportFormat | string;
  status: ExportStatus | string;
  file_asset_id: Id | null;
  options: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  file_asset: Asset | null;
}

export interface ExportPreset {
  id: string;
  name: string;
  description: string;
  page_width: number;
  page_height: number;
  dpi: number;
  bleed: number;
  safe_margin: number;
  color_mode: string;
  reading_direction: ReadingDirection | string;
  file_format: ExportFormat | string;
  compression_quality: number;
  required_qa_gates: string[];
  options: Record<string, unknown>;
}

export interface ProjectPublishingMetadataDraft {
  title: string;
  subtitle: string;
  author_name: string;
  publisher: string;
  language: string;
  synopsis: string;
  age_rating: string;
  genres: string[];
  tags: string[];
  copyright_notice: string;
  ai_disclosure_text: string;
  metadata_json: Record<string, unknown>;
}

export interface ProjectPublishingMetadata extends ProjectPublishingMetadataDraft {
  id: Id;
  project_id: Id;
  created_at: string;
  updated_at: string;
}

export interface FeedbackCreate {
  project_id?: Id | null;
  page_id?: Id | null;
  panel_id?: Id | null;
  category: string;
  severity: "low" | "medium" | "high" | "blocking";
  title: string;
  description: string;
  contact_email?: string | null;
  browser_info?: Record<string, unknown>;
  context?: Record<string, unknown>;
  diagnostic_info?: Record<string, unknown>;
}

export interface FeedbackItem extends FeedbackCreate {
  id: Id;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDataControls {
  project_id: Id;
  allow_training: boolean;
  allow_product_improvement: boolean;
  data_collection_notes: string;
  collected_by_default: boolean;
  explanation: string;
}

export interface GenerationFeedbackCreate {
  project_id?: Id | null;
  target_type: LearningTargetType;
  target_id: Id;
  rating: -1 | 0 | 1 | number;
  issue_type?: LearningIssueType | null;
  comment?: string;
  user_correction?: string;
  before_snapshot_id?: Id | null;
  after_snapshot_id?: Id | null;
  allow_use_for_product_improvement?: boolean;
  metadata_json?: Record<string, unknown>;
}

export interface GenerationFeedback extends GenerationFeedbackCreate {
  id: Id;
  project_id: Id | null;
  allow_use_for_product_improvement: boolean;
  created_at: string;
  updated_at: string;
}

export interface LearningFeedbackOptions {
  issue_tags: Array<{ id: LearningIssueType; label: string }>;
  default_allow_use_for_product_improvement: boolean;
  collection_explanation: string;
}

export interface ImprovementReport {
  generated_at: string;
  privacy_note: string;
  generation_success_rate: number;
  retry_rate: number;
  provider_failure_rate: Record<string, number>;
  qa_failure_categories: Record<string, number>;
  average_page_qa_score: number | null;
  export_success_rate: number;
  most_common_failures: Array<Record<string, unknown>>;
  worst_performing_pipeline_stage: string;
  best_performing_style_or_preset: string | null;
  qa_trends: Record<string, unknown>;
  provider_reliability: Array<Record<string, unknown>>;
  recommended_engineering_priorities: string[];
}

export interface AlphaOnboardingInfo {
  auth: Record<string, unknown>;
  welcome_title: string;
  welcome_message: string;
  first_demo_premise: string;
  provider_modes: Array<Record<string, unknown>>;
  suggested_first_steps: string[];
  safety_rules: string[];
  docs: Array<{ label: string; href: string }>;
}

export interface AlphaDashboardMetric {
  label: string;
  value: number | string;
  detail: string;
}

export interface AlphaDashboard {
  metrics: AlphaDashboardMetric[];
  failed_jobs: GenerationJob[];
  provider_errors: GenerationJob[];
  feedback_items: FeedbackItem[];
  recent_qa_failures: QAReport[];
}

export interface ExportReadinessItem {
  key: string;
  label: string;
  passed: boolean;
  severity: "info" | "warning" | "blocking" | string;
  message: string;
  details: Record<string, unknown>;
}

export interface ExportReadiness {
  project_id: Id;
  preset: ExportPreset;
  ready: boolean;
  force_required: boolean;
  checklist: ExportReadinessItem[];
  page_count: number;
  blocking_issue_count: number;
  metadata: ProjectPublishingMetadata | null;
}

export interface ExportPreview {
  project_id: Id;
  preset: ExportPreset;
  readiness: ExportReadiness;
  estimated_files: string[];
  estimated_size_bytes: number;
  warnings: string[];
  metadata_preview: Record<string, unknown>;
}

export interface VersionRecord {
  id: Id;
  project_id: Id | null;
  parent_id: Id | null;
  entity_type: string;
  entity_id: Id;
  snapshot_json: Record<string, unknown>;
  asset_ids: Id[];
  label: string;
  created_by: string;
  created_at: string;
  reason: string;
  is_checkpoint: boolean;
}

export interface VersionRestoreResult {
  restored_version: VersionRecord;
}

export interface VersionDiffResult {
  version_a: Record<string, unknown>;
  version_b: Record<string, unknown>;
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: Record<string, unknown>;
}

export interface DemoPipelineResult {
  project: Project;
  story_bible_id: Id;
  chapter_id: Id;
  page_ids: Id[];
  panel_ids: Id[];
  render_job_ids: Id[];
  composite_asset_ids: Id[];
  qa_report_ids: Id[];
  exports: Record<string, Id>;
}

export interface EvalScenario {
  id: string;
  name: string;
  premise: string;
  genre: string[];
  tone: string;
  target_audience: string;
  page_count: number;
  expected_character_count: number;
  expected_location_count: number;
  expected_key_beats: string[];
  expected_page_types: string[];
  export_requirements: string[];
  reading_direction: ReadingDirection | string;
  expected_panel_count?: number;
}

export interface EvalScenarioReport {
  scenario: EvalScenario;
  project_id: Id;
  job_id: Id;
  status: string;
  duration_seconds: number;
  scores: Record<string, number | string | null>;
  metrics: Record<string, number | string | null>;
  counts: Record<string, number>;
  generated: Record<string, unknown>;
  failures: string[];
  links: Record<string, string>;
}

export interface EvalRunReport {
  run_id: Id;
  created_at: string;
  completed_at: string;
  provider: string;
  quality_mode: string;
  scenario_selector: string;
  scenario_count: number;
  metrics: Record<string, number | string | null>;
  scenarios: EvalScenarioReport[];
}

export interface StoryBibleCreate {
  premise?: string | null;
  genre?: string | null;
  tone?: string | null;
  target_audience?: string | null;
  chapter_count?: number;
}

export interface StoryCharacter {
  id?: Id | null;
  name: string;
  role: string;
  description: string;
  traits: string[];
  visual_notes: string | null;
}

export interface StoryLocation {
  id?: Id | null;
  name: string;
  description: string;
  visual_notes: string | null;
  rules: string[];
}

export interface StoryKeyObject {
  id?: Id | null;
  name: string;
  description: string;
  significance: string;
  visual_notes: string | null;
}

export interface ChapterOutlineItem {
  chapter_number: number;
  title: string;
  summary: string;
}

export interface StyleBible {
  id?: Id | null;
  visual_style: string;
  line_art: string;
  palette: string;
  paneling: string;
  lettering: string;
  negative_prompts: string[];
}

export interface StoryBible {
  id?: Id | null;
  project_id?: Id | null;
  logline: string;
  synopsis: string;
  genre: string;
  themes: string[];
  target_audience: string;
  tone: string;
  main_conflict: string;
  world_rules: string[];
  characters: StoryCharacter[];
  locations: StoryLocation[];
  key_objects: StoryKeyObject[];
  chapter_outline: ChapterOutlineItem[];
  continuity_rules: string[];
  style_bible: StyleBible | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScenePlan {
  id?: Id | null;
  scene_order: number;
  title: string;
  summary: string;
  location_name: string | null;
  emotional_turn: string | null;
  characters: string[];
}

export interface ChapterPlan {
  id?: Id | null;
  project_id?: Id | null;
  story_bible_id?: Id | null;
  chapter_number: number;
  title: string;
  summary: string;
  goal: string;
  scenes: ScenePlan[];
}

export interface PanelPlan {
  id?: Id | null;
  page_plan_id?: Id | null;
  panel_order: number;
  story_beat: string;
  shot_type: string;
  camera_angle: string;
  characters: string[];
  location: string | null;
  dialogue: string | null;
  narration: string | null;
  visual_notes: string;
  emotional_intent: string;
  beat_importance: number;
  time_duration: string;
  camera_motion: string;
  motion_intensity: number;
  dialogue_weight: number;
  silence: boolean;
  impact_level: number;
  recommended_panel_size: string;
  transition_type: string;
}

export interface PagePlan {
  id?: Id | null;
  project_id?: Id | null;
  chapter_id?: Id | null;
  page_number: number;
  summary: string;
  pacing: string;
  page_role: string;
  emotional_intensity: number;
  action_intensity: number;
  dialogue_density: number;
  silence_level: number;
  reveal_level: number;
  page_turn_importance: number;
  recommended_page_type: string;
  pacing_notes: string;
  panels: PanelPlan[];
}

export interface PacingPanelAnalysis {
  panel_plan_id: Id;
  panel_order: number;
  beat_importance: number;
  time_duration: string;
  camera_motion: string;
  motion_intensity: number;
  dialogue_weight: number;
  silence: boolean;
  impact_level: number;
  recommended_panel_size: string;
  transition_type: string;
  notes: string[];
}

export interface PacingPageAnalysis {
  page_plan_id: Id;
  page_number: number;
  page_role: string;
  emotional_intensity: number;
  action_intensity: number;
  dialogue_density: number;
  silence_level: number;
  reveal_level: number;
  page_turn_importance: number;
  recommended_page_type: string;
  pacing_notes: string;
  panel_count: number;
  panels: PacingPanelAnalysis[];
}

export interface PacingRecommendation {
  code: string;
  severity: "info" | "warning" | "blocking" | string;
  target_type: string;
  target_id: Id;
  page_number: number | null;
  message: string;
  suggested_action: string;
  details: Record<string, unknown>;
}

export interface PacingAnalysisResult {
  project_id: Id;
  chapter_id: Id | null;
  pages: PacingPageAnalysis[];
  recommendations: PacingRecommendation[];
  summary: Record<string, unknown>;
}

export interface PacingRebalanceResult extends PacingAnalysisResult {
  updated_page_plan_ids: Id[];
  updated_panel_plan_ids: Id[];
  version_ids: Id[];
}

export type ReadingDirection = "rtl" | "ltr" | "vertical-rl";
export type BubbleKind = "speech" | "thought" | "narration" | "shout" | "whisper" | "radio" | "monster" | "offscreen";
export type PageType =
  | "standard"
  | "splash"
  | "double_spread_left"
  | "double_spread_right"
  | "silent_page"
  | "action_sequence"
  | "dialogue_scene"
  | "reveal_page"
  | "comedy_reaction"
  | "horror_build"
  | "romantic_pause"
  | "exposition_page";

export interface LayoutPoint {
  x: number;
  y: number;
}

export interface Bubble {
  id: Id;
  panel_id: Id;
  kind: BubbleKind | string;
  bubble_type: BubbleKind | string;
  speaker_character_id: Id | null;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  language: string;
  reading_direction: ReadingDirection | string;
  shape: string;
  position: Record<string, unknown>;
  size: Record<string, unknown>;
  tail_target: Record<string, unknown>;
  font_family: string;
  font_size: number;
  font_weight: string;
  text_align: string;
  vertical_text: boolean;
  z_index: number;
  locked: boolean;
  created_at: string;
  updated_at: string;
}

export interface SFXElement {
  id: Id;
  page_id: Id;
  panel_id: Id | null;
  text: string;
  meaning: string;
  style: string;
  position: Record<string, unknown>;
  size: Record<string, unknown>;
  rotation: number;
  warp_style: string;
  stroke_width: number;
  fill: string;
  outline: string;
  z_index: number;
  locked: boolean;
  created_at: string;
  updated_at: string;
}

export interface LetteringPage {
  page_id: Id;
  bubbles: Bubble[];
  sfx: SFXElement[];
  warnings: string[];
}

export interface LetteringGenerateResult extends LetteringPage {
  created_bubble_ids: Id[];
  created_sfx_ids: Id[];
}

export interface PanelLayout {
  id: Id;
  page_id: Id;
  x: number;
  y: number;
  width: number;
  height: number;
  polygon: LayoutPoint[];
  reading_order: number;
  prompt: string | null;
  bubbles: Bubble[];
}

export interface PageLayout {
  page_id: Id;
  width: number;
  height: number;
  bleed: number;
  safe_margin: number;
  reading_direction: ReadingDirection;
  qa_overlay_enabled: boolean;
  panels: PanelLayout[];
}

export interface LayoutTemplate {
  id: Id;
  project_id: Id;
  name: string;
  page_type: PageType;
  panel_count: number;
  reading_direction: ReadingDirection;
  emotional_use: string;
  action_level: string;
  density: string;
  layout_json: Record<string, unknown>;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface LayoutTemplateCreate {
  name: string;
  page_type: PageType;
  panel_count: number;
  reading_direction: ReadingDirection;
  emotional_use?: string;
  action_level?: string;
  density?: string;
  layout_json?: Record<string, unknown>;
  notes?: string;
}

export interface LayoutSlot {
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string | null;
  notes?: string | null;
}

export interface LayoutValidationIssue {
  severity: "info" | "warning" | "error";
  code: string;
  message: string;
  panel_order?: number | null;
}

export interface SuggestedPanelLayout {
  id?: Id | null;
  x: number;
  y: number;
  width: number;
  height: number;
  polygon: LayoutPoint[];
  reading_order: number;
  prompt?: string | null;
  story_beat?: string | null;
  emotional_beat?: string | null;
  importance: number;
  locked: boolean;
  bubble_slots: LayoutSlot[];
  sfx_slots: LayoutSlot[];
}

export interface LayoutSuggestion {
  page_id: Id;
  width: number;
  height: number;
  bleed: number;
  safe_margin: number;
  reading_direction: ReadingDirection;
  page_type: PageType;
  template_id?: Id | null;
  layout_reasoning: string[];
  validation_issues: LayoutValidationIssue[];
  panels: SuggestedPanelLayout[];
}

export interface CharacterCard {
  id: Id;
  project_id: Id;
  name: string;
  aliases: string[];
  age_range: string;
  role: string;
  personality: string;
  face_description: string;
  hair_description: string;
  eye_description: string;
  body_type: string;
  outfit_default: string;
  accessories: string[];
  scars_marks: string;
  voice_style: string;
  forbidden_changes: string[];
  continuity_rules: string[];
  canonical_visual_summary: string;
  silhouette_keywords: string[];
  face_anchor_description: string;
  hair_anchor_description: string;
  eye_anchor_description: string;
  body_anchor_description: string;
  outfit_anchor_description: string;
  color_notes_even_for_bw: string;
  recurring_props: string[];
  allowed_variations: string[];
  forbidden_variations: string[];
  current_story_state: string;
  injury_state: string;
  emotional_baseline: string;
  reference_asset_ids: string[];
  approved_panel_asset_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CharacterState {
  id: Id;
  character_id: Id;
  chapter_id: Id;
  scene_id: Id;
  page_id: Id | null;
  outfit_state: string;
  injury_state: string;
  emotional_state: string;
  prop_state: string;
  visibility_notes: string;
  continuity_notes: string;
  created_at: string;
  updated_at: string;
}

export interface CharacterReferenceAsset {
  id: Id;
  project_id: Id;
  character_card_id: Id;
  filename: string;
  kind: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ReferencePackCharacter {
  card: CharacterCard;
  state: CharacterState | null;
  reference_assets: CharacterReferenceAsset[];
  approved_panel_assets: Asset[];
  missing_state: boolean;
}

export interface ReferencePack {
  panel_id: Id;
  page_id: Id;
  project_id: Id;
  style_bible: Record<string, unknown> | null;
  story_memory: Record<string, unknown>;
  characters: ReferencePackCharacter[];
  character_states: CharacterState[];
  locations: StoryLocation[];
  key_objects: StoryKeyObject[];
  approved_visual_references: Record<string, unknown>[];
  continuity_rules: string[];
  previous_summaries: Array<{
    panel_id: Id;
    reading_order: number;
    prompt: string | null;
    summary: string | null;
  }>;
  required_anchor_names: string[];
  missing_character_state_ids: Id[];
}

export interface PagePanelReferencePackSummary {
  panel_id: Id;
  reading_order: number;
  characters: string[];
  active_states: CharacterState[];
  missing_state_character_ids: Id[];
  warning: string | null;
}

export interface PageReferencePacks {
  page_id: Id;
  panels: PagePanelReferencePackSummary[];
}

export interface ExpressionSheet {
  id: Id;
  project_id: Id;
  character_card_id: Id;
  name: string;
  expressions: string[];
  asset_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface GenerateCharacterSheetResult {
  job: GenerationJob;
  assets: CharacterReferenceAsset[];
  expression_sheet: ExpressionSheet;
}

export interface StyleBibleLab {
  id: Id;
  project_id: Id;
  story_bible_id: Id | null;
  name: string;
  style_name: string;
  style_intent: string;
  line_weight: string;
  line_variation: string;
  line_texture: string;
  face_shape_language: string;
  eye_design_language: string;
  nose_mouth_simplification: string;
  anatomy_proportions: string;
  hair_rendering: string;
  clothing_fold_style: string;
  background_density: string;
  architecture_detail: string;
  shadow_strategy: string;
  screentone_strategy: string;
  hatching_strategy: string;
  black_fill_ratio: string;
  speedline_style: string;
  impact_frame_style: string;
  panel_border_style: string;
  gutter_style: string;
  sfx_shape_language: string;
  bubble_style: string;
  emotional_visual_rules: string[];
  positive_prompt_fragments: string[];
  negative_prompt_fragments: string[];
  forbidden_artist_references: string[];
  forbidden_franchise_references: string[];
  linework: string;
  screentone: string;
  hatching: string;
  black_white_balance: string;
  face_language: string;
  anatomy_style: string;
  background_detail: string;
  panel_rhythm: string;
  sfx_style: string;
  typography_notes: string;
  forbidden_references: string[];
  prompt_style_positive: string;
  prompt_style_negative: string;
  created_at: string;
  updated_at: string;
}

export type StyleGuardSeverity = "safe" | "warning" | "blocked";

export interface StyleGuardIssue {
  severity: "warning" | "error";
  code: string;
  message: string;
  field: string | null;
  matched_text: string | null;
}

export interface StyleGuardResult {
  allowed: boolean;
  severity: StyleGuardSeverity;
  issues: StyleGuardIssue[];
  suggested_style: Record<string, unknown>;
}

export interface StyleDNAGenerateRequest {
  genre: string;
  tone: string;
  audience: string;
  visual_keywords: string[];
  avoid_keywords: string[];
  sample_story_summary: string;
}

export type StyleDNAOption = Omit<
  StyleBibleLab,
  | "id"
  | "project_id"
  | "story_bible_id"
  | "name"
  | "linework"
  | "screentone"
  | "hatching"
  | "black_white_balance"
  | "face_language"
  | "anatomy_style"
  | "background_detail"
  | "panel_rhythm"
  | "sfx_style"
  | "forbidden_references"
  | "prompt_style_positive"
  | "prompt_style_negative"
  | "created_at"
  | "updated_at"
> & {
  preview_prompt: string;
};

export interface StyleDNAOptionsResult {
  options: StyleDNAOption[];
}

export interface StylePreviewResult {
  asset: Asset;
  public_url: string;
  preview_prompt: string;
  safety: StyleGuardResult;
}

export interface StyleSampleAsset {
  id: Id;
  project_id: Id;
  style_bible_id: Id;
  filename: string;
  kind: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
