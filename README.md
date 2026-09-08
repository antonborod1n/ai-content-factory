# AI Content Factory

Automated B2B article production system. This repository implements **Stage 1**:
FastAPI + PostgreSQL generating articles through an AI provider, callable from n8n.

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

1. Copy the environment file and fill it in:

```bash
cp .env.example .env
```

Set your own `POSTGRES_PASSWORD`, keep `DATABASE_URL` in sync with it, and add
`OPENAI_API_KEY`. Compose refuses to start if `POSTGRES_PASSWORD` or
`DATABASE_URL` is missing — no credentials are hardcoded anywhere.

2. Start services (the app container applies Alembic migrations on start;
   Compose also starts **n8n** on port `5678`):

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

n8n UI: <http://localhost:5678> (create a local owner account on first visit).

## Local development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e ".[dev]"
```

For local pytest against Compose Postgres, set:

```bash
# Windows PowerShell — use the password from your own .env
$env:DATABASE_URL = "postgresql+asyncpg://acf:<your-password>@localhost:5432/acf"
```

Alternatively export `POSTGRES_PASSWORD` (plus optional `POSTGRES_USER` /
`POSTGRES_DB`) and `tests/conftest.py` builds the `localhost:5432` URL for you.

Tests truncate tables, so they never touch the application database: the suite
derives `<database>_test` (e.g. `acf_test`), creates it if missing and migrates
it on first use. Override with `TEST_DATABASE_URL` if you need another target.

```bash
make test
make lint
```

## API

`POST /api/v1/articles/generate`

```json
{
  "topic": "Как выбрать промышленный насос",
  "language": "ru",
  "audience": "Инженеры и закупщики",
  "keywords": ["промышленный насос"]
}
```

Only `topic` is required; `language`, `audience` and `keywords` default to
`ru`, `general` and `[]`. On success the response is `200` with `id`, `status`,
`title`, `meta_description`, `content_markdown` and a backend-recalculated
`word_count`.

Failures return a sanitized body (`detail`, `id`, `status: failed`) and the row
is stored with status `failed`:

| Status | Cause |
| --- | --- |
| 422 | Invalid request body |
| 502 | AI provider error or invalid AI response |
| 500 | Unexpected application error or misconfigured provider |

Interactive docs: <http://localhost:8000/docs>

## Topics from a file

Edit [`topics/topics.json`](topics/topics.json) using the full brief format
(`topic`, `word_count`, `primary_keywords`, `outline`, …). Start the API, then:

```bash
make generate-topics
```

Each object is sent as `POST /api/v1/articles/generate`. The user prompt in
`prompts/article_writer.md` substitutes every brief field (including the whole
plan as `{{brief_json}}`). Example: `topics/topics.example.json`.

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

## n8n workflow

n8n is a Compose service and a thin HTTP client: topic →
`POST /api/v1/articles/generate` → show result. Generation and secrets stay
in the backend. Default workflow URL uses the Compose hostname `app`.

Workflow export: [`n8n/workflows/stage1_generate_article.json`](n8n/workflows/stage1_generate_article.json).

Full Russian step-by-step (import, parameters, troubleshooting):
**[`n8n/README.md`](n8n/README.md)**.

## Project layout

```text
app/           FastAPI application (layered architecture)
tests/         Unit, API, and integration tests
prompts/       AI prompt templates
topics/        Topic lists for batch generation
scripts/       Manual smoke / batch clients (not part of the test suite)
n8n/workflows/ Exported workflow JSON (no secrets)
alembic/       Database migrations
```

## Documentation

- `GUIDE.md` — how to work with the project: files map, prompts, article flow
- `PROJECT.md` — product scope and Stage 1 requirements
- `ARCHITECTURE.md` — Stage 1 architecture blueprint

## Stage 1 status

Implemented:

- Project skeleton
- Docker Compose (`app` + `postgres` + `n8n`), migrations applied on container start
- `GET /health` with database connectivity check
- `articles` table, Alembic migration, `ArticleRepository`
- AI layer: `AIWriter` protocol, `OpenAIWriter`, `MockAIWriter`, prompt loading
- `ArticleService` (generation orchestration and status transitions)
- `POST /api/v1/articles/generate`
- n8n workflow export for manual generation
