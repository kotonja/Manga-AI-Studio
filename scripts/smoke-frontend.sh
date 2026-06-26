#!/usr/bin/env sh
set -eu

WEB_URL="${WEB_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000}"

echo "Checking dashboard..."
curl -fsS -o /dev/null "$WEB_URL/"

echo "Creating demo project for route smoke checks..."
DEMO_JSON="$(curl -fsS -X POST "$API_URL/demo/create-full-project" -H "Content-Type: application/json" -d "{}")"
PROJECT_ID="$(printf '%s' "$DEMO_JSON" | node -e "let data='';process.stdin.on('data',c=>data+=c);process.stdin.on('end',()=>console.log(JSON.parse(data).project.id))")"
PAGE_ID="$(printf '%s' "$DEMO_JSON" | node -e "let data='';process.stdin.on('data',c=>data+=c);process.stdin.on('end',()=>console.log(JSON.parse(data).page_ids[0]))")"

curl -fsS -o /dev/null "$WEB_URL/projects/$PROJECT_ID"
curl -fsS -o /dev/null "$WEB_URL/projects/$PROJECT_ID/director"
curl -fsS -o /dev/null "$WEB_URL/projects/$PROJECT_ID/story"
curl -fsS -o /dev/null "$WEB_URL/projects/$PROJECT_ID/pages/$PAGE_ID/studio"
curl -fsS -o /dev/null "$WEB_URL/projects/$PROJECT_ID/publishing"

echo "Frontend route smoke checks passed for project $PROJECT_ID."
