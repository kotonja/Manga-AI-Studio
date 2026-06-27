# Alpha Deployment Plan Baseline

Date: 2026-06-27

This document records the private-alpha deployment planning baseline after PR #4 was refreshed on the raw-byte LF normalization baseline and merged into `main`.

## Git References

- PR: #4, `alpha-deployment-plan`
- PR source branch SHA: `7ca66a8193de3790480fed65a40d2edb6cac4a34`
- PR merge commit on `main`: `d014ba153df29e2f18f590583af35d8f53d870c7`
- Baseline tag: `v0.1.5-alpha-deployment-plan`

## Deployment Artifacts

- `.env.alpha.example`
- `docs/ALPHA_DEPLOYMENT_DECISION.md`
- `docs/ALPHA_TESTER_INVITE_TEMPLATE.md`
- `docs/ALPHA_FEEDBACK_TRIAGE.md`
- `docs/ALPHA_LAUNCH_CHECKLIST.md`
- `docs/ALPHA_DEPLOYMENT_SMOKE_COMMANDS.md`

## Recommended First Alpha Deployment

Use a single private deployment in mock mode for the first controlled alpha.

- Tester size: 2 to 5 testers.
- Access model: per-user alpha tokens.
- Asset/export access: protected proxy only.
- Provider mode: deterministic mock providers only.
- Real provider calls: no real OpenAI or ComfyUI calls for the first alpha.

## Status

- Local demo: ready.
- Founder demo: ready.
- Controlled private alpha: ready with per-user tokens.
- Public beta: not ready.
- Production: not ready.
- Mock art proves workflow/pipeline, not commercial art quality.

## Public Raw Byte Counts

The following counts were verified through public raw GitHub URLs on `main` after PR #4 was merged.

| File | Public raw LF_0A | Public raw CR_0D | Bytes |
| --- | ---: | ---: | ---: |
| `.env.alpha.example` | 78 | 0 | 2655 |
| `docs/ALPHA_DEPLOYMENT_DECISION.md` | 151 | 0 | 4865 |
| `docs/ALPHA_LAUNCH_CHECKLIST.md` | 115 | 0 | 3650 |
| `docs/ALPHA_DEPLOYMENT_SMOKE_COMMANDS.md` | 168 | 0 | 3706 |
| `scripts/create-alpha-token.py` | 55 | 0 | 1782 |
| `scripts/check-alpha-env.py` | 227 | 0 | 8374 |
| `scripts/alpha-smoke-test.py` | 119 | 0 | 4807 |

All listed files ended with a final `0A` byte.

## Verification Results

- `python scripts/normalize-text-files.py --check`: passed.
- `python scripts/scan-hidden-unicode.py`: passed.
- `python -m py_compile` for alpha utility scripts: passed.
- `python scripts/check-alpha-env.py --env-file .env.alpha.example`: intentionally failed with placeholder-secret blockers, exited cleanly, and did not print real secrets.
- `python -m pytest -q services/api/tests/test_alpha_readiness.py services/api/tests/test_alpha_launch_ops.py`: `18 passed, 1 warning`.
- `python -m pytest -q services/api/tests`: `122 passed, 3 warnings`.
- `pnpm --filter @manga-ai/web typecheck`: passed.
- `pnpm --filter @manga-ai/web build`: passed.
- `pnpm --filter @manga-ai/web smoke`: `3 passed`.
- `docker compose config --quiet`: passed.
- GitHub CI on PR #4: backend, frontend, and docker-build passed.

## Remaining Launch Risks

- Replace template placeholders with generated per-user alpha tokens and real private alpha secrets before deployment.
- Keep `TRUST_EXTERNAL_AUTH_HEADERS=false` unless a trusted reverse proxy and auth provider are configured.
- Rehearse backup and restore before expanding beyond the first small tester group.
- Continue upload, export, storage, and admin security review before public beta.
- Real provider mode still requires provider hardening, cost controls, and additional safety review.
- Production still needs real auth provider integration, rate limiting, monitoring, and operational runbooks.
