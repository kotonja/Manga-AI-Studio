#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

echo "This will remove local Docker volumes for Postgres, MinIO, and node caches."
docker compose down -v
docker compose up --build -d postgres redis minio minio-init api worker web
echo "Local stack reset. Web: http://localhost:3000 API: http://localhost:8000/docs"
