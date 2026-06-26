#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

docker compose build api web worker
docker compose run --rm --no-deps -e ENABLE_BACKGROUND_JOBS=false api sh -lc "python -m pip install -e /app/services/api[test] >/dev/null && pytest"
docker compose run --rm --no-deps web sh -lc "pnpm install && pnpm --filter @manga-ai/web typecheck && pnpm --filter @manga-ai/web build"
docker compose run --rm --no-deps worker sh -lc "python - <<'PY'
from manga_worker.tasks import director_generate_draft, render_panel
assert render_panel.name == 'manga_worker.render_panel'
assert director_generate_draft.name == 'manga_worker.director_generate_draft'
print('worker import ok')
PY"
