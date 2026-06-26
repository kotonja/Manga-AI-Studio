# Demo Visual Quality

The Founder Demo and final-boss evidence use deterministic mock rendering. The images are not presented as real model output; they are polished local placeholders that prove the production pipeline can create, render, compose, QA, and export a manga draft without paid API keys.

## What The Mock Art Represents

- A ruined city with cracked silhouettes, broken towers, rain, and high-contrast gutters.
- Ren, the lonely swordsman, as a tall dark figure with a sword and coat silhouette.
- Mio, the ghost child, as a smaller glowing figure tied to a lantern motif.
- Manga-specific draft language: screentone texture, speed lines, black fills, speech bubbles, panel borders, and page/panel numbering.
- Four distinct story beats: establishing/meeting, danger/protection, chase/action, and quiet resolution.

## What Changed

- Removed raw debug strings, UUID snippets, provider names, and prompt fragments from composed final pages.
- Replaced blank rectangle placeholders with deterministic manga-style panel art.
- Added varied page layouts across the four-page evidence set, including wide, tall, and large dramatic panels.
- Kept protected asset download support in the UI so private-alpha images do not depend on public MinIO URLs.
- Regenerated final pages, ZIP/PDF exports, provenance, and the export manifest.

## Evidence Files

- `evidence/final_boss_demo/final_pages/page-001.png`
- `evidence/final_boss_demo/final_pages/page-002.png`
- `evidence/final_boss_demo/final_pages/page-003.png`
- `evidence/final_boss_demo/final_pages/page-004.png`
- `evidence/final_boss_demo/export_manifest.json`
- `evidence/final_boss_demo/provenance.json`
- `evidence/final_boss_demo/exports/zip-be896d20-ecd0-4186-9670-5ce980e52154.zip`
- `evidence/final_boss_demo/exports/pdf-f6c27c0c-eb06-490d-bf47-2b33594fc952.pdf`

## Limitations

- Mock pages are storyboard-quality proof images, not final commercial artwork.
- Character consistency is represented through silhouettes and labels rather than true image identity preservation.
- OpenAI and ComfyUI providers remain optional and are not required for tests or the local founder demo.
- Public beta still needs real authentication, stricter rate limiting, and a production asset access policy review.
