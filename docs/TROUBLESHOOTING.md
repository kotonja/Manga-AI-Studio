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
