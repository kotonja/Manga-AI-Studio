#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

API_URL="${API_URL:-http://localhost:8000}"
echo "Creating demo manga through $API_URL/demo/create-full-project"
curl -fsS -X POST "$API_URL/demo/create-full-project" \
  -H "Content-Type: application/json" \
  -d "{}"
echo
