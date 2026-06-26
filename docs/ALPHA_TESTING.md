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

Local development can run without auth. For private alpha, set:

```bash
ALPHA_AUTH_ENABLED=true
ALPHA_SHARED_PASSWORD=change-me
ALPHA_SESSION_SECRET=change-me-to-a-long-random-value
ENABLE_DEV_ADMIN=false
```

Admin API access can use `ENABLE_DEV_ADMIN=true` in local development only. Production should connect a real auth provider or trusted reverse-proxy identity header:

```bash
AUTH_PROVIDER_MODE=external
AUTH_PROVIDER_NAME=your-auth-provider
AUTH_FORWARDED_USER_HEADER=X-Authenticated-User
```

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

- No multi-user collaboration or per-user project ownership yet.
- Local alpha auth is intentionally simple; use a real provider for production.
- Real provider calls depend on external configuration and may cost money.
- Visual consistency and multimodal QA are still placeholder/mock-first.
- Export packages are MVP-standard skeletons, not full marketplace certification.

## Safety and IP Rules

- Only upload assets you own or have permission to use.
- Do not request exact copies of named franchises, living artists, or protected character designs.
- Avoid prompts such as "exactly like", "same as", or "in the style of" a specific artist/franchise.
- Review AI-assisted output before publishing.
- Keep alpha output private unless rights, disclosure, and provider terms are confirmed.
