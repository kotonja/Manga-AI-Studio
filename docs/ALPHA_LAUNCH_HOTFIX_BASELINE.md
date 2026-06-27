# Alpha Launch Hotfix Baseline

This document records the post-merge verification for the alpha launch hotfix.

## Baseline

- PR: [#3](https://github.com/kotonja/Manga-AI-Studio/pull/3)
- Merge commit SHA: `d51ffd52a2de75a4919cc590dafc78c612c4419c`
- Source commit SHA: `d51885e5a849097172b4398ea8ce37b7025a6de5`
- Tag name: `v0.1.2-alpha-launch-hotfix`
- Tag message: `Manga AI Studio alpha launch hotfix baseline`

## Verification Results

Verified on `main` after PR #3 was merged.

| Check | Result |
| --- | --- |
| Direct file line-ending check | Passed |
| `python scripts/normalize-text-files.py --check` | Passed |
| `python scripts/scan-hidden-unicode.py` | Passed |
| `python -m pytest -q services/api/tests` | Passed, `122 passed, 3 warnings` |
| `pnpm --filter @manga-ai/web typecheck` | Passed |
| `pnpm --filter @manga-ai/web build` | Passed |
| `pnpm --filter @manga-ai/web smoke` | Passed, `3 passed` |
| `docker compose config --quiet` | Passed |
| `docker compose build api worker web` | Passed |
| GitHub raw `main` file verification | Passed |

The GitHub raw `main` verification was performed with a curl-backed fetch on this Windows machine because the bundled local Python runtime hit an OpenSSL Applink issue during HTTPS requests. The raw file bytes matched the expected LF-only multiline files.

## Main File Counts

| File | LF | CR | Splitlines | Final LF |
| --- | ---: | ---: | ---: | --- |
| `scripts/check-alpha-env.py` | 222 | 0 | 222 | Yes |
| `services/api/manga_api/routes/alpha.py` | 306 | 0 | 306 | Yes |
| `scripts/scan-hidden-unicode.py` | 316 | 0 | 316 | Yes |

## Authentication Truth Statement

- `ALPHA_USER_TOKENS` is the recommended controlled-alpha authentication mode.
- Trusted forwarded headers are allowed only behind a trusted proxy.
- `AUTH_JWKS_URL` is future/reserved and does not currently validate users.

## Text Normalization Statement

- `.gitattributes` enforces LF line endings for text files.
- `scripts/scan-hidden-unicode.py` catches CR bytes, BOM, hidden Unicode, and missing final newlines.
- `scripts/normalize-text-files.py --check` is available to verify text normalization without rewriting files.

## Status

- Local demo: ready
- Founder demo: ready
- Controlled private alpha: ready with per-user tokens
- Public beta: not ready
- Production: not ready

Mock art proves pipeline behavior, not final commercial art quality.

## Public Beta And Production Blockers

- Replace controlled-alpha token auth with a real auth provider or fully hardened trusted proxy flow.
- Add real production rate limiting.
- Continue provider hardening before enabling paid or external generation for testers.
- Rehearse backup and restore procedures.
- Continue upload, export, storage, and admin security review.
