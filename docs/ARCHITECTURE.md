# Architecture

## Overview

Manga AI Studio is split into six boundaries:

- `apps/web`: Next.js, TypeScript, Tailwind, and shadcn/ui-style components.
- `services/api`: FastAPI service that owns HTTP routes, validation, persistence, and job creation.
- `services/worker`: Celery worker that consumes render jobs and writes outputs to object storage.
- `packages/shared`: TypeScript interfaces and JSON Schemas for frontend and service contracts.
- `infra`: local infrastructure notes and Compose-managed dependencies.
- `docs`: architecture, data model, and pipeline documentation.

## Runtime Services

Local development is orchestrated by Docker Compose:

- PostgreSQL stores projects, pages, panels, asset metadata, jobs, and renders.
- Redis is the Celery broker and result backend.
- MinIO provides local S3-compatible object storage.
- The API runs Alembic migrations before starting Uvicorn.
- The worker imports the API package models so database contracts stay aligned.
- The web app calls the API through `NEXT_PUBLIC_API_BASE_URL` in the browser and `API_INTERNAL_URL` from server-side Next.js code.

## Request Flow

1. The web app creates projects, pages, and panels through FastAPI.
2. `POST /jobs/render-panel` creates a `generation_jobs` row in `queued` status with provider and options.
3. The API enqueues a Celery task when `ENABLE_BACKGROUND_JOBS=true`; when it is false, the API renders synchronously through the same orchestrator for tests and fallback local development.
4. The worker or synchronous fallback loads the job and panel, assembles render prompt JSON, calls the selected image provider, writes the PNG to object storage, creates `assets` and `renders` rows, and marks the job `succeeded`.
5. The web app polls `GET /jobs/{id}` and displays the job status and render preview when available.

## Demo Flow

`POST /demo/create-full-project` is the golden-path integration route. It creates a complete deterministic project from a fixed premise, then exercises the production services for rendering, composition, QA, and ZIP/PDF export. The endpoint is useful for demos, smoke checks, and verifying object storage connectivity.

## Director Flow

Director Mode is the user-driven orchestration route:

- `POST /projects/{id}/director/generate-draft` creates a `director_generate_draft` generation job.
- `GET /jobs/{id}/events` returns ordered progress events for that job.
- When background jobs are enabled, the API enqueues `manga_worker.director_generate_draft`; when disabled, the same orchestrator runs synchronously for tests and simple local smoke checks.
- `MangaDirectorOrchestrator` stores resumable intermediate state in `generation_jobs.output_payload.director_state`.
- The orchestrator creates or updates the project, story bible, character records, Character Lab cards, locations, key objects, style bible, chapters, page plans, panel plans, page layouts, bubbles, panel renders, page composites, QA reports, and a draft ZIP export.
- If a selected image provider fails and `allow_mock_assets=true`, panel rendering falls back to deterministic mock assets instead of losing the draft.

## Health Flow

The API exposes shallow and dependency-specific health checks:

- `/health`
- `/health/db`
- `/health/redis`
- `/health/storage`
- `/health/worker`

Dependency checks return `503` with JSON details when a dependency is unavailable.

## Story Flow

1. Story Room calls `POST /projects/{id}/story/generate-bible`.
2. The API calls `AITaskRunner` with the registered prompt template, inputs, output schema, and configured `LLMProvider`.
3. `AITaskRunner` renders the prompt, calls the provider, validates JSON output, retries invalid JSON, invokes the repair prompt if needed, and stores an `ai_task_runs` audit row.
4. The mock provider returns deterministic valid JSON for local development and tests.
5. The API saves the story bible plus nested characters, locations, key objects, and style bible data.
6. Story Room calls `POST /projects/{id}/story/generate-chapter-plan` to persist chapters and scenes.
7. Story Room calls `POST /chapters/{id}/story/generate-page-plans` to persist page and panel plans.

## Prompt Registry Flow

Prompt templates live in `services/api/app/prompts` as versioned JSON files. Each template declares task type, prompts, output schema, default options, safety notes, and changelog. The runner mirrors used templates into `prompt_templates` and stores executions in `ai_task_runs`.

Supported task types include story bible, character cards, locations/objects, style bible, chapter/page/panel planning, layout planning, panel prompt compilation, bubble planning, page/panel critique, and invalid JSON repair.

The internal admin route `/admin/ai-task-runs` is disabled unless `ENABLE_DEV_ADMIN=true` on the API and `NEXT_PUBLIC_ENABLE_DEV_ADMIN=true` on the web app.

## Page Studio Flow

1. Page Studio loads `GET /pages/{id}/layout`.
2. The editor renders the page and panels with Konva using page-space coordinates.
3. Users edit page dimensions, bleed, safe margin, reading direction, panel geometry, and QA overlay state locally.
4. `PUT /pages/{id}/layout` validates panel bounds, unique reading order, and reading direction before saving.
5. Speech bubbles and narration boxes are persisted through `POST /panels/{id}/bubbles` and `PUT /bubbles/{id}`.
6. `POST /pages/{id}/compose` exports the saved layout as a final page PNG and `GET /pages/{id}/composite` returns the latest composite asset.

## Composition Flow

The API owns page composition through `PageCompositor` in `manga_api.compositor`. It loads saved page layout, latest successful panel renders, and bubbles, then uses Pillow to place panel images into polygon masks, preserve white gutters, draw black borders, letter bubble text, and upload a `page_composite` PNG asset to object storage.

## QA Flow

Manga QA is owned by `PageQAService` in `manga_api.qa`. It produces persisted `QAReport` rows for page targets by checking page plans, panel geometry, render completion, lettering, final composites, and export resolution presets. `MockQAProvider` is deterministic for tests and development; `OpenAIQAProvider` reads OpenAI environment settings but is intentionally a future multimodal critique stub.

## Publishing Flow

Publishing Room calls `POST /projects/{id}/exports` to create ZIP, PDF, EPUB, or layered project packages. The API-owned `ProjectExporter` checks latest QA reports, gathers final page composites, embeds metadata and provenance, stores the generated file as a `project_export` asset, and serves it through `GET /exports/{id}/download`.

## Lab Flow

Character Lab manages `CharacterCard` records and metadata-only reference assets. The mock `generate-character-sheet` endpoint creates a completed `GenerationJob`, placeholder reference asset records, and an `ExpressionSheet`; it does not call image models.

Style Lab manages project `StyleBible` records, metadata-only sample assets, and the active style pointer on `Project.active_style_bible_id`.

## Provider Abstraction

Panel rendering uses `ImageProvider` and `RenderOrchestrator` in `manga_api.rendering`. The API stores `provider`, prompt JSON, provider options, model name, normalized outputs, and errors on every `GenerationJob`. The worker supplies object storage and delegates provider execution to the same orchestrator used by tests.

Available image providers:

- `mock`: deterministic placeholder PNGs for local development and tests.
- `openai`: official OpenAI SDK integration for image generation; reads `OPENAI_API_KEY` and `OPENAI_IMAGE_MODEL`.
- `comfyui`: submits workflow JSON to `COMFYUI_BASE_URL` when configured and fails clearly when ComfyUI is unavailable or output retrieval is not implemented.

The API uses `LLMProvider` in `manga_api.llm` for story planning. `MockLLMProvider` is deterministic; `OpenAIProvider` is a stub that reads `OPENAI_API_KEY` and `OPENAI_MODEL` from environment variables.

Future provider integrations should:

- Implement the `ImageProvider` protocol.
- Keep credentials in environment variables or managed secrets.
- Store provider-specific inputs in `input_payload`.
- Store normalized outputs in `output_payload`.
- Preserve the same `assets` and `renders` persistence path.

## Local Security Posture

The repository includes safe local defaults for development. Production deployment should replace them with managed credentials, private buckets, restricted CORS origins, TLS, and a proper secrets backend.
