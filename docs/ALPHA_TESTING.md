# Manga AI Studio Private Alpha

Manga AI Studio alpha is intended for a small tester group validating the complete manga creation loop: premise, story planning, character/style setup, page layout, mock rendering, lettering, QA, provenance, and export.

## What Works

- Founder Demo and Director Mode can create draft projects with deterministic mock providers.
- Story Room, Character Lab, Style Lab, Page Studio, Lettering Room, QA Room, Provenance, and Publishing Room are available for inspection and editing.
- Mock panel rendering, page composition, QA checks, ZIP/PDF/EPUB/webtoon/archive export paths, and provenance files are testable locally.
- Feedback can be submitted from the global Feedback button with project/page context.
- Failed panel render jobs can be retried with the mock provider.

## Mock Only

- Mock LLM/image/QA providers are deterministic placeholders and do not claim real model quality.
- Placeholder manga art is for workflow testing, not final production art.
- OpenAI and ComfyUI hooks are present, but testers should use dry-run and provider health checks before making any real provider call.

## Auth for Alpha

Local development can run without auth. Requests map to a local `local-dev` user so one-command demo runs stay simple.

For private alpha, set:

```bash
ALPHA_AUTH_ENABLED=true
ALPHA_SHARED_PASSWORD=change-me
ALPHA_USER_TOKENS=tester-a:long-token-a,tester-b:long-token-b
ALPHA_SESSION_SECRET=change-me-to-a-long-random-value
ENABLE_DEV_ADMIN=false
S3_PUBLIC_READ_ENABLED=false
ASSET_DOWNLOAD_MODE=proxy
```

With alpha auth enabled, the web login sets a signed `manga_alpha_session` cookie and browser API requests include credentials. The cookie is signed with `ALPHA_SESSION_SECRET` and carries `user_id`, `is_admin`, `iat`, and `exp`; malformed, expired, unsigned, or invalid-signature cookies are rejected. API clients can also use `X-Alpha-Token` or `Authorization: Bearer ...`. Projects are owner-scoped: project lists, project detail, pages, panels, jobs, exports, asset downloads, provenance, and related nested resources verify ownership before returning data. General feedback without project/page/panel context remains public so testers can report onboarding or login issues.

For multi-user private alpha, use `ALPHA_USER_TOKENS` or external auth. If a tester logs in with the token for `tester-a:long-token-a`, browser-created projects are owned by `tester-a`; `tester-b` receives a separate signed session and cannot access tester A's projects. `ALPHA_SHARED_PASSWORD` maps every browser login to the same shared `alpha-user` account and is only suitable for tiny demos where tester isolation is not required.

Admin API access can use `ENABLE_DEV_ADMIN=true` in local development only. Production should connect a real auth provider or trusted reverse-proxy identity header:

```bash
AUTH_PROVIDER_MODE=external
AUTH_PROVIDER_NAME=your-auth-provider
AUTH_FORWARDED_USER_HEADER=X-Authenticated-User
TRUST_EXTERNAL_AUTH_HEADERS=true
```

Only set `TRUST_EXTERNAL_AUTH_HEADERS=true` when the API is behind a trusted proxy that strips spoofed incoming identity/admin headers and injects authenticated identity headers itself. Without that switch, forwarded auth headers are rejected.

Never commit real passwords, API keys, or provider tokens.

## What Users Should Test

- Create a project from the dashboard and from Founder Demo.
- Generate a draft manga in mock mode.
- Open Story Room and confirm the story bible is understandable.
- Edit one character card and one style bible.
- Open Page Studio, suggest/edit layout, render a panel, and retry a failed job if one appears.
- Compose a page, run QA, apply safe fixes where available, and export ZIP/PDF/webtoon.
- Check provenance and rights declaration before exporting.
- Submit feedback for confusing labels, broken flows, poor empty states, or bad error messages.
- Use thumbs up/down ratings on generated story, character cards, page layouts, panel renders, and exports.

## Product Learning Controls

Projects are private by default. Aggregate operational metrics such as success rates, retry rates, QA categories, provider failures, average page QA score, and export success rate do not include prompt text, story text, image data, or uploaded files.

Ratings and corrections are used for product improvement only when both are true:

- The project has `allow_product_improvement` enabled in Settings.
- The individual feedback item is submitted with product-improvement opt-in checked.

Training use is separate and remains off unless the project owner explicitly enables `allow_training`. Alpha testers should leave training use off unless they intentionally want the project considered for future training workflows.

## How to Report Bugs

Use the in-app Feedback button and include:

- What you were trying to do.
- What happened.
- What you expected.
- Whether the project used mock mode or a real provider.
- Any copied diagnostic info from the error screen.

The feedback form automatically attaches current route context when it can detect a project or page.

## Known Limitations

- No multi-user collaboration yet; ownership is isolation-oriented rather than a sharing/collaboration model.
- Local alpha auth is intentionally simple; use a real provider or trusted auth proxy for production.
- Real provider calls depend on external configuration and may cost money.
- Visual consistency and multimodal QA are still placeholder/mock-first.
- Export packages are MVP-standard skeletons, not full marketplace certification.

## Safety and IP Rules

- Only upload assets you own or have permission to use.
- Do not request exact copies of named franchises, living artists, or protected character designs.
- Avoid prompts such as "exactly like", "same as", or "in the style of" a specific artist/franchise.
- Review AI-assisted output before publishing.
- Keep alpha output private unless rights, disclosure, and provider terms are confirmed.
