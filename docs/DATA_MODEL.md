# Data Model

## Projects

`projects` are the top-level manga workspaces.

Important fields:

- `id`: UUID primary key.
- `name`: display name.
- `description`: optional project brief.
- `style_prompt`: reusable visual style guidance.
- `status`: currently `draft` or `archived`.
- `active_style_bible_id`: optional active style pointer for prompt assembly.
- `created_at`, `updated_at`: audit timestamps.

Relationships:

- One project has many pages.
- One project can own many assets and generation jobs.

## Assets

`assets` store object-storage metadata only. Binary files live in MinIO or another S3-compatible store.

Important fields:

- `project_id`: optional owning project.
- `filename`: original or generated filename.
- `kind`: `source`, `render`, or future asset categories.
- `content_type`: MIME type.
- `size_bytes`: object size.
- `storage_key`: object-storage key.
- `metadata_json`: flexible metadata for provider, upload, and render details.

Final page exports use `kind = page_composite` and store page id, dimensions, reading direction, bleed, safe margin, panel count, bubble count, and public URL in `metadata_json`.

## Pages

`pages` belong to projects and define a manga page canvas.

Important fields:

- `project_id`: owning project.
- `page_number`: project-local page order.
- `width`, `height`: canvas dimensions in pixels.
- `layout_json`: page layout settings such as bleed, safe margin, reading direction, and QA overlay state.

Relationships:

- One page has many panels.
- Jobs can reference a page for page-level or panel-level generation.

## Panels

`panels` belong to pages and define rectangular page regions.

Important fields:

- `page_id`: owning page.
- `x`, `y`, `width`, `height`: rectangle geometry in page pixels.
- `polygon`: future-ready panel polygon points.
- `reading_order`: page-local reading sequence.
- `prompt`: optional panel render prompt.

Panel polygons are stored as points:

```json
[
  { "x": 0, "y": 0 },
  { "x": 100, "y": 0 },
  { "x": 100, "y": 100 },
  { "x": 0, "y": 100 }
]
```

## Bubbles

`bubbles` store speech bubbles, thought bubbles, narration boxes, and shout bubbles attached to panels.

Important fields:

- `panel_id`: owning panel.
- `kind`: `speech`, `thought`, `narration`, or `shout`.
- `x`, `y`, `width`, `height`: page-space geometry.
- `text`: required bubble content.

## Character Lab

`character_cards` store character continuity data for future generation providers.

Important fields:

- `name`, `aliases`, `age_range`, `role`.
- `personality`, `voice_style`.
- `face_description`, `hair_description`, `eye_description`, `body_type`.
- `outfit_default`, `accessories`, `scars_marks`.
- `forbidden_changes`, `continuity_rules`.

Related tables:

- `character_reference_assets`: metadata-only reference image records.
- `expression_sheets`: generated or curated expression sets.
- `outfit_variants`: alternate costume continuity records.

## Style Lab

`style_bibles` store reusable visual style guidance. The table also retains legacy Story Room style fields for compatibility.

Lab fields include:

- `name`
- `linework`
- `screentone`
- `hatching`
- `black_white_balance`
- `face_language`
- `anatomy_style`
- `background_detail`
- `panel_rhythm`
- `sfx_style`
- `typography_notes`
- `forbidden_references`
- `prompt_style_positive`
- `prompt_style_negative`

`style_sample_assets` store metadata-only references for style samples. Projects attach one active style with `active_style_bible_id`.

## Generation Jobs

`generation_jobs` represent asynchronous work.

Important fields:

- `project_id`, `page_id`, `panel_id`: optional scope pointers.
- `provider`: `mock` now, later `openai`, `comfyui`, or another provider.
- `job_type`: currently `render_panel`.
- `status`: `queued`, `running`, `succeeded`, or `failed`.
- `input_payload`: normalized request inputs, including assembled prompt JSON, flattened prompt text, provider name, model name, size, references, seed, and provider options.
- `output_payload`: normalized result metadata, including output asset id, render id, object storage key, public URL, provider, model name, seed, and provider options.
- `error_message`: failure details.

## Prompt Registry And AI Task Runs

`prompt_templates` store the database mirror of versioned prompt registry files from `services/api/app/prompts`.

Important fields:

- `id`: stable template id such as `generate_story_bible.v1`.
- `name`, `version`, `task_type`.
- `system_prompt`, `user_prompt_template`.
- `output_schema_name`: Pydantic schema expected from the task.
- `default_options`: JSON defaults such as temperature.
- `safety_notes`, `changelog`.

`ai_task_runs` store every structured LLM task execution.

Important fields:

- `prompt_template_id`: template used.
- `task_type`, `status`, `provider`, `model`.
- `schema_name`, `schema_version`.
- `raw_input`: inputs plus rendered prompts and template metadata.
- `raw_output`: raw model output and retry attempts.
- `parsed_output`: schema-validated JSON output.
- `token_metadata`, `cost_metadata`: provider metadata when available.
- `error_message`, `attempt_count`.

## Renders

`renders` represent completed visual outputs.

Important fields:

- `job_id`: generation job that produced the render.
- `panel_id`: panel this image belongs to.
- `asset_id`: asset metadata row for the stored PNG.
- `storage_key`: object-storage key.
- `public_url`: local or public URL when available.
- `width`, `height`, `mime_type`: rendered file metadata.

## QA Reports

`qa_reports` store Manga QA results for project, page, or panel targets.

Important fields:

- `target_type`: `project`, `page`, or `panel`.
- `target_id`: UUID of the checked target.
- `overall_score`: 0-100 deterministic score.
- `scores`: JSON category scores for story plan, layout, renders, lettering, and export.
- `issues`: JSON issue list with severity, target ids, blocking flag, and details.
- `recommendations`: JSON recommendations linked to page, panel, or bubble targets.
- `blocking`: true when one or more issues should prevent export.

## Exports

`exports` store project-level publishing jobs.

Important fields:

- `project_id`: exported project.
- `format`: `zip`, `pdf`, `epub`, or `layered`.
- `status`: `queued`, `running`, `succeeded`, or `failed`.
- `file_asset_id`: generated `project_export` asset when the export succeeds.
- `options`: JSON options such as `force` and caller metadata.
- `error_message`: validation or build failure details.

## Story Bible

`story_bibles` store the canonical narrative foundation for a project.

Important fields:

- `logline`, `synopsis`, `genre`, `target_audience`, `tone`.
- `themes`, `world_rules`, `chapter_outline`, `continuity_rules` as JSON arrays.
- `main_conflict` as the central story pressure.

Related tables:

- `characters`: cast entries with role, description, traits, and visual notes.
- `locations`: recurring places with description, visual notes, and local rules.
- `key_objects`: important props or artifacts with significance and visual notes.
- `style_bibles`: visual continuity guidance for line art, palette, paneling, lettering, and negative prompts.

## Chapter And Page Plans

`chapters` and `scenes` describe story structure.

`page_plans` and `panel_plans` translate that structure into manga layout beats.

Panel plan fields include:

- `panel_order`
- `story_beat`
- `shot_type`
- `camera_angle`
- `characters`
- `location`
- `dialogue`
- `narration`
- `visual_notes`
- `emotional_intent`
