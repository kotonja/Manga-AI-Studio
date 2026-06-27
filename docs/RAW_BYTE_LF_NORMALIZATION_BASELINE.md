# Raw-Byte LF Normalization Baseline

Date: 2026-06-27

This document records the raw-byte LF normalization baseline after PR #6 was merged into `main`.

## Git References

- PR: #6, `raw-byte-lf-normalization-fix`
- PR source commit: `9707d74949890912b25158cccb550ed32a8d9add`
- PR merge commit on `main`: `1aeb12ba1b9ddad2ea94d7b68635864dfb143012`
- Baseline tag: `v0.1.4-raw-lf-normalized`

## Scope

This fix changes only text normalization and scanner behavior.

It does not change manga generation, auth behavior, or deployment behavior.

PR #4 remains blocked until it is refreshed on this new `main` baseline.

## Critical File Byte Counts

The following counts were verified locally on `main` and through public raw GitHub URLs after the merge.

| File | Local LF_0A | Local CR_0D | Public raw LF_0A | Public raw CR_0D | Bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `.gitattributes` | 26 | 0 | 26 | 0 | 503 |
| `scripts/check-alpha-env.py` | 227 | 0 | 227 | 0 | 8374 |
| `scripts/create-alpha-token.py` | 55 | 0 | 55 | 0 | 1782 |
| `scripts/alpha-smoke-test.py` | 119 | 0 | 119 | 0 | 4807 |
| `scripts/scan-hidden-unicode.py` | 349 | 0 | 349 | 0 | 9518 |
| `scripts/normalize-text-files.py` | 371 | 0 | 371 | 0 | 10422 |
| `services/api/manga_api/routes/alpha.py` | 311 | 0 | 311 | 0 | 11958 |

All critical files ended with a final `0A` byte.

## Verification Results

- `python scripts/normalize-text-files.py --check`: passed.
- `python scripts/scan-hidden-unicode.py`: passed.
- `python -m py_compile` for the alpha utility scripts and alpha route: passed.
- `python -m pytest -q services/api/tests/test_alpha_readiness.py services/api/tests/test_alpha_launch_ops.py`: `18 passed, 1 warning`.
- `python -m pytest -q services/api/tests`: `122 passed, 3 warnings`.
- `pnpm --filter @manga-ai/web typecheck`: passed.
- `pnpm --filter @manga-ai/web build`: passed.
- `pnpm --filter @manga-ai/web smoke`: `3 passed`.
- `docker compose config --quiet`: passed.

## Baseline Status

`main` now enforces physical LF byte thresholds for the critical files in both `scripts/scan-hidden-unicode.py` and `scripts/normalize-text-files.py`.

Future release or deployment branches should be refreshed from this baseline before merge.
