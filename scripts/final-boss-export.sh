#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/final-boss-demo.sh

ZIP_COUNT="$(find evidence/final_boss_demo/exports -name '*.zip' -type f | wc -l | tr -d ' ')"
PDF_COUNT="$(find evidence/final_boss_demo/exports -name '*.pdf' -type f | wc -l | tr -d ' ')"

if [ "$ZIP_COUNT" -lt 1 ]; then
  echo "Final Boss export check failed: no ZIP export file found." >&2
  exit 1
fi

if [ "$PDF_COUNT" -lt 1 ]; then
  echo "Final Boss export check failed: no PDF export file found." >&2
  exit 1
fi

echo "Final Boss export files verified in evidence/final_boss_demo/exports"
