# Manga AI Studio Private Alpha Baseline

Date: 2026-06-26

This document records the private-alpha baseline created from PR #1.

Status:

- Local demo is ready.
- Controlled private alpha is ready with per-user tester tokens.
- Public beta is not ready.
- Production is not ready.
- Mock art proves pipeline behavior, not final commercial art quality.

## Baseline

- Merge commit SHA: `cb1d8a086f38f167395270f1968b5add4994949c`
- Source branch merged into `main`: `origin/private-alpha-hardening`
- Baseline tag: `v0.1.0-private-alpha`
- PR: `https://github.com/kotonja/Manga-AI-Studio/pull/1`

## Verification Results

| Check | Result |
| --- | --- |
| `python -m pytest -q services/api/tests` | `108 passed, 3 warnings` |
| `pnpm --filter @manga-ai/web typecheck` | Passed |
| `pnpm --filter @manga-ai/web build` | Passed |
| `pnpm --filter @manga-ai/web smoke` | `3 passed` |
| `docker compose config --quiet` | Passed |
| `docker compose build api worker web` | Passed |

Warnings are limited to existing dependency deprecations in backend tests and normal Docker build warnings about package install behavior.

## Local Demo Instructions

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

- Web app: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

Local demo mode is unlocked by default. Use the dashboard or `/demo` to create and inspect the founder demo manga. The deterministic mock providers are expected to work without paid API keys.

## Private Alpha Env Example

For multi-user browser testing, prefer per-tester tokens:

```env
APP_ENV=alpha
ALPHA_AUTH_ENABLED=true
ALPHA_SESSION_SECRET=replace-with-long-random-secret
ALPHA_USER_TOKENS=tester-a:replace-with-token-a,tester-b:replace-with-token-b
ALPHA_ADMIN_TOKEN=replace-with-admin-token
ALPHA_SHARED_PASSWORD=
ENABLE_DEV_ADMIN=false
TRUST_EXTERNAL_AUTH_HEADERS=false
```

For a tiny shared demo, `ALPHA_SHARED_PASSWORD` can be set, but every browser login maps to the shared `alpha-user` account. Shared-password mode does not isolate testers.

External auth header mode must only be enabled behind a trusted proxy that strips spoofed incoming identity headers and injects authenticated identity headers:

```env
AUTH_PROVIDER_MODE=external
AUTH_FORWARDED_USER_HEADER=X-Authenticated-User
TRUST_EXTERNAL_AUTH_HEADERS=true
```

Do not enable `TRUST_EXTERNAL_AUTH_HEADERS=true` on an API that is directly reachable by browsers or untrusted clients.

## Tester Token Guidance

- Use one `user-id:token` pair per tester in `ALPHA_USER_TOKENS`.
- A tester can log into the web app with either the token value or `user-id:token`.
- Browser sessions are signed with `ALPHA_SESSION_SECRET` in the `manga_alpha_session` cookie.
- Projects created through a per-user session are owned by that tester and hidden from other testers.
- Admin pages require either a non-production dev admin flag or a signed admin session created with `ALPHA_ADMIN_TOKEN`.

Generate tester tokens with:

```powershell
python scripts/create-alpha-token.py --user tester-a
```

Validate deployment env with:

```powershell
python scripts/check-alpha-env.py
```

Operator launch docs:

- `docs/ALPHA_LAUNCH_PLAN.md`
- `docs/TESTER_GUIDE.md`
- `docs/ALPHA_OPERATOR_RUNBOOK.md`

## Known Blockers Before Public Beta or Production

- Replace private-alpha auth with a real production auth provider or a hardened trusted auth proxy.
- Replace placeholder rate limiting with distributed or edge rate limiting.
- Harden OpenAI, ComfyUI, and future provider paths beyond deterministic mock mode.
- Add stronger operational monitoring, alerting, backup, and restore drills.
- Continue security review of upload handling, export packages, object storage permissions, and admin routes.
- Mock art proves pipeline, not final commercial art.
