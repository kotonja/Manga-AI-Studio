#!/usr/bin/env sh
set -eu

echo "Checking Manga AI Studio local environment..."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker was not found on PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is not available." >&2
  exit 1
fi

if [ ! -f ".env" ]; then
  echo ".env is missing. Copy .env.example to .env for local overrides."
else
  echo ".env found."
fi

docker --version
docker compose version
echo "Environment check complete."
