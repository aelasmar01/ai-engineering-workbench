.PHONY: setup format lint typecheck test security check api dashboard dev

setup:
	uv sync --all-groups
	cd apps/dashboard && npm install

format:
	uv run ruff format src tests apps/api scripts
	uv run ruff check --fix src tests apps/api scripts
	cd apps/dashboard && npm run format

lint:
	uv run ruff check src tests apps/api scripts
	cd apps/dashboard && npm run lint

typecheck:
	uv run mypy src
	cd apps/dashboard && npm run typecheck

test:
	uv run pytest
	cd apps/dashboard && npm test

security:
	uv run bandit -q -r src scripts

check: lint typecheck test security
	cd apps/dashboard && npm run build

api:
	uv run uvicorn workbench.api.app:create_app --factory --host 127.0.0.1 --port 8787

dashboard:
	cd apps/dashboard && npm run dev -- --host 127.0.0.1

dev:
	$(MAKE) -j2 api dashboard
