# Private Alpha Operator Runbook

This runbook is for operating Manga AI Studio `v0.1.0-private-alpha` for a small
controlled tester group.

## Environment Variables

Minimum controlled-alpha auth settings:

```env
APP_ENV=alpha
ALPHA_AUTH_ENABLED=true
ALPHA_SESSION_SECRET=replace-with-strong-random-value
ALPHA_USER_TOKENS=tester-a:token-a,tester-b:token-b
ALPHA_ADMIN_TOKEN=replace-with-strong-admin-token
ALPHA_SHARED_PASSWORD=
ENABLE_DEV_ADMIN=false
NEXT_PUBLIC_ENABLE_DEV_ADMIN=false
TRUST_EXTERNAL_AUTH_HEADERS=false
S3_PUBLIC_READ_ENABLED=false
ASSET_DOWNLOAD_MODE=proxy
```

Required services:

```env
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
S3_ENDPOINT_URL=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
```

Run:

```powershell
python scripts/check-alpha-env.py
```

Controlled alpha should use `ALPHA_USER_TOKENS` by default. The web alpha login
turns a valid tester token into a signed browser session tied to that tester's
user id.

External trusted-header mode is implemented only when all of these are true:

- `AUTH_PROVIDER_MODE=external`
- `TRUST_EXTERNAL_AUTH_HEADERS=true`
- `AUTH_FORWARDED_USER_HEADER` names the trusted identity header

Only use that mode behind a trusted proxy that strips client-supplied identity
and admin headers before forwarding requests to the API.

`AUTH_JWKS_URL` is reserved for future bearer-token validation. Setting a JWKS URL
does not currently validate users and should not be treated as production-ready
external auth.

## Deployment Startup

Local Docker startup:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

For hosted alpha, deploy API, worker, web, PostgreSQL, Redis, and object storage
together. API and web must share `ALPHA_SESSION_SECRET` so signed browser
sessions validate consistently.

## Health Checks

Public checks:

- `GET /health`
- `GET /health/db`
- `GET /health/redis`
- `GET /health/storage`
- `GET /health/worker`

Admin alpha check:

- `GET /alpha/readiness` with `X-Alpha-Token: <ALPHA_ADMIN_TOKEN>`

Frontend:

- `/admin/alpha-readiness`
- `/admin/alpha`

## Database Migrations

Apply Alembic migrations before inviting testers:

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

The private-alpha baseline includes `0024_alpha_feedback_triage` after launch-prep.

## Creating Tester Tokens

```powershell
python scripts/create-alpha-token.py --user tester-a
python scripts/create-alpha-token.py --user tester-b --write
```

Copy pairs into:

```env
ALPHA_USER_TOKENS=tester-a:...,tester-b:...
```

Restart API and web after changing tokens.

## Disabling Tester Access

1. Remove that tester's pair from `ALPHA_USER_TOKENS`.
2. Restart API and web.
3. Rotate `ALPHA_SESSION_SECRET` if active sessions must be invalidated immediately.
4. Keep project data unless there is a clear deletion request and backup.

## Reading Logs

Local Docker:

```powershell
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web
```

Look for request ids, job ids, provider names, and safe error messages. Logs should not expose secrets.

## Checking Failed Jobs

- Open `/admin/alpha`.
- Review failed jobs and provider errors.
- Retry failed mock render jobs from the UI when available.
- For real providers, dry-run before retrying paid generation.

## Checking Storage

Use:

```powershell
docker compose exec api python - <<'PY'
from manga_api.storage import get_object_storage
storage = get_object_storage()
storage.check()
print("storage ok")
PY
```

Also verify export downloads through the app, not by public bucket URLs.

## Backup Notes

Before inviting testers:

- Back up PostgreSQL.
- Back up object storage bucket contents.
- Save deployment env separately in a secure password manager.

Do not store `.env`, generated tester tokens, or provider keys in Git.

## Restoring From Backup

1. Stop API, worker, and web.
2. Restore PostgreSQL backup.
3. Restore object storage bucket.
4. Start database, storage, Redis, API, worker, and web.
5. Run `/alpha/readiness`.
6. Run `scripts/alpha-smoke-test.py` against the restored deployment.

## Restarting Workers

Local Docker:

```powershell
docker compose restart worker
docker compose logs -f worker
```

If worker readiness still fails, check Redis URL, queue connectivity, and worker environment.

## Common Failure Modes

- Login loops: missing or mismatched `ALPHA_SESSION_SECRET` between web and API.
- Everyone sees the same projects: shared-password mode is enabled instead of per-user tokens.
- Export downloads fail: `ASSET_DOWNLOAD_MODE` or storage credentials are wrong.
- Readiness worker failure: worker is down or cannot reach Redis.
- Real provider errors: missing provider keys, unsupported size, or provider outage.
- Storage readiness failure: bucket missing, bad endpoint, or bad credentials.

## Emergency Shutdown

1. Remove public ingress or stop web/API containers.
2. Remove `ALPHA_USER_TOKENS` and restart if services must stay up.
3. Rotate `ALPHA_SESSION_SECRET`.
4. Preserve logs and data for investigation.
5. Notify testers that access is paused.
