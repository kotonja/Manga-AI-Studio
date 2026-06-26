# Manga AI Studio

Manga AI Studio is a local-first AI manga creation monorepo. It includes a Next.js web app, FastAPI API, Celery worker, PostgreSQL, Redis, MinIO object storage, and shared TypeScript/JSON Schema contracts.

The default local provider stack is deterministic and does not require OpenAI, ComfyUI, or external APIs.

Local development is unlocked by default. Private alpha mode can enable simple shared-password/token auth, project owner scoping, and protected asset/export downloads without changing the one-command Docker workflow.

## Structure

```text
manga-ai/
  apps/web
  services/api
  services/worker
  packages/shared
  infra
  docs
  scripts
```

## Quick Start

Requirements:

- Docker Desktop with Docker Compose
- Optional for non-Docker checks: Node.js 20+, pnpm 11+, Python 3.12+

Run the full stack:

```bash
cd manga-ai
docker compose up --build
```

Or use the helper:

```bash
sh scripts/dev.sh
```

On Windows PowerShell, use `docker compose up --build` directly unless you are running Git Bash or WSL.

Local URLs:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001
- API health: http://localhost:8000/health

Default MinIO credentials are `minioadmin` / `minioadmin` for local development only.

## Demo Manga

Create a complete deterministic demo project from the premise:

> A lonely swordsman protects a ghost child in a ruined city.

From the web dashboard, click **Create Demo Manga**.

From the API:

```bash
curl -X POST http://localhost:8000/demo/create-full-project \
  -H "Content-Type: application/json" \
  -d "{}"
```

Or:

```bash
sh scripts/seed-demo.sh
```

The demo creates a project, story bible, two characters, one location, one style bible, one chapter, four pages, panels, bubbles, mock panel renders, final page composites, QA reports, and ZIP/PDF exports.

## Director Mode

Director Mode creates a complete draft manga from one premise for any project:

```http
POST /projects/{project_id}/director/generate-draft
```

The request selects chapter count, page count, target audience, genres, tone, reading direction, render provider, quality mode, and whether mock assets may be used as fallback. The response returns a generation job id, and progress is available at:

```http
GET /jobs/{job_id}/events
```

In the web app, open a project and click **Director Mode**. With the mock provider, the full draft pipeline runs without external API keys.

## Prompt Registry And AI Task Runs

Prompt templates live in `services/api/app/prompts` and are versioned JSON contracts for story, planning, prompt compilation, critique, and repair tasks. `AITaskRunner` validates provider output against Pydantic schemas, retries invalid JSON, repairs when possible, and stores every run in `ai_task_runs`.

The internal page `/admin/ai-task-runs` is disabled by default. For local debugging only, set both:

```bash
ENABLE_DEV_ADMIN=true
NEXT_PUBLIC_ENABLE_DEV_ADMIN=true
```

## Evaluation Harness

Run repeatable manga generation scenarios and write `eval_reports/latest.json` plus `eval_reports/latest.md`:

```bash
docker compose exec api python -m app.eval.run --scenario all --provider mock
```

The dev-only web page is `/admin/eval` when `ENABLE_DEV_ADMIN=true` and `NEXT_PUBLIC_ENABLE_DEV_ADMIN=true`.

## Production Deployment

Production-ready Docker targets, environment examples, migration guidance, worker deployment notes, object storage configuration, reverse proxy notes, and the security checklist are documented in:

- `docs/DEPLOYMENT.md`
- `docs/ENVIRONMENT.md`
- `docs/SECURITY_CHECKLIST.md`
- `docker-compose.prod.example.yml`

## Developer Commands

```bash
make dev      # start Docker Compose
make test     # backend tests, web typecheck/build, worker import smoke
make reset    # destroy local Docker volumes and restart
make seed     # create the demo manga through the API
make lint     # Python compile check and web typecheck
make format   # placeholder until Prettier/Ruff are added
make final-check   # full final-boss verification gate on sh-capable systems
make final-demo    # generate evidence/final_boss_demo demo manga
make final-export  # verify demo ZIP/PDF exports
```

Equivalent scripts live in `scripts/`.

On this Windows PowerShell setup, use the native wrappers:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\final-boss-check.ps1
powershell -ExecutionPolicy Bypass -File scripts\final-boss-demo.ps1
powershell -ExecutionPolicy Bypass -File scripts\final-boss-export.ps1
```

Final-boss evidence is written to `evidence/final_boss_demo/`, with the audit in `docs/FINAL_BOSS_AUDIT.md` and results in `docs/FINAL_BOSS_RESULTS.md`.

Frontend smoke tests run on an isolated port and mock the API boundary:

```bash
pnpm --filter @manga-ai/web exec playwright install chromium
pnpm --filter @manga-ai/web smoke
```

On Windows, if Playwright browser download fails with a certificate-chain error, retry with `NODE_OPTIONS=--use-system-ca`.

## Health Checks

- `GET /health`
- `GET /health/db`
- `GET /health/redis`
- `GET /health/storage`
- `GET /health/worker`

The dependency-specific checks return clear JSON with `503` when the dependency is unavailable.

## Implemented Rooms

- Project dashboard
- Story Room
- Character Lab
- Style Lab
- Page Studio
- QA panel
- Publishing Room

## Implemented API Highlights

- Project/page/panel CRUD
- Private alpha auth, project ownership scoping, and protected asset/export download proxy
- Story bible, chapter plan, page plan generation with mock LLM provider
- Character cards and style bibles
- Provider-based panel rendering with mock/OpenAI/ComfyUI boundaries
- Page composition and lettering
- Manga QA reports
- ZIP, PDF, EPUB skeleton, and layered project exports
- Full demo project endpoint
- Director Mode one-premise draft orchestration
- Prompt registry and AI task run auditing
- Manga AI evaluation harness
- Production configuration, request limits, structured logs, and CI smoke checks

See `docs/ARCHITECTURE.md`, `docs/PIPELINE.md`, `docs/LOCAL_DEV.md`, `docs/DEMO_PIPELINE.md`, `docs/EVALUATION.md`, `docs/DEPLOYMENT.md`, `docs/ENVIRONMENT.md`, `docs/SECURITY_CHECKLIST.md`, and `docs/TROUBLESHOOTING.md` for details.

## Provider Boundary

No API keys are hard-coded. Local development uses mock providers by default.

- `MODEL_PROVIDER=mock` for story generation
- `provider_name=mock` for panel rendering
- `OPENAI_API_KEY` and `OPENAI_IMAGE_MODEL` are only needed when selecting OpenAI image rendering
- `COMFYUI_BASE_URL` is only needed when selecting ComfyUI

Missing external provider settings do not break tests.
