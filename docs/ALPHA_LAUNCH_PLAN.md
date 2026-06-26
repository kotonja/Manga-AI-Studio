# Private Alpha Launch Plan

Manga AI Studio `v0.1.0-private-alpha` is ready for a small controlled tester launch with per-user tester tokens and deterministic mock providers.

## Audience

This alpha is for trusted testers who can give detailed product feedback and understand that generated art is mock/draft quality. It is not for public signup, paid customers, press demos, or commercial publishing.

## What Testers Can Do

- Log in with a per-user alpha token.
- Run the Founder Demo and create a complete mock manga draft.
- Create projects, inspect Story Room, Character Lab, Style Lab, Page Studio, Lettering Room, QA Room, and Publishing Room.
- Use deterministic mock rendering and exports to validate the workflow.
- Submit feedback with project, page, and panel context.

## What Testers Should Not Expect

- Production uptime, data retention guarantees, or public-beta polish.
- Final commercial-quality art from mock providers.
- Fully hardened real OpenAI or ComfyUI generation paths.
- Public collaboration, billing, marketplace, or long-term account management.

## Mock Mode Versus Real Provider Mode

Mock mode is the default for launch validation. It is deterministic, free, and proves that the pipeline can create pages, QA reports, provenance, and exports.

Real provider mode should only be enabled after provider health and dry-run checks pass. Real providers can cost money, have latency, and may fail differently from mock mode.

Mock art proves pipeline behavior, not final commercial art quality.

## Tester Tokens

Generate one token per tester:

```powershell
python scripts/create-alpha-token.py --user tester-a
python scripts/create-alpha-token.py --user tester-b --write
```

Copy the generated pairs into `ALPHA_USER_TOKENS`:

```env
ALPHA_USER_TOKENS=tester-a:token-a,tester-b:token-b
```

Never reuse the same token for multiple testers unless you intentionally want shared access.

## Revoking a Tester

1. Remove that tester's `user-id:token` pair from `ALPHA_USER_TOKENS`.
2. Restart the API and web services so the new env is loaded.
3. If immediate browser logout is required, rotate `ALPHA_SESSION_SECRET`.
4. Keep the user's existing projects for audit unless deletion is explicitly requested and versioned.

## Rotating `ALPHA_SESSION_SECRET`

1. Generate a new strong random secret.
2. Update `ALPHA_SESSION_SECRET` in the deployment environment.
3. Restart API and web services.
4. Tell testers to log in again.

Rotating the secret invalidates existing browser sessions.

## Resetting a Test Deployment

For a disposable local environment:

```powershell
docker compose down
docker volume rm manga-ai_postgres-data manga-ai_minio-data
docker compose up --build
```

For hosted alpha, take a backup first, then run the documented database/storage reset procedure for that environment.

## Feedback Collection

- Ask testers to use the in-app feedback button whenever possible.
- Ask for a short title, severity, what they expected, and what happened.
- Project/page/panel context should be attached when available.
- Admins triage feedback as `new`, `triaged`, `fixed`, or `wontfix`.

## Bug Triage

1. Check `/admin/alpha-readiness`.
2. Check `/admin/alpha` for failed jobs, provider errors, feedback, and QA blockers.
3. Reproduce with mock mode first.
4. Capture request id, project id, page id, panel id, and export id.
5. Mark severity:
   - `low`: cosmetic or unclear copy.
   - `medium`: confusing workflow or recoverable failure.
   - `high`: broken core path for one tester/project.
   - `blocker`: prevents login, generation, QA, export, or data access safety.

## Safety and IP Rules

- Testers must only upload assets they own or are licensed to use.
- Do not request exact copies of living artists, franchises, or protected characters.
- Do not publish or sell alpha output.
- Review all AI-assisted output before sharing externally.
- Keep private projects private unless the tester explicitly opts in to share feedback details.

## Known Limitations

- Mock art is intentionally placeholder/draft art.
- Real provider paths need more hardening before broad usage.
- Private-alpha auth is not a permanent production auth system.
- Rate limiting is still a placeholder.
- Operational backup/restore needs environment-specific rehearsal.

## Launch Checklist

- `main` is tagged `v0.1.0-private-alpha`.
- `python -m pytest -q services/api/tests` passes.
- `pnpm --filter @manga-ai/web build` passes.
- `pnpm --filter @manga-ai/web smoke` passes.
- `docker compose config --quiet` passes.
- `python scripts/check-alpha-env.py` passes for deployment env.
- `/alpha/readiness` shows no failed checks.
- Each tester has a unique token.
- `ALPHA_SHARED_PASSWORD` is empty for multi-user alpha.
- `S3_PUBLIC_READ_ENABLED=false`.
- `ASSET_DOWNLOAD_MODE=proxy`.
- Admin has an emergency shutdown plan.

## Rollback Plan

1. Stop inviting testers.
2. Set `ALPHA_AUTH_ENABLED=true` and remove tester tokens, or shut down public ingress.
3. Preserve logs, database, and object storage for investigation.
4. Roll deployment back to the last known-good image/tag.
5. Rotate `ALPHA_SESSION_SECRET` before re-opening access.
