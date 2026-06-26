# Render Pipeline

## Provider Render Pipeline

The render pipeline is provider-based while staying deterministic for tests through `MockImageProvider`.

1. User creates a project in the web dashboard.
2. User creates a page, saves panel layout in Page Studio, and selects a panel.
3. User chooses a provider and starts a panel render.
4. API validates the panel, creates a `generation_jobs` row with provider/options, and enqueues Celery when background jobs are enabled.
5. If `ENABLE_BACKGROUND_JOBS=false`, the API runs the same render orchestrator synchronously for tests and fallback local development.
6. Worker or synchronous fallback marks the job `running`.
7. `RenderOrchestrator` assembles prompt JSON from project style, story bible, page plan, panel plan, character cards, location/object references, and panel layout.
8. Worker or synchronous fallback calls the selected `ImageProvider`.
9. The PNG is uploaded to object storage.
10. The API creates an `assets` row and a `renders` row and stores prompt/provider/model/seed/options metadata on the job and asset.
11. The job is marked `succeeded`.
12. Web polls `GET /jobs/{id}` and displays the latest status plus the output image inside the panel.

## Demo Pipeline

`POST /demo/create-full-project` creates a complete deterministic manga project and validates the full pipeline in one call:

- project
- story bible
- two characters
- one location
- one key object
- one active style bible
- one chapter
- four pages
- eight panels
- bubbles/dialogue
- mock render assets
- final composite page PNGs
- QA reports
- ZIP and PDF exports

Providers:

- `mock`: deterministic placeholder PNG generation for local development and tests.
- `openai`: uses the official OpenAI SDK for `generate_image`; requires `OPENAI_API_KEY` only when selected.
- `comfyui`: submits a workflow JSON template to `COMFYUI_BASE_URL` when available and returns a clear provider error until output retrieval is implemented.

## Director Mode Pipeline

Director Mode turns one user premise into a complete draft project through an async generation job.

1. Web calls `POST /projects/{id}/director/generate-draft` with premise, chapter count, page count, audience, genres, tone, reading direction, render provider, quality mode, and mock fallback preference.
2. API creates or updates the project and inserts a `director_generate_draft` generation job.
3. API writes a `queued` `job_events` row and either enqueues Celery or runs the orchestrator synchronously when `ENABLE_BACKGROUND_JOBS=false`.
4. `MangaDirectorOrchestrator` emits ordered events for story bible generation, characters, style, page planning, layouts, rendering, composition, QA, export, completion, or failure.
5. The orchestrator stores intermediate ids in `generation_jobs.output_payload.director_state`, so already-completed steps can be skipped on a rerun.
6. Story and lab records are generated deterministically from the premise for local development.
7. Page layouts are created with the requested reading direction and rectangular panel polygons.
8. Bubbles are created from generated panel dialogue or narration.
9. Panel renders use the selected provider. If provider rendering fails and mock fallback is allowed, mock images are generated for those panels.
10. Pages are composed with the existing compositor.
11. QA reports are run for each page.
12. A draft ZIP export is created after non-blocking QA.
13. Web polls `GET /jobs/{id}` and `GET /jobs/{id}/events`, then links to the generated project rooms and pages.

## Story Engine Pipeline

The Story Engine is synchronous for this milestone.

1. Story Room requests a story bible for a project.
2. FastAPI builds structured task inputs from project metadata and `StoryBibleCreate`.
3. `AITaskRunner` loads the latest `generate_story_bible` prompt template from `services/api/app/prompts`.
4. The runner renders variables, calls the configured `LLMProvider`, validates JSON against `StoryBibleResult`, retries invalid JSON, and calls `repair_invalid_json` when needed.
5. The runner stores `prompt_templates` and `ai_task_runs` records with raw input, raw output, parsed output, provider/model, schema version, and metadata.
6. FastAPI persists the story bible, characters, locations, key objects, and style bible.
7. Story Room requests a chapter plan.
8. FastAPI persists chapters and scenes from `ChapterPlanResult`.
9. Story Room requests page plans for a chapter.
10. FastAPI persists page plans and panel plans from `PagePlanResult` and `PanelPlanResult`.

The mock provider returns deterministic JSON so tests do not need network access or API keys.

## AI Task Registry Pipeline

The prompt registry provides versioned prompt contracts for all AI-oriented tasks:

- story bible generation
- character cards
- location/object cards
- style bible
- chapter/page/panel planning
- layout planning
- panel render prompt compilation
- bubble planning
- page/panel critique
- invalid JSON repair

Every prompt file includes a stable id, semantic version, task type, system prompt, user prompt template, output schema name, default options, safety notes, and changelog. Snapshot tests run every registered prompt through `MockLLMProvider` and validate the output with Pydantic.

## Page Studio Pipeline

Page Studio is an interactive frontend editor backed by synchronous layout endpoints.

1. The web app loads a page layout from `GET /pages/{id}/layout`.
2. Konva renders the manga page canvas, bleed area, safe margin, panels, and bubbles.
3. Panel drag and resize operations update local page-space geometry and rectangular polygons.
4. `PUT /pages/{id}/layout` saves page settings and panel layout.
5. Bubble creation and text edits persist through panel and bubble endpoints.

Validation keeps panels inside page bounds, ensures panel reading order is unique per page, rejects empty bubble text, and stores the selected reading direction.

## Page Composition Pipeline

Page composition exports the saved layout as a final PNG.

1. Page Studio calls `POST /pages/{id}/compose`.
2. FastAPI loads the page layout, panels, bubbles, and latest successful render for each panel.
3. `PageCompositor` creates a white page at the configured page size.
4. Panel renders are fitted into panel polygon masks, preserving white gutters between panels.
5. Black panel borders are drawn over each polygon.
6. Speech, thought, narration, and shout bubbles are drawn over the page.
7. Text is wrapped and auto-fit into each bubble with a basic font-size search.
8. The final PNG is written to object storage and stored as an `assets.kind = page_composite` row.
9. Page Studio calls `GET /pages/{id}/composite` to preview and download the latest final PNG.

## Manga QA Pipeline

Manga QA is deterministic for local development and tests.

1. Page Studio calls `POST /pages/{id}/qa` with a selected export preset.
2. FastAPI loads page plan, page layout, panels, bubbles, latest panel renders, and latest final composite.
3. `PageQAService` runs structural checks for panel count, bounds, overlap, render coverage, bubble placement/text/coverage, composite presence, and export resolution.
4. `MockQAProvider` returns a deterministic report draft from those checks.
5. FastAPI persists a `QAReport` row with overall score, category scores, issues, recommendations, and blocking status.
6. Page Studio calls `GET /pages/{id}/qa/latest` to restore the latest score panel.
7. Clicking an issue highlights the referenced panel or bubble on the canvas.

`OpenAIQAProvider` is an environment-reading stub for future multimodal critique. It is not required for tests.

## Publishing Pipeline

Publishing Room creates project-level deliverables synchronously for the MVP.

1. The user selects ZIP, PDF, EPUB, or layered package in Publishing Room.
2. FastAPI creates an `exports` row in `running` status.
3. The exporter verifies that no page has latest blocking QA issues unless `force=true`.
4. The exporter loads final composite PNGs and project/page metadata.
5. ZIP exports include final page PNGs and `project.json`.
6. PDF exports use the final page PNGs as fixed pages.
7. EPUB exports create a fixed-layout skeleton with page images, OPF, nav, and metadata.
8. Layered packages include layout JSON, panel images, bubble JSON/SVG, final composites, and metadata.
9. The output file is stored as a `project_export` asset and the export row is marked `succeeded`.
10. `GET /exports/{id}/download` streams the stored file.

## Character And Style Lab Pipeline

Character Lab and Style Lab are metadata-first workflows.

1. Character cards and style bibles are created and edited through synchronous CRUD endpoints.
2. Reference and style sample upload endpoints store metadata only; real file upload and image generation are future work.
3. `POST /characters/{id}/generate-character-sheet` creates deterministic placeholder character sheet assets and a completed mock job.
4. Style Lab can attach a style bible as the project's active style for future prompt/render workflows.

## Failure Handling

If the worker raises while processing a job, it marks the job `failed` and stores the exception text in `error_message`.

Retry policy is not enabled yet. Add retries once real provider calls are introduced and provider-specific idempotency rules are defined.

## Adding Providers

New providers should be added behind the image provider interface:

```python
class ImageProvider(Protocol):
    name: str
    model_name: str

    def generate_image(self, prompt: str, size: str, references: list[dict], options: dict) -> GeneratedImage:
        ...

    def edit_image(self, input_image: bytes, mask: bytes | None, prompt: str, options: dict) -> GeneratedImage:
        ...
```

Recommended integration path:

- Add provider-specific settings through environment variables.
- Add a provider class without changing API route contracts.
- Validate provider input before enqueuing jobs.
- Store raw provider request and response metadata in JSON payload fields.
- Keep object storage writes centralized through `ObjectStorage`.
- Keep generated render records normalized in `renders`.
- For story planning, implement `LLMProvider.generate_structured(schema, system_prompt, user_prompt)` and validate provider output through the supplied Pydantic schema before saving.

## Future Pipeline Milestones

- Upload source assets to MinIO and attach them to projects.
- Add storyboard and script generation job types.
- Add panel-to-panel character consistency references.
- Add provider-specific job retries and cancellation.
- Add render versioning per panel.
