# UX Polish Pass

This pass makes Manga AI Studio feel more like a premium production workspace while keeping existing API contracts intact.

## Navigation

- Project pages now share a persistent sidebar with room navigation.
- Rooms include Dashboard, Director Mode, Story Room, Character Lab, World Room, Style Lab, Page Studio, Lettering Room, QA Room, Publishing Room, Provenance, and Settings.
- The sidebar summarizes project status, active chapter, pages, panels, render progress, QA score, active jobs, and latest export status.

## Status Language

Status chips use a consistent visual vocabulary:

- Draft
- Planning
- Rendering
- Needs Review
- QA Passed
- Exported

## Room Improvements

- Dashboard has a stronger studio overview, metrics, loading skeletons, and a richer empty state.
- Director Mode has a stage animation, recovery affordance, and generated page preview cards.
- Story Room has a summary-first review surface plus panel-plan accordions.
- Character Lab has a character card grid, reference gallery treatment, continuity timeline, and approved-panel placeholders.
- World Room surfaces locations, key objects, world rules, and continuity rules from the Story Bible.
- Page Studio adds page thumbnails, viewport controls, grid toggle, safe-margin toggle, render status badges, bubble counts, and QA badges.
- Lettering Room adds metrics and clearer empty states for bubbles and SFX.
- Publishing Room adds export readiness checks and blocking QA warnings.
- Settings centralizes project readiness, rights metadata, and operations shortcuts.

## Verification Targets

Suggested screenshots after launching the app:

- `http://localhost:3000/` for the dashboard.
- `/projects/{id}` for the project sidebar and overview.
- `/projects/{id}/director` for the cinematic generation flow.
- `/projects/{id}/pages/{pageId}/studio` for the Page Studio controls.
- `/projects/{id}/publishing` for export readiness.
