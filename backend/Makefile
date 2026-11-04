.PHONY: install db-up db-down migrate test test-db-down lint mypy format-check check

install:
	poetry install --with dev

db-up:
	docker compose --project-directory .. -f ../compose.yaml up -d db

db-down:
	docker compose --project-directory .. -f ../compose.yaml down

migrate: db-up
	poetry run alembic upgrade head

test:
	docker compose --project-directory .. -f ../compose.yaml --profile test run --build --rm test-runner

test-db-down:
	docker compose --project-directory .. -f ../compose.yaml --profile test stop test-db

lint:
	poetry run ruff check --config pyproject.toml worship_bot tests migrations ../bot_service

mypy:
	poetry run mypy

format-check:
	poetry run ruff format --check --config pyproject.toml worship_bot tests migrations ../bot_service

check: lint mypy format-check test