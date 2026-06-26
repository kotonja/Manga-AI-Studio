#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

RESULTS="docs/FINAL_BOSS_RESULTS.md"
LOG_DIR="evidence/final_boss_demo/logs"
mkdir -p "$LOG_DIR" docs evidence

cat > "$RESULTS" <<EOF
# Final Boss Results

Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Command Results

| Gate | Status | Log |
| --- | --- | --- |
EOF

run_gate() {
  name="$1"
  shift
  log_file="$LOG_DIR/$name.log"
  set +e
  "$@" >"$log_file" 2>&1
  status="$?"
  set -e
  if [ "$status" -eq 0 ]; then
    printf '| %s | PASS | `%s` |\n' "$name" "$log_file" >> "$RESULTS"
  else
    printf '| %s | FAIL | `%s` |\n' "$name" "$log_file" >> "$RESULTS"
    echo "Final Boss gate failed: $name"
    echo "See $log_file"
    exit "$status"
  fi
}

run_gate compose-build docker compose build api web worker
run_gate compose-up docker compose up -d postgres redis minio minio-init api worker web
run_gate health-api curl -fsS http://localhost:8000/health
run_gate health-db curl -fsS http://localhost:8000/health/db
run_gate health-redis curl -fsS http://localhost:8000/health/redis
run_gate health-storage curl -fsS http://localhost:8000/health/storage
run_gate health-worker curl -fsS http://localhost:8000/health/worker
run_gate frontend-start curl -fsS http://localhost:3000/

run_gate migration-empty-drop docker compose exec -T postgres dropdb -U "${POSTGRES_USER:-manga}" --if-exists final_boss_migration_check
run_gate migration-empty-create docker compose exec -T postgres createdb -U "${POSTGRES_USER:-manga}" final_boss_migration_check
run_gate migration-empty-upgrade docker compose run --rm --no-deps \
  -e DATABASE_URL="postgresql+psycopg://${POSTGRES_USER:-manga}:${POSTGRES_PASSWORD:-manga}@postgres:5432/final_boss_migration_check" \
  api sh -lc "alembic upgrade head"

run_gate backend-tests docker compose run --rm --no-deps -e ENABLE_BACKGROUND_JOBS=false api sh -lc "python -m pip install -e /app/services/api[test] >/dev/null && pytest -q"
run_gate frontend-typecheck docker compose run --rm --no-deps web sh -lc "pnpm install >/dev/null && pnpm --filter @manga-ai/web typecheck"
run_gate frontend-build docker compose run --rm --no-deps web sh -lc "pnpm install >/dev/null && pnpm --filter @manga-ai/web build"
run_gate frontend-restart-after-build docker compose up -d --force-recreate web
run_gate wait-frontend-after-build sh -c 'i=0; until curl -fsS http://localhost:3000/ >/dev/null; do i=$((i + 1)); if [ "$i" -gt 60 ]; then exit 1; fi; sleep 2; done'
run_gate worker-import docker compose run --rm --no-deps worker sh -lc "python - <<'PY'
from manga_worker.tasks import director_generate_draft, mock_render_panel, render_panel
assert render_panel.name == 'manga_worker.render_panel'
assert mock_render_panel.name == 'manga_worker.mock_render_panel'
assert director_generate_draft.name == 'manga_worker.director_generate_draft'
print('worker import ok')
PY"

run_gate final-demo sh scripts/final-boss-demo.sh
run_gate final-export sh scripts/final-boss-export.sh
run_gate final-inventory docker compose exec -T api python -m app.final_boss.run --inventory-only --skip-results-doc --repo-root /app/repo --output /app/evidence/final_boss_demo

cat >> "$RESULTS" <<EOF

## Demo Evidence

- Evidence directory: \`evidence/final_boss_demo/\`
- Manifest: \`evidence/final_boss_demo/export_manifest.json\`
- Final pages: \`evidence/final_boss_demo/final_pages/\`
- Exports: \`evidence/final_boss_demo/exports/\`

## Notes

- Real OpenAI and ComfyUI calls were not required for this check.
- Mock providers are deterministic and are the expected local/test path.
- See \`docs/STUBS_AND_TODOS.md\` for documented provider stubs and placeholder areas.
EOF

echo "Final Boss check passed. Results written to $RESULTS"
