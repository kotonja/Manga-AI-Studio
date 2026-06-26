# Frontend Inventory

Generated at: 2026-06-26T13:42:55.804404+00:00

| Route | Purpose | Backend Dependencies | Status | Known UI Issues |
| --- | --- | --- | --- | --- |
| `/admin/ai-task-runs` | Developer-only AI task run inspector. | GET /admin/ai-task-runs | PARTIAL | Protected by dev flag/admin auth; keep disabled for untrusted users. |
| `/admin/alpha` | Private alpha admin health and feedback dashboard. | GET /admin/alpha-dashboard | PARTIAL | Protected by dev flag/admin auth; keep disabled for untrusted users. |
| `/admin/eval` | Developer-only evaluation harness UI. | GET /eval/scenarios, POST /eval/run | PARTIAL | Protected by dev flag/admin auth; keep disabled for untrusted users. |
| `/demo` | Founder Demo one-button walkthrough. | POST /demo/founder-run, GET /jobs/{id}/events, project/story/page/export endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/onboarding` | Private alpha onboarding and provider mode explanation. | GET /alpha/onboarding | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/` | Project dashboard and demo creation entry. | GET/POST /projects, POST /demo/create-full-project | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/characters` | Character cards, references, and continuity state. | character CRUD and reference asset metadata endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/director` | One-premise draft manga orchestrator. | POST /projects/{id}/director/generate-draft, GET /jobs/{id}/events | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}` | Project detail shell. | GET /projects/{id}, GET /projects/{id}/workspace-summary | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/pages/{pageId}/lettering` | Bubble and SFX lettering editor. | lettering, bubble, SFX, SVG endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/pages/{pageId}/studio` | Konva page layout, rendering, QA overlay, and panel preview. | layout, panel render, compose, QA endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/provenance` | Rights declarations and asset provenance. | rights declaration and provenance endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/publishing` | Export readiness and download room. | export create/get/download endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/qa` | Grouped QA issues and safe auto-fixes. | page/project QA and auto-fix endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/settings` | Project settings and operational status. | GET /projects/{id}, GET /projects/{id}/workspace-summary | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/story` | Story bible and chapter/page plan inspection. | story endpoints for bible, chapter plans, and page plans | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/style` | Style bible, StyleDNA options, and style safety warnings. | style bible CRUD, StyleDNA, style preview endpoints | WORKING | No blocker found in static inventory; covered by build and route smoke where applicable. |
| `/projects/{id}/world` | Locations and key object worldbuilding. | story bible location/key object data | PARTIAL | World Room is mostly metadata inspection from story generation, not a full bespoke editor. |
