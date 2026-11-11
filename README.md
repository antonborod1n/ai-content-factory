# AI Content Factory

Automated B2B article production system. **Stage 1** generates articles through
an AI provider. **Stage 2** adds a knowledge base (documents → chunks →
pgvector → RAG context on generate). **Stage 3** adds competitor SERP research
and an improved outline before generate. **Stage 4** adds a multi-agent chain
(research → SEO → writer → fact-check → editor) behind `use_multi_agent`.
**Stage 5** replaces image placeholders and inserts internal links.
**Stage 6** adds a shorter Dzen version of the same article (`use_dzen`) and
optional quality checks: detectors, humanizer, and summary.
**Topic Discovery** builds a content plan from Google (Serper) and Yandex
(SerpAPI) snapshots and exports briefs into `topics.json`.

## Stack

- Python 3.12+
- FastAPI / Uvicorn
- Pydantic 2
- SQLAlchemy 2.x + asyncpg
- Alembic
- pgvector (Postgres image `pgvector/pgvector:pg16`)
- pytest / pytest-asyncio / httpx
- Ruff
- Docker Compose
- Vite + React + TypeScript + MUI (operator UI in `web/`)

## Quick start

Commands from the repo root. Skip step 1 if `.env` already exists.

1. Copy the environment file and fill it in (once):

```bash
cp .env.example .env
```

Set your own `POSTGRES_PASSWORD`, keep `DATABASE_URL` in sync with it, and add
`OPENAI_API_KEY`. Compose refuses to start if `POSTGRES_PASSWORD` or
`DATABASE_URL` is missing — no credentials are hardcoded anywhere.

**Upgrading from Stage 1:** Postgres image changed from `postgres:16-alpine`
to `pgvector/pgvector:pg16`. Compose uses a new volume
(`postgres_pgvector_data`), so the database starts empty. Article files in
`output/articles/` are unchanged. The old `postgres_data` volume can be
removed later if you no longer need those rows.

2. Start API, Postgres, and n8n (migrations run on app start):

```bash
docker compose up --build -d
```

3. Check health:

```bash
curl http://localhost:8000/health
```

On Windows PowerShell use `curl.exe`. Expected:

```json
{"status":"ok","database":"ok"}
```

4. Start the operator UI (leave this terminal open):

```bash
cd web
npm run dev
```

`npm install` in `web/` is only needed the first time or after dependency
changes. `npm run dev` from the repo root does not work — `package.json` is
in `web/`.

5. Open <http://127.0.0.1:15173>. See [GUIDE.md §2](GUIDE.md) (порядок
включения) and [§5.7](GUIDE.md).

n8n UI: <http://localhost:15678> (create a local owner account on first visit).
On Windows, Hyper-V may reserve 5432/5678/5173 — Compose and Vite use
15432/15678/15173 on the host instead.
Compose publishes API, Postgres, n8n, and the operator UI on `127.0.0.1`
only. There is no API auth yet — do not expose these ports beyond this
machine without a reverse proxy and authentication.
Stop containers: `docker compose down` from the repo root.

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
$env:DATABASE_URL = "postgresql+asyncpg://acf:<your-password>@localhost:15432/acf"
```

Alternatively export `POSTGRES_PASSWORD` (plus optional `POSTGRES_USER` /
`POSTGRES_DB`) and `tests/conftest.py` builds the `localhost:15432` URL for you.
Inside Docker (`docker compose run --rm --entrypoint pytest app -q`) the suite
uses the container `DATABASE_URL` instead.

Tests truncate tables, so they never touch the application database: the suite
derives `<database>_test` (e.g. `acf_test`), creates it if missing and migrates
it on first use. Override with `TEST_DATABASE_URL` if you need another target.

```bash
make test
make lint
```

## API

### Articles catalog (Stage 8a)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/articles` | List cards (`limit`, `offset`, `status`); no markdown |
| GET | `/api/v1/articles/{id}` | Full article (same fields as generate) |

### Generate article

`POST /api/v1/articles/generate`

```json
{
  "topic": "Как выбрать промышленный насос",
  "language": "ru",
  "audience": "Инженеры и закупщики",
  "keywords": ["промышленный насос"],
  "use_knowledge_base": true
}
```

Only `topic` is required. `use_knowledge_base` defaults to `true`: if the
knowledge base has ready chunks, nearest excerpts are added to the writer
prompt. Empty KB → same behaviour as Stage 1.

`use_competitor_research` defaults to `false`. Set it `true` or pass
`research_id` from `POST /api/v1/research` to write from a SERP-based outline
(see [GUIDE.md §5.2](GUIDE.md)).

`use_multi_agent` defaults to `false`. Set it `true` to run
Research → SEO → Writer → Fact Checker → Editor
(see [GUIDE.md §5.3](GUIDE.md)). The response then includes a `pipeline` trace.

`use_images` defaults to `false` (image APIs are billed separately).
`use_internal_links` defaults to `true` and is a no-op until other completed
articles exist (see [GUIDE.md §5.4](GUIDE.md)).

`use_dzen` defaults to `false`. Set it `true` for a shorter Dzen version of
the same article (cover + two in-body images when `use_images` is also true;
see [GUIDE.md §5.5](GUIDE.md)).

`use_detectors`, `use_humanizer`, and `use_summary` default to `false`.
They add heuristic AI-likeness scores, an optional rewrite, and a short
excerpt — not Copyscape / GPTZero (see [GUIDE.md §5.6](GUIDE.md)).

### Knowledge base

Пошагово (загрузка → поиск → generate, OpenRouter, что осталось):
**[GUIDE.md §5.1 и §11](GUIDE.md)**.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/documents` | Ingest JSON `{title?, content, filename?}` |
| POST | `/api/v1/documents/upload` | Ingest `.md` / `.txt` / `.pdf` |
| GET | `/api/v1/documents` | List documents |
| GET | `/api/v1/documents/{id}` | Document + extracted text |
| DELETE | `/api/v1/documents/{id}` | Delete document and chunks |
| POST | `/api/v1/documents/search` | `{query, top_k?}` nearest chunks |

Ingest uses the same `OPENAI_API_KEY` / `OPENAI_BASE_URL` for embeddings
(`OPENAI_EMBEDDING_MODEL`, default `text-embedding-3-small`, 1536 dimensions).
On OpenRouter use `openai/text-embedding-3-small`.

### Topic Discovery

Пошагово: **[GUIDE.md §5.2a](GUIDE.md)**. Needs `SERP_API_KEY` (Serper).
Yandex is optional (`YANDEX_SERP_API_KEY`).

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/discovery` | Seeds → SERP snapshots → article briefs |
| GET | `/api/v1/discovery` | List content plans |
| GET | `/api/v1/discovery/{id}` | One plan + briefs |
| POST | `/api/v1/discovery/{id}/export` | Append unique briefs to `topics.json` |

Then generate as usual: `make generate-topics`.

Switch without calling the APIs by hand (GUIDE [§5.2c](GUIDE.md)):

```bash
make topics-discovery SEEDS="матрасы Минск"
make topics-competitors COMPETITOR_FILES="topics/keys.csv"
make topics-competitors CONTENT_PLAN=topics/content-plan-example.com.json
```

### Competitor topic files

Пошагово: **[GUIDE.md §5.2b](GUIDE.md)**. Выгрузки конкурентов или JSON-план → briefs.
Does not call SERP. Discovery stays a separate entry (search seeds).

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/competitor-topics` | content-plan JSON → article briefs |
| POST | `/api/v1/competitor-topics/upload` | Same, from a `.json` file |
| POST | `/api/v1/competitor-topics/sources` | xlsx/csv/txt/json dumps → gap analysis → briefs |
| GET | `/api/v1/competitor-topics` | List competitor-gap plans |
| GET | `/api/v1/competitor-topics/{id}` | One plan + briefs |
| POST | `/api/v1/competitor-topics/{id}/export` | Append unique briefs to `topics.json` |

### Competitor research

Пошагово: **[GUIDE.md §5.2](GUIDE.md)**. Needs `SERP_API_KEY` (Serper).

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/research` | SERP → page structure → improved outline |
| GET | `/api/v1/research` | List research runs |
| GET | `/api/v1/research/{id}` | One run + competitors |

On successful generate the response is `200` with `id`, `status`, `title`,
`meta_description`, `content_markdown` and a backend-recalculated `word_count`.

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
(`topic`, `word_count`, `primary_keywords`, `outline`, …), or build the list
from Google/Yandex SERP via `POST /api/v1/discovery` (GUIDE §5.2a) or from a
competitor dumps via `POST /api/v1/competitor-topics/sources` or a ready
content-plan JSON via `POST /api/v1/competitor-topics` (GUIDE §5.2b).
Start the API, then:

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

- `GUIDE.md` — how to work with the project: files map, prompts, article flow, knowledge base, competitor research, multi-agent, images, internal links, Dzen, quality checks
- `PROJECT.md` — product scope and stage requirements
- `ARCHITECTURE.md` — Stage 1–6 architecture blueprint

## Stage status

Stage 1 (article generate), Stage 2 (knowledge base / RAG), Stage 3
(competitor research / SEO outline), Stage 4 (multi-agent pipeline),
Stage 5 (images + internal links) and Stage 6 (Dzen + quality checks) are implemented:

- Docker Compose (`app` + `postgres` with pgvector + `n8n`)
- `GET /health`, `POST /api/v1/articles/generate`, `GET /api/v1/articles`
- Operator UI: `web/` (Vite + React + MUI)
- Knowledge base: ingest, list, get, delete, search
- RAG: retrieved chunks are injected into writer prompts when the KB is not empty
- Research: `POST /api/v1/research`; generate with `use_competitor_research` or `research_id`
- Multi-agent: generate with `use_multi_agent`; `SeoAgent` / `FactChecker` / `Editor`
- Images: generate with `use_images`; `ImageProvider` replaces placeholders
- Internal links: default on; links to other completed articles with the same language
- Dzen: generate with `use_dzen`; shorter version from the main title, 3 image slots
- Quality: generate with `use_detectors` / `use_humanizer` / `use_summary`; heuristic scores, optional rewrite, short excerpt
- AI layer: `AIWriter` + `Embedder` + `CompetitorAnalyst` + Stage 4 agents + `ImageProvider` + `DzenWriter` + `AiDetector` / `Humanizer` / `Summarizer` (real + mock)
- Tests do not call a real chat, embedding, SERP, or image provider
