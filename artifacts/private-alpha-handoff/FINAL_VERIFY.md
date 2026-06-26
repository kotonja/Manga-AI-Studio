# Final Verification

## Commands

| Command | Exit Code | Result |
| --- | --- | --- |
| `python -m pytest -q services/api/tests` | 0 | 102 passed, 3 warnings |
| `pnpm --filter @manga-ai/web typecheck` | 0 | TypeScript check passed |
| `pnpm --filter @manga-ai/web build` | 0 | Next.js production build passed |
| `pnpm --filter @manga-ai/web smoke` | 0 | 3 Playwright smoke tests passed |
| `docker compose config --quiet` | 0 | Compose config valid |
| `docker compose exec -T api sh -lc "alembic current"` | 0 | `0023_project_owner_assets (head)` |
| `docker compose build api worker web` | 0 | API, worker, and web images built earlier in this handoff pass |

## Warnings

- Backend tests reported existing dependency deprecation warnings from FastAPI/Starlette/httpx and one HTTP status constant deprecation warning.
- Docker worker logs warn about running Celery as root in local Docker; this is not a test failure and should be hardened before production deployment.

## Failed Output

None.
