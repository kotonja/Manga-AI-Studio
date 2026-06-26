# Troubleshooting

## Docker Is Not Found

Install Docker Desktop, then reopen the terminal and verify:

```powershell
docker --version
docker compose version
```

## Docker Desktop Cannot Start

Open Docker Desktop manually. On Windows, make sure WSL 2 is installed and Docker Desktop is allowed to use it.

## Web Build Fails On `workspace:*`

The web image must use pnpm, not npm. The current `apps/web/Dockerfile` enables Corepack and runs `pnpm install --frozen-lockfile`.

If old node modules were copied into Docker, rebuild after clearing volumes:

```bash
docker compose rm -sf web
docker volume rm manga-ai_web-node-modules manga-ai_web-app-node-modules manga-ai_web-shared-node-modules manga-ai_web-next-cache
docker compose build web
docker compose up -d web
```

## Local Web Build Fails On Symlink Permission

Windows can block Next.js standalone output symlinks when Developer Mode is off. Local `pnpm --filter @manga-ai/web build` disables standalone output by default. Docker production builds still set `NEXT_OUTPUT_STANDALONE=true`.

If you intentionally need a local standalone build, enable Windows Developer Mode or run:

```powershell
$env:NEXT_OUTPUT_STANDALONE="true"
pnpm --filter @manga-ai/web build
```

## Playwright Browser Download Fails Certificate Verification

If `playwright install chromium` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, use Node's Windows certificate store:

```powershell
$env:NODE_OPTIONS="--use-system-ca"
pnpm --filter @manga-ai/web exec playwright install chromium
```

## API Health

Check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/redis
curl http://localhost:8000/health/storage
curl http://localhost:8000/health/worker
```

`/health/worker` returns `503` if no Celery worker responds.

## Demo Export Fails

The demo requires shared object storage across render, compose, and export. In Docker this is MinIO. Confirm MinIO is running and the bucket exists:

```bash
docker compose ps minio minio-init
curl http://localhost:8000/health/storage
```

Then rerun:

```bash
sh scripts/seed-demo.sh
```

## Reset Local Data

This removes local Postgres and MinIO volumes:

```bash
sh scripts/reset-db.sh
```

## External Providers

OpenAI and ComfyUI are optional. Missing provider env vars do not break tests or the demo. They only matter if you explicitly choose those providers in Page Studio.
