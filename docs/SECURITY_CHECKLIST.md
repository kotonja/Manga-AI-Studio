# Security Checklist

Use this checklist before exposing Manga AI Studio outside local development.

## Secrets

- [ ] No real secrets are committed to Git.
- [ ] Production uses a secret manager, platform secrets, or `/run/secrets`.
- [ ] `OPENAI_API_KEY`, S3 credentials, database password, and Redis credentials are rotated before launch.
- [ ] `.env.prod` is stored outside the repository or protected by deployment tooling.

## API Runtime

- [ ] `APP_ENV=production`.
- [ ] `EXPOSE_ERROR_DETAILS=false`.
- [ ] `LOG_FORMAT=json`.
- [ ] `TRUSTED_HOSTS` is restricted to production domains.
- [ ] `API_CORS_ORIGINS` contains only trusted web origins.
- [ ] `ENABLE_DEV_ADMIN=false`.
- [ ] `NEXT_PUBLIC_ENABLE_DEV_ADMIN=false`.
- [ ] `ALPHA_AUTH_ENABLED=true` for private alpha or production-like deployments.
- [ ] `ALPHA_USER_TOKENS`, `ALPHA_SHARED_PASSWORD`, and `ALPHA_ADMIN_TOKEN` are stored as secrets and rotated before inviting testers.
- [ ] Production uses `AUTH_PROVIDER_MODE=external` behind a trusted auth proxy or a real auth provider hook.
- [ ] `MAX_REQUEST_BYTES` is set and mirrored at the reverse proxy.
- [ ] `UPLOAD_ALLOWED_CONTENT_TYPES` is an allowlist.
- [ ] `UPLOAD_MAX_BYTES` is appropriate for the storage budget.
- [ ] Edge or Redis-backed rate limiting exists for public traffic.

## Data And Storage

- [ ] PostgreSQL backups are automated and restore-tested.
- [ ] Object storage backups/versioning are enabled.
- [ ] Export packages include provenance metadata.
- [ ] Uploaded assets require rights declarations.
- [ ] Bucket policies do not expose private raw assets accidentally.
- [ ] `ASSET_DOWNLOAD_MODE=proxy` unless public CDN reads are explicitly intended.
- [ ] `S3_PUBLIC_READ_ENABLED=false` for private alpha assets.
- [ ] Asset and export downloads are validated through owner-scoped API routes.

## Providers

- [ ] Mock providers are disabled for real paid production workflows unless explicitly intended.
- [ ] Provider keys are stored only in secret storage.
- [ ] Provider logs never include API keys.
- [ ] Provider errors shown to users are sanitized.
- [ ] Cost monitoring exists for OpenAI/ComfyUI provider workloads.

## Network

- [ ] TLS terminates at the reverse proxy/load balancer.
- [ ] API and worker are not directly exposed to the public internet except through intended routes.
- [ ] Redis and PostgreSQL are private-network only.
- [ ] MinIO console is protected or disabled.
- [ ] `X-Request-ID` is preserved through the proxy.

## Deployment

- [ ] Alembic migrations pass from an empty database in CI.
- [ ] `alembic upgrade head` runs before API/worker rollout.
- [ ] Worker image and API image are deployed from the same commit.
- [ ] Rollback plan covers both database and object storage changes.
- [ ] Health checks are wired into the orchestrator.
