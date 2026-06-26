#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

mkdir -p evidence

docker compose up -d postgres redis minio minio-init api

echo "Waiting for API health..."
i=0
until curl -fsS http://localhost:8000/health >/dev/null; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "API did not become healthy in time." >&2
    exit 1
  fi
  sleep 2
done

docker compose exec -T api python -m app.final_boss.run \
  --demo-only \
  --repo-root /app/repo \
  --output /app/evidence/final_boss_demo

echo "Final Boss demo evidence written to evidence/final_boss_demo"
