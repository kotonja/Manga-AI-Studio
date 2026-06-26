# Secret Scan

## Commands Used

- `git status --ignored -s`
- `rg --files -g ".env*" -g "!node_modules" -g "!.next" -g "!apps/web/.next" -g "!apps/web/node_modules"`
- `rg --files-with-matches -i "OPENAI_API_KEY|COMFYUI_BASE_URL|ALPHA_ADMIN_TOKEN|ALPHA_SESSION_SECRET|DATABASE_URL|POSTGRES_PASSWORD|MINIO_SECRET_KEY|AWS_SECRET|AWS_ACCESS|Bearer |sk-[A-Za-z0-9]|gh[opsu]_[A-Za-z0-9_]+|BEGIN (RSA|OPENSSH|PRIVATE) KEY|refresh_token|access_token|cookie|session|password" ...`
- `rg --files-with-matches -i "OPENAI_API_KEY|Bearer |sk-[A-Za-z0-9]|gh[opsu]_[A-Za-z0-9_]+|AWS_SECRET|AWS_ACCESS|password|secret|token|cookie|session" evidence/final_boss_demo ...`
- Local absolute path scan across `docs`, handoff artifacts, and evidence manifest JSON files for Windows, macOS, and Linux home-directory paths.

## Findings

- `.env` exists locally but is ignored and was not staged.
- Ignored runtime/build/cache paths were present and left unstaged: `node_modules`, `apps/web/.next`, Playwright test output, Python caches, pytest cache, and egg-info metadata.
- `.env.example`, `.env.prod.example`, and `.env.test.example` contain documented placeholders/defaults only.
- Keyword scans found expected config names, route names, docs, tests, and placeholder strings.
- Evidence scan false positives were reviewed:
  - `evidence/final_boss_demo/characters.json` contains the character trait text `secretly gentle`.
  - `evidence/final_boss_demo/logs/compose-build.log` contains Docker registry wording about pull tokens, not a token value.
  - `evidence/final_boss_demo/logs/frontend-build.log` contains the route name `/admin/ai-task-runs`.
- No local absolute paths were found in docs, handoff artifacts, or evidence manifest JSON files.

## Removed Or Cleaned

- No secret values were removed because no committed or staged real secrets were detected.

## Final Result

Secrets detected: no.
