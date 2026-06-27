# Manga AI Studio Alpha Launch Baseline

Date: 2026-06-26

## Baseline

- Merge commit SHA: `a6270712e406d83d67b867d52c90feb09c0b530f`
- Tag name: `v0.1.1-alpha-launch`
- Source PR: `#2` - `alpha-launch-prep`

## Status

Local demo: ready
Founder demo: ready
Controlled private alpha: ready with per-user tokens
Public beta: not ready
Production: not ready
Mock art proves pipeline behavior, not final commercial art quality

## Verification Results

- Hidden Unicode scan: passed, `No dangerous hidden Unicode format characters found.`
- Backend tests: passed, `112 passed, 3 warnings`
- Frontend typecheck: passed
- Frontend build: passed
- Browser smoke: passed, `3 passed`
- Docker Compose config: passed
- Docker build smoke: passed for `api`, `worker`, and `web`

## Alpha Launch Paths

- Launch plan: `docs/ALPHA_LAUNCH_PLAN.md`
- Tester guide: `docs/TESTER_GUIDE.md`
- Operator runbook: `docs/ALPHA_OPERATOR_RUNBOOK.md`
- Alpha testing guide: `docs/ALPHA_TESTING.md`
- Environment reference: `docs/ENVIRONMENT.md`
- Security checklist: `docs/SECURITY_CHECKLIST.md`
- Token utility: `scripts/create-alpha-token.py`
- Environment checker: `scripts/check-alpha-env.py`
- Alpha smoke script: `scripts/alpha-smoke-test.py`
- Hidden Unicode scanner: `scripts/scan-hidden-unicode.py`
- Readiness endpoint: `GET /alpha/readiness`
- Admin readiness UI: `/admin/alpha-readiness`

## Tester Tokens

Use per-user tokens for controlled alpha testers. Generate tokens with:

```bash
python scripts/create-alpha-token.py tester-a tester-b
```

Copy the generated `user-id:token` pairs into `ALPHA_USER_TOKENS`. Keep
`ALPHA_SHARED_PASSWORD` empty for multi-user alpha so tester projects stay
isolated by owner.

To revoke a tester, remove that tester's pair from `ALPHA_USER_TOKENS` and
restart the API/web services. Rotate `ALPHA_SESSION_SECRET` when active browser
sessions must be invalidated immediately.

## Required Alpha Environment

Set these for controlled private alpha:

```bash
ALPHA_AUTH_ENABLED=true
ALPHA_SESSION_SECRET=replace-with-strong-random-value
ALPHA_USER_TOKENS=tester-a:token-a,tester-b:token-b
ALPHA_ADMIN_TOKEN=replace-with-strong-admin-token
ALPHA_SHARED_PASSWORD=
AUTH_PROVIDER_MODE=local
TRUST_EXTERNAL_AUTH_HEADERS=false
S3_PUBLIC_READ_ENABLED=false
ENABLE_DEV_ADMIN=false
NEXT_PUBLIC_ENABLE_DEV_ADMIN=false
```

Core service configuration is still required:

```bash
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
S3_ENDPOINT_URL=...
S3_PUBLIC_URL=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
S3_REGION=us-east-1
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

Run `python scripts/check-alpha-env.py` before inviting testers.

`AUTH_PROVIDER_MODE=external` is implemented only for trusted forwarded identity
headers when `TRUST_EXTERNAL_AUTH_HEADERS=true` and the API is behind a trusted
proxy. `AUTH_JWKS_URL` is reserved for future bearer-token validation and does
not currently authenticate users.

## Remaining Public Beta And Production Blockers

- Real auth provider or trusted reverse-proxy auth hardening, including JWKS/JWT
  bearer-token validation if that mode is used.
- Real rate limiting and abuse controls.
- Provider hardening for paid image/LLM calls, quotas, and cost controls.
- Backup and restore rehearsal for database and object storage.
- Continued upload, export, storage, admin, and provenance security review.
- Production observability, alerting, and incident response coverage.
- Legal/IP review for publishing workflows and user-provided assets.
