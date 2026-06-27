# Environment Configuration

Manga AI Studio uses environment variables for API, worker, web, database, queue, object storage, and provider configuration. Do not commit real secrets.

## Modes

- Development: copy `.env.example` to `.env` and run `docker compose up --build`.
- Test: use `.env.test.example` as a reference. Tests default to SQLite and mock providers.
- Alpha: use per-user `ALPHA_USER_TOKENS`, signed browser sessions, protected downloads, and `scripts/check-alpha-env.py` before inviting testers.
- Production: copy `.env.prod.example` to `.env.prod`, replace all placeholder secrets, and use `docker-compose.prod.example.yml` as a starting point.

Current status: local demo is ready, controlled private alpha is ready with per-user tester tokens, public beta is not ready, and production is not ready.

## Core

| Variable | Required | Example | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | yes | `development`, `test`, `production` | Controls debug/error behavior. |
| `SECRETS_DIR` | prod | `/run/secrets` | Optional directory for file-based secrets. |
| `PUBLIC_BASE_URL` | prod | `https://manga.example.com` | Public app URL. |
| `LOG_LEVEL` | yes | `INFO` | Python logging level. |
| `LOG_FORMAT` | yes | `plain`, `json` | Use `json` in production. |
| `TRUSTED_HOSTS` | prod | `manga.example.com,api.manga.example.com` | `*` is acceptable only for local dev. |
| `API_CORS_ORIGINS` | yes | `https://manga.example.com` | Comma-separated allowed browser origins. |

## Backend Limits

| Variable | Default | Notes |
| --- | ---: | --- |
| `MAX_REQUEST_BYTES` | `26214400` | Rejects oversized request bodies before route handling. |
| `UPLOAD_MAX_BYTES` | `10485760` | Metadata/file size ceiling for uploaded assets. |
| `UPLOAD_ALLOWED_CONTENT_TYPES` | `image/png,image/jpeg,image/webp` | Comma-separated allowlist. |
| `RATE_LIMIT_ENABLED` | `false` | Enables the local placeholder limiter. Prefer edge/Redis rate limiting in production. |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-process placeholder limit. |
| `EXPOSE_ERROR_DETAILS` | auto | Defaults to `false` in production and `true` elsewhere. |

## Database And Queue

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | SQLAlchemy URL, usually `postgresql+psycopg://...`. |
| `POSTGRES_USER` | compose | Used by local/prod compose Postgres. |
| `POSTGRES_PASSWORD` | compose | Use a secret manager or Docker secret in production. |
| `POSTGRES_DB` | compose | Database name. |
| `REDIS_URL` | yes | Redis broker/cache URL for Celery jobs. |
| `ENABLE_BACKGROUND_JOBS` | yes | `true` in production, `false` in many tests. |

## Object Storage

| Variable | Required | Notes |
| --- | --- | --- |
| `S3_ENDPOINT_URL` | yes | Internal S3-compatible endpoint. |
| `S3_PUBLIC_URL` | yes | Public or CDN URL used in asset metadata. |
| `S3_ACCESS_KEY_ID` | yes | Store securely. |
| `S3_SECRET_ACCESS_KEY` | yes | Store securely. |
| `S3_BUCKET_NAME` | yes | Bucket for renders, composites, exports. |
| `S3_REGION` | yes | Region string, `us-east-1` for MinIO. |
| `S3_PUBLIC_READ_ENABLED` | alpha/prod | Defaults to `false`; only set `true` if bucket/CDN public reads are intentionally allowed. |
| `ASSET_DOWNLOAD_MODE` | alpha/prod | Use `proxy` for protected API downloads. `public_url` is only honored when public reads are explicitly enabled. |

## Provider Configuration

| Variable | Required | Notes |
| --- | --- | --- |
| `MODEL_PROVIDER` | yes | Defaults to `mock`. |
| `OPENAI_API_KEY` | optional | Required only for OpenAI provider calls. |
| `OPENAI_MODEL` | optional | LLM model stub/config. |
| `OPENAI_IMAGE_MODEL` | optional | Image model for OpenAI rendering. |
| `COMFYUI_BASE_URL` | optional | Required only for ComfyUI provider calls. |

## Web

| Variable | Required | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | yes | Browser-visible API base URL. |
| `API_INTERNAL_URL` | prod | Server-side API URL from the web container. |
| `NEXT_PUBLIC_ENABLE_DEV_ADMIN` | no | Keep `false` in production. |
| `ENABLE_DEV_ADMIN` | no | Backend admin/eval routes are hidden unless enabled. |

## Private Alpha Auth

| Variable | Required | Notes |
| --- | --- | --- |
| `ALPHA_AUTH_ENABLED` | alpha/prod | Enables the simple local alpha gate for the web app and sensitive API endpoints. |
| `ALPHA_SHARED_PASSWORD` | alpha | Shared tester password for a single shared `alpha-user` account only; it does not isolate testers from each other. |
| `ALPHA_USER_TOKENS` | alpha | Optional comma-separated `user_id:token` pairs for per-user API and browser-login ownership isolation. |
| `ALPHA_ADMIN_TOKEN` | optional | Token for protected admin API calls when `ENABLE_DEV_ADMIN=false`. |
| `ALPHA_SESSION_SECRET` | alpha | Required for browser login when alpha auth is enabled. Used to sign `manga_alpha_session` cookies; never falls back to `ALPHA_SHARED_PASSWORD`. |
| `AUTH_PROVIDER_MODE` | prod | Use `local` for dev alpha, `external` behind a real auth provider or reverse proxy. |
| `AUTH_PROVIDER_NAME` | prod | Human-readable provider label. |
| `AUTH_FORWARDED_USER_HEADER` | prod | Trusted identity header set by the upstream auth proxy, for example `X-Authenticated-User`. |
| `TRUST_EXTERNAL_AUTH_HEADERS` | prod | Defaults to `false`. Use only behind a trusted proxy that strips spoofed auth headers. |
| `AUTH_JWKS_URL` | future | Reserved for direct JWT/JWKS validation. Setting it does not currently authenticate users. |
| `AUTH_ISSUER` | future | JWT issuer metadata for provider integrations. |
| `AUTH_AUDIENCE` | future | JWT audience metadata for provider integrations. |
| `DEFAULT_PROJECT_ALLOW_TRAINING` | no | Defaults new projects to training opt-in. Keep `false` for alpha unless explicitly approved. |
| `DEFAULT_PROJECT_ALLOW_PRODUCT_IMPROVEMENT` | no | Defaults new projects to product-improvement opt-in. Keep `false`; testers can opt in per project. |

## Secret Loading

The backend supports Pydantic settings and file-based secret loading through `SECRETS_DIR`.
In container platforms, mount secret files named after the field, for example
`database_url` or `s3_secret_access_key`, set `SECRETS_DIR=/run/secrets`, or inject
environment variables through the platform secret manager.

## Alpha Ownership

When `ALPHA_AUTH_ENABLED=true`, the backend resolves the current user from
`X-Alpha-Token`, `Authorization: Bearer ...`, a signed `manga_alpha_session`
cookie set by the web alpha login, the admin token, or a trusted forwarded
identity header in external-auth mode.

Projects are stamped with `owner_user_id`, project lists are filtered by owner,
and page/panel/job/export/asset routes verify ownership before returning data.

The browser cookie format is
`v1.<base64url_json_payload>.<base64url_hmac_sha256_signature>`, signed with
`ALPHA_SESSION_SECRET`. The payload contains `user_id`, `is_admin`, `iat`, and
`exp`. Expired, malformed, unsigned, or invalid-signature cookies are rejected.
Browser login requires `ALPHA_SESSION_SECRET` when alpha auth is enabled.

For multi-user private alpha, prefer `ALPHA_USER_TOKENS`. A user who enters the
token for `tester-a:long-token-a` receives a signed session with
`user_id=tester-a`. `ALPHA_SHARED_PASSWORD` remains available for small demos,
but all users share the same `alpha-user` identity and therefore do not get
per-tester project isolation.

Local development keeps `ALPHA_AUTH_ENABLED=false`, which maps requests to the `local-dev` user so the one-command demo remains frictionless.

When `AUTH_PROVIDER_MODE=external`, forwarded identity headers are ignored unless
`TRUST_EXTERNAL_AUTH_HEADERS=true`. This mode is safe only behind a trusted proxy
that removes any client-supplied spoofed identity/admin headers before injecting
authenticated headers.

`AUTH_JWKS_URL` is reserved for future JWT/JWKS bearer-token validation. The API
does not currently validate JWKS bearer tokens, so setting only `AUTH_JWKS_URL`
does not make external auth ready.

## Alpha Operations Helpers

Generate one tester token pair:

```bash
python scripts/create-alpha-token.py --user tester-a
```

Append a generated pair to the local gitignored `.alpha-tokens.generated` file:

```bash
python scripts/create-alpha-token.py --user tester-b --write
```

Validate alpha env:

```bash
python scripts/check-alpha-env.py
make check-alpha-env
```

Run an API smoke test against a deployed alpha:

```bash
python scripts/alpha-smoke-test.py --base-url https://api.example.com --admin-token "$ALPHA_ADMIN_TOKEN" --tester-a-token "$TESTER_A_TOKEN" --tester-b-token "$TESTER_B_TOKEN"
```
