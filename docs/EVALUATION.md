# Manga AI Evaluation Harness

The evaluation harness creates repeatable manga-generation runs and scores whether the pipeline is improving over time.

## Scenarios

- Dark fantasy revenge, 8 pages
- School romance confession, 6 pages
- Shonen battle intro, 8 pages
- Horror shrine mystery, 6 pages
- Comedy slice-of-life, 4 pages

Each scenario defines a premise, genre, tone, target audience, page count, expected character and location counts, key beats, page type expectations, and export requirements.

## Run From API

```bash
curl -X POST http://localhost:8000/eval/run \
  -H "Content-Type: application/json" \
  -d '{"scenario":"all","provider":"mock","quality_mode":"fast","write_reports":true}'
```

## Run From CLI

From `services/api`:

```bash
python -m app.eval.run --scenario all --provider mock
```

Inside Docker:

```bash
docker compose exec api python -m app.eval.run --scenario all --provider mock
```

## Reports

Runs write:

- `eval_reports/latest.json`
- `eval_reports/latest.md`

The report includes aggregate metrics and per-scenario scores, failures, counts, generated project ids, and local UI links.

## Metrics

- `pipeline_completion_rate`
- `story_schema_validity`
- `page_count_accuracy`
- `panel_count_accuracy`
- `character_state_coverage`
- `prompt_anchor_coverage`
- `render_asset_coverage`
- `composition_success_rate`
- `lettering_readability_score`
- `qa_blocking_issue_count`
- `export_success_rate`
- `total_generation_time`
- `estimated_cost`

Mock runs are deterministic and report `estimated_cost` as `0.0`.
