#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

./scripts/check-env.sh
docker compose up --build
