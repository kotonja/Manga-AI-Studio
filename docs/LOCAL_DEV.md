# Local Development

## One Command

```bash
docker compose up --build
```

or:

```bash
sh scripts/dev.sh
```

The API runs Alembic migrations before Uvicorn starts. The web app uses pnpm workspaces in Docker. The worker consumes Celery jobs from Redis.

On Windows PowerShell, run the `docker compose ...` commands directly. The `scripts/*.sh` helpers require a POSIX shell such as Git Bash or WSL.

## URLs

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001
- API health: http://localhost:8000/health

## Scripts

- `sh scripts/check-env.sh`: verifies Docker and Compose.
- `sh scripts/dev.sh`: creates `.env` if needed and starts the stack.
- `sh scripts/test-all.sh`: builds containers, runs backend tests, web typecheck/build, and worker import smoke.
- `sh scripts/reset-db.sh`: destroys Docker volumes and restarts the local stack.
- `sh scripts/seed-demo.sh`: calls the demo endpoint.
- `sh scripts/smoke-frontend.sh`: checks key frontend routes against a running stack.

## Frontend Smoke Tests

The Playwright smoke suite starts Next on port `3100` and mocks the API boundary. It covers the dashboard, one-click Founder Demo, project detail, Story Room, Page Studio, and Publishing Room.

```bash
pnpm --filter @manga-ai/web exec playwright install chromium
pnpm --filter @manga-ai/web smoke
```

On Windows certificate-managed networks, browser install may need:

```powershell
$env:NODE_OPTIONS="--use-system-ca"
pnpm --filter @manga-ai/web exec playwright install chromium
```

## Make Targets

```bash
make dev
make test
make reset
make seed
make lint
make format
```

`make format` is currently a placeholder because Prettier/Ruff have not been added.

## Environment

Copy `.env.example` to `.env` for local overrides. The checked-in defaults are safe local values and should not be used in production.

External providers are optional:

- OpenAI image rendering requires `OPENAI_API_KEY` only when the OpenAI provider is selected.
- ComfyUI rendering requires `COMFYUI_BASE_URL` and a workflow template only when selected.
- Tests and the demo pipeline use mock providers.

## Dev Admin

The internal AI task run page is off by default. To inspect prompt registry runs locally, set these in `.env` and restart Compose:

```bash
ENABLE_DEV_ADMIN=true
NEXT_PUBLIC_ENABLE_DEV_ADMIN=true
```

Then open `/admin/ai-task-runs`.
