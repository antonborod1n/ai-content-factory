# AI Content Factory

Automated B2B article production system. This repository currently implements the **Stage 1 skeleton**: FastAPI + PostgreSQL with a working health check.

## Stack

- Python 3.12+
- FastAPI / Uvicorn
- Pydantic 2
- SQLAlchemy 2.x + asyncpg
- Alembic
- pytest / pytest-asyncio / httpx
- Ruff
- Docker Compose

## Quick start

1. Copy environment file:

```bash
cp .env.example .env
```

2. Start services (the app container applies Alembic migrations on start):

```bash
docker compose up --build -d
```

3. Check health:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok","database":"ok"}
```

## Local development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e ".[dev]"
```

For local pytest against Compose Postgres, set:

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql+asyncpg://acf:acf_secret@localhost:5432/acf"
```

Or rely on `tests/conftest.py` defaults (`localhost:5432`).

```bash
make test
make lint
```

## AI provider

`OpenAIWriter` reads `OPENAI_API_KEY` and `OPENAI_MODEL` from the environment.
Set `OPENAI_BASE_URL` to use an OpenAI-compatible gateway instead of the
official API — for OpenRouter use `https://openrouter.ai/api/v1` together with a
prefixed model name such as `openai/gpt-4o-mini`.

The test suite never contacts a provider. To verify a live provider manually
(this spends API credits):

```bash
docker compose run --rm -e PYTHONPATH=/app -v ${PWD}/scripts:/app/scripts \
    --entrypoint python app scripts/smoke_openai.py
```

## Project layout

```text
app/           FastAPI application (layered architecture)
tests/         Unit, API, and integration tests
prompts/       AI prompt templates
scripts/       Manual smoke checks (not part of the test suite)
n8n/           Workflow exports (later)
alembic/       Database migrations
```

## Documentation

- `PROJECT.md` — product scope and Stage 1 requirements
- `ARCHITECTURE.md` — Stage 1 architecture blueprint

## Stage 1 status

Implemented:

- Project skeleton
- Docker Compose (`app` + `postgres`)
- `GET /health` with database connectivity check
- `articles` table, Alembic migration, `ArticleRepository`
- AI layer: `AIWriter` protocol, `OpenAIWriter`, `MockAIWriter`, prompt loading

Not yet implemented (next assignments):

- `ArticleService` (generation orchestration)
- `POST /api/v1/articles/generate`
- n8n workflow
