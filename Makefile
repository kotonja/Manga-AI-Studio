.PHONY: dev test reset seed lint format check-env check-alpha-env final-check final-demo final-export

dev:
	sh scripts/dev.sh

test:
	sh scripts/test-all.sh

reset:
	sh scripts/reset-db.sh

seed:
	sh scripts/seed-demo.sh

lint:
	docker compose run --rm --no-deps api sh -lc "python -m compileall manga_api"
	docker compose run --rm --no-deps web sh -lc "pnpm install && pnpm --filter @manga-ai/web typecheck"

format:
	@echo "No formatter is configured yet. Keep edits formatted by TypeScript/Python conventions until Prettier/Ruff are added."

check-env:
	sh scripts/check-env.sh

check-alpha-env:
	python scripts/check-alpha-env.py

final-check:
	sh scripts/final-boss-check.sh

final-demo:
	sh scripts/final-boss-demo.sh

final-export:
	sh scripts/final-boss-export.sh
