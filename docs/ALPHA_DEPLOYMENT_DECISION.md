# Alpha Deployment Decision

This document compares practical deployment paths for the first controlled private alpha of Manga AI Studio `v0.1.2-alpha-launch-hotfix`.

Current release posture:

- Local demo: ready
- Founder demo: ready
- Controlled private alpha: ready with per-user tokens
- Public beta: not ready
- Production: not ready
- Mock mode should be used first

## Option 1: Local Machine Only

Run the full Docker Compose stack on one trusted local machine and let testers use it only through a local network, tunnel, or screen-shared demo session.

Pros:

- Fastest to operate with the fewest moving parts.
- Keeps data and generated mock assets on a machine you control.
- Good for internal rehearsals and one-on-one guided demos.
- Easy to stop immediately by shutting down Compose.

Cons:

- Not reliable for multiple remote testers.
- Depends on the host machine staying awake and connected.
- Tunnels can add security and reliability uncertainty.
- Harder to collect realistic private-alpha usage patterns.

Risk level: low for internal demos, medium for remote testers.

Operational difficulty: low.

Recommended use: rehearsal, founder demo, and final pre-alpha smoke testing.

Secrets needed:

- `ALPHA_SESSION_SECRET`
- `ALPHA_USER_TOKENS`
- `ALPHA_ADMIN_TOKEN`
- Postgres password
- MinIO access key and secret key

Expected maintenance:

- Pull updates manually.
- Run migrations through the API service startup.
- Back up local Postgres and MinIO volumes before resets.
- Watch local logs during testing.

## Option 2: Single VPS / Docker Compose

Run one private deployment on a small VPS using Docker Compose, with a reverse proxy and TLS in front of the web/API services.

Pros:

- Best balance for the first controlled alpha.
- Gives 2 to 5 testers a stable shared URL.
- Keeps the stack simple: Postgres, Redis, MinIO, API, worker, web.
- Per-user alpha tokens can be issued and revoked manually.
- Easier to protect asset/export downloads through the API proxy.

Cons:

- Requires server patching, backups, firewall rules, and log review.
- Single host means single point of failure.
- Must keep MinIO and internal service ports private.
- Needs disciplined secret handling.

Risk level: medium.

Operational difficulty: medium.

Recommended use: first controlled private alpha in mock mode.

Secrets needed:

- `ALPHA_SESSION_SECRET`
- `ALPHA_USER_TOKENS`
- `ALPHA_ADMIN_TOKEN`
- Postgres password
- MinIO access key and secret key
- TLS/reverse proxy credentials, depending on provider

Expected maintenance:

- Apply OS and Docker updates.
- Back up Postgres and MinIO volumes.
- Review `api`, `worker`, and `web` logs daily during alpha.
- Rotate tester tokens if a tester leaves or a token leaks.
- Keep real provider keys unset until a separate provider hardening pass.

## Option 3: Managed Container Platform

Deploy the API, worker, web, database, Redis, and object storage using managed container, database, cache, and storage services.

Pros:

- Better long-term reliability and scaling path.
- Managed database and storage backups are easier to automate.
- Cleaner separation between services.
- More production-like observability options.

Cons:

- More setup complexity before the first alpha.
- More places to configure secrets incorrectly.
- Managed object storage and public URL behavior must be reviewed carefully.
- Can create accidental cost exposure if paid providers or autoscaling are enabled too early.

Risk level: medium to high for the first alpha, lower later with infrastructure hardening.

Operational difficulty: high.

Recommended use: later private alpha or pre-beta deployment after the single-host run proves the workflow.

Secrets needed:

- All app alpha auth secrets.
- Managed database credentials.
- Managed Redis credentials.
- Managed object storage credentials.
- Platform deploy tokens.
- TLS/domain configuration.

Expected maintenance:

- Monitor service health and cloud spend.
- Maintain infrastructure-as-code or platform deployment manifests.
- Configure backups, retention, and restore drills.
- Add stronger auth and rate limiting before public exposure.

## Recommendation

Use a single private deployment in mock mode for the first controlled alpha.

Recommended shape:

- One private VPS or equivalent single-host deployment.
- Docker Compose stack behind TLS and a reverse proxy.
- 2 to 5 testers only.
- Per-user alpha tokens through `ALPHA_USER_TOKENS`.
- `ALPHA_ADMIN_TOKEN` held only by the operator.
- `S3_PUBLIC_READ_ENABLED=false`.
- `ASSET_DOWNLOAD_MODE=proxy` for protected asset/export downloads.
- No real OpenAI or ComfyUI calls.
- `MODEL_PROVIDER=mock`, `OPENAI_API_KEY=` empty, and `COMFYUI_BASE_URL=` empty.

This path gives testers the real app flow while keeping operational risk contained. Mock art proves pipeline behavior, not final commercial art quality.
