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

`n8n/workflows/stage1_generate_article.json` is an importable workflow:

```text
Manual Trigger -> Set Article Parameters -> Generate Article (HTTP) -> IF Success -> Result / Error Result
```

It only supplies `topic`, `language`, `audience`, `keywords` and displays the
response; all generation logic and the provider key stay in the backend.

Import it via **Workflows -> Import from File** in the n8n UI. If you do not
have n8n installed, run it next to the API:

```bash
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Then open <http://localhost:5678>, import the file, edit the topic in
**Set Article Parameters** and press **Execute Workflow**.

Adjust the URL in **Generate Article** to match where n8n runs:

| n8n runs | URL |
| --- | --- |
| On the host | `http://localhost:8000/api/v1/articles/generate` |
| In Docker (Windows/macOS) | `http://host.docker.internal:8000/api/v1/articles/generate` |
| In this Compose project | `http://app:8000/api/v1/articles/generate` |

## Project layout

```text
app/           FastAPI application (layered architecture)
tests/         Unit, API, and integration tests
prompts/       AI prompt templates
scripts/       Manual smoke checks (not part of the test suite)
n8n/workflows/ Exported workflow JSON (no secrets)
alembic/       Database migrations
```

## Documentation

- `PROJECT.md` — product scope and Stage 1 requirements
- `ARCHITECTURE.md` — Stage 1 architecture blueprint

## Stage 1 status

Implemented:

- Project skeleton
- Docker Compose (`app` + `postgres`), migrations applied on container start
- `GET /health` with database connectivity check
- `articles` table, Alembic migration, `ArticleRepository`
- AI layer: `AIWriter` protocol, `OpenAIWriter`, `MockAIWriter`, prompt loading
- `ArticleService` (generation orchestration and status transitions)
- `POST /api/v1/articles/generate`
- n8n workflow export for manual generation
