UV := uv
PNPM := corepack pnpm

.PHONY: bootstrap generate check-generated dev dev-api dev-web test lint format-check typecheck build check

bootstrap:
	$(UV) sync --all-packages --all-groups --locked
	$(PNPM) install --frozen-lockfile
	@test -f .env || cp .env.example .env

generate:
	$(UV) run python -m scripts.export_openapi
	$(PNPM) --dir apps/web run generate:api

check-generated:
	$(UV) run python -m scripts.export_openapi --check
	@temporary_file="$$(mktemp)"; \
	trap 'rm -f "$$temporary_file"' EXIT; \
	$(PNPM) --dir apps/web exec openapi-typescript openapi.json -o "$$temporary_file"; \
	cmp apps/web/src/api/schema.d.ts "$$temporary_file"

dev:
	@set -eu; \
	$(MAKE) dev-api & api_pid=$$!; \
	$(MAKE) dev-web & web_pid=$$!; \
	trap 'kill $$api_pid $$web_pid 2>/dev/null || true' INT TERM EXIT; \
	wait $$api_pid $$web_pid

dev-api:
	$(UV) run uvicorn tribuna.adapters.api.main:app \
		--host 127.0.0.1 --port 8000 --reload --reload-dir apps/backend/src \
		--no-access-log

dev-web:
	$(PNPM) --dir apps/web run dev

test:
	$(UV) run pytest
	$(PNPM) --dir apps/web run test

lint:
	$(UV) run ruff check .
	$(PNPM) --dir apps/web run lint

format-check:
	$(UV) run ruff format --check .
	$(PNPM) --dir apps/web run format:check

typecheck:
	$(UV) run mypy apps/backend/src apps/backend/tests scripts/export_openapi.py
	$(PNPM) --dir apps/web run typecheck

build:
	$(PNPM) --dir apps/web run build

check: check-generated lint format-check typecheck test build
