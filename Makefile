.PHONY: help install install-dev up down logs build test lint format shell migrate generate-topics import-competitor-plan topics-discovery topics-competitors web

help:
	@echo "Targets:"
	@echo "  install          Install runtime dependencies"
	@echo "  install-dev      Install runtime + dev dependencies"
	@echo "  up               Start Docker Compose (app + postgres + n8n)"
	@echo "  down             Stop Docker Compose"
	@echo "  logs             Tail Compose logs"
	@echo "  build            Rebuild Compose images"
	@echo "  migrate          Run Alembic migrations"
	@echo "  test             Run pytest"
	@echo "  lint             Run Ruff check"
	@echo "  format           Run Ruff format"
	@echo "  shell            Open a shell in the app container"
	@echo "  generate-topics  Generate articles from topics/topics.json"
	@echo "  import-competitor-plan  Map content-plan JSON → topics file"
	@echo "  topics-discovery Build topics.json from search seeds (Discovery)"
	@echo "  topics-competitors  Build topics.json from competitor files or plan"
	@echo "  web              Start the Stage 8a operator UI (Vite on :15173)"

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

# Tests create and migrate their own database, so no `migrate` dependency here.
test:
	docker compose run --rm --entrypoint pytest app -q

lint:
	docker compose run --rm --entrypoint ruff app check app tests scripts

format:
	docker compose run --rm --entrypoint ruff app format app tests

shell:
	docker compose exec app bash

# Reads topics/topics.json and POSTs each topic to the running API.
# Override file: make generate-topics TOPICS=topics/my_list.txt
TOPICS ?= topics/topics.json
generate-topics:
	docker compose run --rm \
		-e PYTHONPATH=/app \
		-e API_BASE_URL=http://app:8000 \
		-v "$(CURDIR)/scripts:/app/scripts" \
		-v "$(CURDIR)/topics:/app/topics" \
		--entrypoint python app scripts/generate_from_topics.py $(TOPICS)

# Map a content-plan JSON into a topics file (no generate).
# Example:
#   make import-competitor-plan PLAN=topics/content-plan-example.com.json
PLAN ?=
COMPETITOR_TOPICS ?= topics/topics.json
import-competitor-plan:
	@test -n "$(PLAN)" || (echo "Set PLAN=topics/content-plan-<domain>.json" && exit 1)
	docker compose run --rm --entrypoint python app scripts/import_competitor_plan.py "$(PLAN)" --topics-file "$(COMPETITOR_TOPICS)"

# Fill topics.json from Google/Yandex seeds. Does not generate articles.
# Example: make topics-discovery SEEDS="матрасы Минск"
SEEDS ?=
NICHE ?=
AUDIENCE ?= general
topics-discovery:
	docker compose run --rm \
		-e PYTHONPATH=/app \
		-e API_BASE_URL=http://app:8000 \
		-v "$(CURDIR)/scripts:/app/scripts" \
		-v "$(CURDIR)/topics:/app/topics" \
		--entrypoint python app scripts/build_topics.py \
		--mode discovery \
		--seed "$(SEEDS)" \
		--niche "$(NICHE)" \
		--audience "$(AUDIENCE)" \
		--topics-file "$(TOPICS)"

# Fill topics.json from competitor dumps or a ready content-plan JSON.
# Example:
#   make topics-competitors COMPETITOR_FILES="topics/keys.csv"
#   make topics-competitors CONTENT_PLAN=topics/content-plan-example.com.json
COMPETITOR_FILES ?=
CONTENT_PLAN ?=
DOMAIN ?=
topics-competitors:
	docker compose run --rm \
		-e PYTHONPATH=/app \
		-e API_BASE_URL=http://app:8000 \
		-v "$(CURDIR)/scripts:/app/scripts" \
		-v "$(CURDIR)/topics:/app/topics" \
		-v "$(CURDIR):/work:ro" \
		--entrypoint python app scripts/build_topics.py \
		--mode competitor \
		$(if $(CONTENT_PLAN),--plan /work/$(CONTENT_PLAN),) \
		$(foreach f,$(COMPETITOR_FILES),--files /work/$(f)) \
		--domain "$(DOMAIN)" \
		--niche "$(NICHE)" \
		--topics-file "$(TOPICS)"

web:
	cd web && npm install && npm run dev
