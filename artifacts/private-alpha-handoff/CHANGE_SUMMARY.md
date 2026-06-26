# Private Alpha Hardening Change Summary

Branch: `private-alpha-hardening`

## Scope

This patch prepares Manga AI Studio for private-alpha review by hardening backend authorization, adding project ownership isolation, protecting private asset/export downloads, improving deterministic demo evidence, and adding browser smoke coverage.

## Backend

- `services/api/manga_api/access.py`
- `services/api/manga_api/auth.py`
- `services/api/manga_api/config.py`
- `services/api/manga_api/models.py`
- `services/api/manga_api/schemas.py`
- `services/api/manga_api/storage.py`
- `services/api/manga_api/demo_pipeline.py`
- `services/api/manga_api/founder_demo.py`
- `services/api/manga_api/rendering.py`
- `services/api/manga_api/evaluation.py`
- `services/api/app/final_boss/run.py`
- `services/api/manga_api/routes/alpha.py`
- `services/api/manga_api/routes/commands.py`
- `services/api/manga_api/routes/composition.py`
- `services/api/manga_api/routes/consistency.py`
- `services/api/manga_api/routes/demo.py`
- `services/api/manga_api/routes/director.py`
- `services/api/manga_api/routes/eval.py`
- `services/api/manga_api/routes/exports.py`
- `services/api/manga_api/routes/jobs.py`
- `services/api/manga_api/routes/labs.py`
- `services/api/manga_api/routes/layout.py`
- `services/api/manga_api/routes/learning.py`
- `services/api/manga_api/routes/lettering.py`
- `services/api/manga_api/routes/pacing.py`
- `services/api/manga_api/routes/panel_render.py`
- `services/api/manga_api/routes/projects.py`
- `services/api/manga_api/routes/provenance.py`
- `services/api/manga_api/routes/qa.py`
- `services/api/manga_api/routes/story.py`
- `services/api/manga_api/routes/versions.py`

## Migration Added

- `services/api/manga_api/migrations/versions/0023_project_owner_assets.py`

Adds `Project.owner_user_id` and backfills existing projects to `local-dev`.

## Frontend

- `apps/web/src/lib/api.ts`
- `apps/web/src/components/demo/founder-demo-view.tsx`
- `apps/web/src/components/page-studio/page-studio-view.tsx`
- `apps/web/next.config.mjs`
- `apps/web/Dockerfile`
- `apps/web/package.json`
- `apps/web/playwright.config.ts`
- `apps/web/tests/alpha-smoke.spec.ts`

## Tests Added Or Updated

- `services/api/tests/test_auth_isolation.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_evaluation_harness.py`
- `apps/web/tests/alpha-smoke.spec.ts`

## Infra And Config

- `.env.example`
- `.env.prod.example`
- `.github/workflows/ci.yml`
- `.gitignore`
- `docker-compose.yml`
- `package.json`
- `pnpm-lock.yaml`

## Documentation

- `README.md`
- `docs/ALPHA_TESTING.md`
- `docs/API_INVENTORY.md`
- `docs/ENVIRONMENT.md`
- `docs/FINAL_BOSS_AUDIT.md`
- `docs/FINAL_BOSS_RESULTS.md`
- `docs/FOUNDER_DEMO.md`
- `docs/FRONTEND_INVENTORY.md`
- `docs/LOCAL_DEV.md`
- `docs/SECURITY_CHECKLIST.md`
- `docs/STUBS_AND_TODOS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/DEMO_VISUAL_QUALITY.md`

## Evidence Regenerated

- `evidence/final_boss_demo/project.json`
- `evidence/final_boss_demo/story_bible.json`
- `evidence/final_boss_demo/characters.json`
- `evidence/final_boss_demo/style_bible.json`
- `evidence/final_boss_demo/pages.json`
- `evidence/final_boss_demo/panels.json`
- `evidence/final_boss_demo/provenance.json`
- `evidence/final_boss_demo/qa_reports.json`
- `evidence/final_boss_demo/export_manifest.json`
- `evidence/final_boss_demo/final_pages/page-001.png`
- `evidence/final_boss_demo/final_pages/page-002.png`
- `evidence/final_boss_demo/final_pages/page-003.png`
- `evidence/final_boss_demo/final_pages/page-004.png`
- `evidence/final_boss_demo/exports/zip-be896d20-ecd0-4186-9670-5ce980e52154.zip`
- `evidence/final_boss_demo/exports/pdf-f6c27c0c-eb06-490d-bf47-2b33594fc952.pdf`

Removed superseded export evidence:

- `evidence/final_boss_demo/exports/zip-08a5dba6-4f5a-4bdb-a396-47a6fd7a3bc7.zip`
- `evidence/final_boss_demo/exports/pdf-79212b83-ab44-4735-9c6d-07d83b3735a5.pdf`

## Verification Results

- Backend tests: `python -m pytest -q services/api/tests` -> 102 passed, 3 warnings.
- Frontend typecheck: `pnpm --filter @manga-ai/web typecheck` -> passed.
- Frontend build: `pnpm --filter @manga-ai/web build` -> passed.
- Browser smoke: `pnpm --filter @manga-ai/web smoke` -> 3 passed.
- Docker Compose config: `docker compose config --quiet` -> passed.
- Migration head: `docker compose exec -T api sh -lc "alembic current"` -> `0023_project_owner_assets (head)`.
- Docker image build: `docker compose build api worker web` -> passed earlier in this handoff pass.

## Known Remaining Blockers

- Private-alpha auth is intentionally simple; public production still needs a real auth provider or trusted auth proxy.
- Rate limiting remains a placeholder and should be replaced with a distributed limiter before public launch.
- OpenAI image editing, ComfyUI output retrieval, and multimodal QA remain provider stubs.
- Mock art proves the pipeline and founder demo flow, not final commercial art quality.
