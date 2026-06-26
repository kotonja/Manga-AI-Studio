# Production Deployment

This guide keeps local development simple while documenting a production path for the web app, API, worker, PostgreSQL, Redis, and S3-compatible object storage.

## Build Targets

- `apps/web/Dockerfile`
  - `dev`: local Next.js dev server.
  - `runner`: production standalone Next.js server.
- `services/api/Dockerfile`
  - `dev`: editable install with reload.
  - `production`: non-root API runtime.
- `services/worker/Dockerfile`
  - `dev`: editable worker install.
  - `production`: non-root Celery runtime.

Local `docker-compose.yml` explicitly targets the `dev` stages. Production examples use production targets.

## Quick Production Shape

1. Copy `.env.prod.example` to `.env.prod`.
2. Replace every placeholder secret.
3. Point `API_CORS_ORIGINS`, `TRUSTED_HOSTS`, `NEXT_PUBLIC_API_BASE_URL`, and `PUBLIC_BASE_URL` at real domains.
4. Review `docker-compose.prod.example.yml`.
5. Run migrations.
6. Start API, worker, and web behind a TLS reverse proxy.

```bash
docker compose -f docker-compose.prod.example.yml --env-file .env.prod build
docker compose -f docker-compose.prod.example.yml --env-file .env.prod run --rm migrate
docker compose -f docker-compose.prod.example.yml --env-file .env.prod up -d
```

## Database Migrations

Run Alembic before deploying new API/worker versions:

```bash
cd services/api
alembic upgrade head
```

In Compose production, the `migrate` service runs:

```bash
alembic upgrade head
```

CI verifies migrations from an empty PostgreSQL database.

## Worker Deployment

The worker must use the same `DATABASE_URL`, `REDIS_URL`, and object storage settings as the API.

Recommended production command:

```bash
celery -A manga_worker.celery_app.celery_app worker --loglevel=info
```

Run at least one worker whenever `ENABLE_BACKGROUND_JOBS=true`. Scale workers separately from API instances when rendering, composition, or director jobs increase.

## Object Storage

Local development uses MinIO. Production can use any S3-compatible service such as AWS S3, Cloudflare R2, Backblaze B2 S3, or managed MinIO.

Required properties:

- Private write credentials for API and worker.
- Public or signed-read URL strategy for browser previews/downloads.
- Lifecycle policy for abandoned temporary assets.
- Backups or versioning for final exports and project packages.

Set:

- `S3_ENDPOINT_URL`
- `S3_PUBLIC_URL`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `S3_REGION`

## Reverse Proxy Notes

Put Caddy, Nginx, Traefik, or a platform load balancer in front of the app.

Recommended routing:

- `https://manga.example.com` -> web container port `3000`
- `https://api.manga.example.com` -> API container port `8000`
- MinIO/S3 should usually stay private except for object/CDN URLs.

Proxy requirements:

- Terminate TLS.
- Forward `X-Forwarded-For`, `X-Forwarded-Proto`, and `Host`.
- Preserve `X-Request-ID` or allow the API to create one.
- Set body-size limits equal to or lower than `MAX_REQUEST_BYTES`.
- Add edge rate limiting before enabling high-traffic public access.

## Logging And Observability

Production should use:

```env
LOG_FORMAT=json
LOG_LEVEL=INFO
APP_ENV=production
EXPOSE_ERROR_DETAILS=false
```

The API logs request id, status, duration, provider calls, export jobs, and job identifiers without logging API keys or full provider secrets. Every response includes `X-Request-ID`.

Health endpoints:

- `GET /health`
- `GET /health/db`
- `GET /health/redis`
- `GET /health/storage`
- `GET /health/worker`

## Backup And Restore

Database backup:

```bash
pg_dump "$DATABASE_URL" > manga-ai-$(date +%Y%m%d).sql
```

Database restore:

```bash
psql "$DATABASE_URL" < manga-ai-YYYYMMDD.sql
```

Object storage backup depends on provider. For MinIO:

```bash
mc mirror local/manga-ai-prod ./backups/manga-ai-prod
```

Back up PostgreSQL and object storage together so asset records and stored files remain consistent.

## Seed Script

Local/demo seed:

```bash
sh scripts/seed-demo.sh
```

In production, seed only non-user demo environments. Do not seed demo data into a real customer workspace unless that is an explicit launch requirement.
