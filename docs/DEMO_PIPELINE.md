# Demo Pipeline

The demo pipeline is the end-to-end smoke path for Manga AI Studio.

Endpoint:

```http
POST /demo/create-full-project
```

Premise:

```text
A lonely swordsman protects a ghost child in a ruined city.
```

## What It Creates

- Project: `Ghost Lantern`
- Story bible
- Two story characters
- Two Character Lab cards
- One location
- One key object
- One active style bible
- One chapter
- Four pages
- Eight panels
- Eight bubbles
- Eight mock panel render PNGs
- Four composed page PNGs
- Four QA reports
- ZIP export
- PDF export

## How To Run

From the dashboard, click **Create Demo Manga**.

From the command line:

```bash
sh scripts/seed-demo.sh
```

Raw API:

```bash
curl -X POST http://localhost:8000/demo/create-full-project \
  -H "Content-Type: application/json" \
  -d "{}"
```

The response contains the project id, story bible id, chapter id, page ids, panel ids, render job ids, composite asset ids, QA report ids, and export ids.

## Validation Path

After creation:

1. Open the returned project in the web app.
2. Inspect Story Room for the story bible.
3. Inspect Character Lab for Ren Aki and Mio.
4. Open a page in Page Studio and confirm panels, bubbles, composites, and QA.
5. Open Publishing Room and download ZIP/PDF exports.

The endpoint uses deterministic mock rendering, so it does not need API keys.

## Director Mode Difference

The demo endpoint always creates the fixed Ghost Lantern sample. Director Mode is the configurable path:

```http
POST /projects/{project_id}/director/generate-draft
GET /jobs/{job_id}/events
```

Use Director Mode from a project when you want to enter a new premise, choose page count and reading direction, and watch the orchestration timeline.
