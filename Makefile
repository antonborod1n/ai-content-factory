.PHONY: help install install-dev up down logs build test lint format shell migrate

help:
	@echo "Targets:"
	@echo "  install      Install runtime dependencies"
	@echo "  install-dev  Install runtime + dev dependencies"
	@echo "  up           Start Docker Compose (app + postgres)"
	@echo "  down         Stop Docker Compose"
	@echo "  logs         Tail Compose logs"
	@echo "  build        Rebuild Compose images"
	@echo "  migrate      Run Alembic migrations"
	@echo "  test         Run pytest"
	@echo "  lint         Run Ruff check"
	@echo "  format       Run Ruff format"
	@echo "  shell        Open a shell in the app container"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

migrate:
	docker compose run --rm --entrypoint alembic app upgrade head

# Integration tests need the schema; the app container migrates on start, but
# `run --entrypoint pytest` bypasses that, so migrate explicitly first.
test: migrate
	docker compose run --rm --entrypoint pytest app -q

lint:
	docker compose run --rm --entrypoint ruff app check app tests

format:
	docker compose run --rm --entrypoint ruff app format app tests

shell:
	docker compose exec app bash
