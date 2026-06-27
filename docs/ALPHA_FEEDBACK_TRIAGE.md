# Alpha Feedback Triage

Use this process during the first controlled private alpha to turn tester feedback into clear engineering priorities without expanding scope.

## Severity Levels

P0 - Stop the alpha:

- Data from one tester is visible to another tester.
- Exports or assets can be downloaded without proper authorization.
- Admin-only surfaces are exposed to testers.
- App is down for all testers.
- Secrets appear in logs, UI, exports, or error messages.

P1 - Fix before inviting more testers:

- Founder Demo cannot complete.
- Demo project generation fails repeatedly.
- Export downloads fail for normal tester projects.
- Worker or API errors make the main workflow unusable.
- Alpha readiness endpoint reports a blocking failure.

P2 - Fix during alpha:

- A room loads but has broken controls.
- Confusing UX causes testers to get stuck.
- QA/export warnings are unclear.
- Feedback submission is unreliable but alternate reporting works.
- Performance is slow but usable.

P3 - Track for later:

- Copy improvements.
- Non-blocking visual polish.
- Nice-to-have workflow shortcuts.
- Requests for real image providers.
- Feature ideas beyond the controlled-alpha goal.

## Bug Categories

- Access/auth
- Project creation
- Founder demo
- Story/planning
- Character/style
- Page Studio
- Rendering/mock assets
- Lettering/composition
- QA
- Export/download
- Feedback/admin
- Performance
- Documentation
- Safety/IP/provenance

## Reproduction Notes

For each issue, capture:

- Tester id, not the raw token.
- Timestamp and timezone.
- Browser and operating system.
- Project id, page id, panel id, or export id if relevant.
- Exact steps to reproduce.
- Expected result.
- Actual result.
- Screenshot or screen recording if available.
- Relevant API, worker, web, or reverse proxy logs with secrets removed.

## P0/P1/P2/P3 Decision Guide

Choose P0 when the issue compromises isolation, protected downloads, secrets, admin boundaries, or the whole alpha availability.

Choose P1 when the issue blocks the core promise: enter the app, create or inspect a demo manga, and export a result.

Choose P2 when the issue affects an important workflow but a tester can continue with guidance or a retry.

Choose P3 when the issue is feedback, polish, or future product direction.

## Daily Triage Checklist

- Review new feedback items.
- Check failed jobs and provider errors.
- Check latest QA failure categories.
- Confirm `/health` and `/alpha/readiness` still pass.
- Review access-denied logs for suspicious patterns.
- Test one export download through the protected proxy.
- Confirm no tester reported cross-user visibility.
- Pick the smallest set of P0/P1 fixes before inviting additional testers.
- Send testers a short status update if a blocker affects them.

## Feedback That Matters Most

For this alpha, prioritize:

- Can testers log in reliably with per-user tokens?
- Can testers understand what mock mode means?
- Does the Founder Demo feel magical enough to explain the product?
- Can testers inspect story, characters, pages, QA, and exports?
- Are asset/export downloads protected?
- Are errors understandable and recoverable?
- Are testers comfortable with the rights and upload warnings?

Do not treat requests for paid providers, public sharing, collaboration, or commercial-quality art as blockers for this alpha.
