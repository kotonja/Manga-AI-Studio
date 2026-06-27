# Repository Text Normalization Baseline

This document records the repository text-normalization baseline created after
PR #5 was merged into `main`.

## Baseline

- PR: #5, `Normalize repository text files to LF`
- Merge commit SHA: `863f9d07cfdf91eadc961137367bb62f74ad1ff8`
- Source commit SHA: `6323737d7921167f78cc1ca627990eb2756f63c3`
- Tag: `v0.1.3-text-normalized`

## Critical File Counts

The following counts were verified from public raw `main` URLs using `curl` with
cache-busting query strings.

| File | LF bytes | CR bytes | Bytes |
| --- | ---: | ---: | ---: |
| `.gitattributes` | 26 | 0 | 503 |
| `scripts/check-alpha-env.py` | 227 | 0 | 8374 |
| `scripts/create-alpha-token.py` | 55 | 0 | 1782 |
| `scripts/alpha-smoke-test.py` | 119 | 0 | 4807 |
| `scripts/scan-hidden-unicode.py` | 334 | 0 | 9018 |
| `scripts/normalize-text-files.py` | 358 | 0 | 9909 |
| `services/api/manga_api/routes/alpha.py` | 311 | 0 | 11958 |

## Verification Results

- `python scripts/normalize-text-files.py --check`: passed
- `python scripts/scan-hidden-unicode.py`: passed
- Python compile checks for alpha scripts and normalization scripts: passed
- Focused alpha backend tests: `18 passed, 1 warning`
- Full backend test suite: `122 passed, 3 warnings`
- Web typecheck: passed
- Web production build: passed
- Web browser smoke: `3 passed`
- `docker compose config --quiet`: passed

## Release Rule

`.gitattributes` enforces LF-delimited text for source, docs, config, and script
files while preserving binary assets as binary.

Before release branches or launch branches are merged, the following checks are
mandatory:

```powershell
python scripts/normalize-text-files.py --check
python scripts/scan-hidden-unicode.py
```

This baseline does not change manga generation, auth behavior, or deployment
behavior. It only fixes repository text normalization and hidden/control
character safety.
