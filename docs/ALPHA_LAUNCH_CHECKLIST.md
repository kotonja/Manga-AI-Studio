# Alpha Launch Checklist

Use this checklist before inviting the first controlled private-alpha testers.

## Before Deploy

- [ ] Confirm `main` is at `v0.1.2-alpha-launch-hotfix` or newer approved hotfix.
- [ ] Confirm deployment uses mock mode first.
- [ ] Confirm no real OpenAI or ComfyUI keys are present.
- [ ] Confirm public beta and production are explicitly out of scope.
- [ ] Confirm only 2 to 5 testers are invited.

## Secrets Generated

- [ ] Generate `ALPHA_SESSION_SECRET`.
- [ ] Generate `ALPHA_ADMIN_TOKEN`.
- [ ] Generate strong Postgres password.
- [ ] Generate strong MinIO access key and secret key.
- [ ] Store secrets outside the repository.

## Tokens Generated

- [ ] Generate one token per tester.
- [ ] Put tester pairs in `ALPHA_USER_TOKENS`.
- [ ] Store `.alpha-tokens.generated` securely if used.
- [ ] Send each tester only their own token.

## Env Validated

- [ ] Copy `.env.alpha.example` to `.env.alpha`.
- [ ] Replace every placeholder.
- [ ] Run `python scripts/check-alpha-env.py --env-file .env.alpha`.
- [ ] Confirm `ENABLE_DEV_ADMIN=false`.
- [ ] Confirm `NEXT_PUBLIC_ENABLE_DEV_ADMIN=false`.
- [ ] Confirm `TRUST_EXTERNAL_AUTH_HEADERS=false`.

## Database Migrated

- [ ] Start Postgres.
- [ ] Confirm the API service runs `alembic upgrade head`.
- [ ] Confirm app startup logs show migration success.
- [ ] Back up the database before inviting testers.

## Storage Protected

- [ ] Confirm `S3_PUBLIC_READ_ENABLED=false`.
- [ ] Confirm `ASSET_DOWNLOAD_MODE=proxy`.
- [ ] Confirm MinIO console is not publicly exposed.
- [ ] Confirm direct object URLs are not required for export download.

## Worker Running

- [ ] Start the worker service.
- [ ] Confirm worker logs show Celery ready.
- [ ] Confirm mock render jobs complete.
- [ ] Confirm failed jobs store clear errors.

## Alpha Readiness Endpoint Passing

- [ ] Run `/health`.
- [ ] Run `/health/db`.
- [ ] Run `/health/redis`.
- [ ] Run `/health/storage`.
- [ ] Run `/health/worker`.
- [ ] Run `/alpha/readiness` with the admin token.

## Demo Project Generated

- [ ] Log in as a tester.
- [ ] Run Founder Demo or `POST /demo/create-full-project`.
- [ ] Confirm project opens in Studio.
- [ ] Confirm story, characters, pages, QA, and publishing rooms load.

## Export Download Tested

- [ ] Create a ZIP export or use the demo export.
- [ ] Download through `/exports/{id}/download`.
- [ ] Confirm file opens locally.
- [ ] Confirm provenance/disclosure files are included when expected.

## Wrong-User Access Tested

- [ ] Create a project as tester A.
- [ ] Attempt to access it as tester B.
- [ ] Confirm tester B receives `403` or `404`.
- [ ] Confirm tester B cannot download tester A exports.

## Admin Readiness Page Checked

- [ ] Open `/admin/alpha-readiness` with admin access.
- [ ] Confirm readiness checks pass.
- [ ] Confirm no tester token is shown in the UI.
- [ ] Confirm failed checks are understandable.

## Tester Invite Sent

- [ ] Fill in `docs/ALPHA_TESTER_INVITE_TEMPLATE.md`.
- [ ] Include app link.
- [ ] Include only that tester's token.
- [ ] Include upload safety reminders.
- [ ] Include support contact.

## Feedback Review Scheduled

- [ ] Schedule daily alpha triage.
- [ ] Review feedback, failed jobs, QA failures, and provider errors.
- [ ] Decide P0/P1/P2/P3 using `docs/ALPHA_FEEDBACK_TRIAGE.md`.

## Emergency Shutdown Path Known

- [ ] Know how to stop the stack.
- [ ] Know how to revoke a tester token.
- [ ] Know how to disable external access at the reverse proxy/firewall.
- [ ] Know how to back up database and MinIO volumes before debugging.
- [ ] Know who will notify testers if the alpha is paused.
