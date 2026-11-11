# AI Content Factory — Stage 1–6 Architecture

This document is the architecture blueprint derived from `PROJECT.md`.
**Stages 1–6 are implemented** (API, RAG, research, multi-agent, images,
internal links, Dzen, quality heuristics, topic discovery / competitor
topics, operator UI). Sections below keep the Stage 1 contracts as the
foundation; later stages plug into the same layers without breaking them.

Deferred without an explicit assignment: CMS publish, auth/billing,
Redis/workers/queues, third-party detector/humanizer SaaS, cloud
deployment, HTML scrape of google.com / yandex.ru.

---

## 1. Scope overview

### What Stage 1 established

A minimal, synchronous pipeline:

```text
n8n → FastAPI → ArticleService → AIWriter (OpenAI) → PostgreSQL
```

Input: article topic (+ optional language, audience, keywords).  
Output: structured article persisted in PostgreSQL and returned over HTTP.

### What Stages 2–6 added (current)

| Stage | Capability |
|-------|------------|
| 2 | Knowledge base: documents → chunks → embeddings → pgvector → optional RAG on generate |
| 3 | Competitor SERP research → improved outline; SEO fields strengthened from SERP |
| 4 | Multi-agent chain: research → SEO → writer → fact-check → editor (`use_multi_agent`) |
| 5 | Real images for placeholders; internal links between completed articles |
| 6 | Shorter Dzen version (`use_dzen`); own-chat detectors / humanizer / summary |
| Sibling | Topic Discovery (Google/Yandex SERP APIs) and competitor topic dumps → `topics.json` |
| UI | Operator UI in `web/` (Vite/React): projects, articles, topics, knowledge, generate, settings |

### Still deferred

CMS / review→publish, authentication, billing, Redis/Kafka/workers,
Kubernetes/cloud, GPTZero/Copyscape/Humanizer SaaS, agent frameworks
(LangChain etc.), HTML scrape of search engines.

### Non-negotiable rules (from PROJECT.md §16)

| # | Rule |
|---|------|
| 1 | API routes contain no business logic |
| 2 | API routes never call OpenAI directly |
| 3 | Repository contains no business logic |
| 4 | Repository never calls OpenAI |
| 5 | OpenAI is called only through the AI layer |
| 6 | ArticleService uses the `AIWriter` abstraction |
| 7 | n8n contains no article-generation business logic |
| 8 | Secrets live only in environment variables |
| 9 | New behavior requires tests |
| 10 | No features beyond the current assigned stage without a separate task |
| 11–12 | Prefer simple, maintainable design |

---

## 2. Exact Stage 1 architecture

### 2.1 Layered stack

```text
┌─────────────────────────────────────────────────────────┐
│  n8n (Compose service — Manual Trigger only)            │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP JSON
┌───────────────────────────▼─────────────────────────────┐
│  API Layer (FastAPI)                                    │
│  • routing • request/response schemas • DI wiring       │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Service Layer                                          │
│  ArticleService — orchestration & domain rules          │
└─────────────┬─────────────────────────────┬─────────────┘
              │                             │
┌─────────────▼─────────────┐ ┌─────────────▼─────────────┐
│  AI Layer                 │ │  Repository Layer         │
│  AIWriter (Protocol)      │ │  ArticleRepository        │
│  └─ OpenAIWriter          │ │  (SQLAlchemy only)        │
│  └─ MockAIWriter (tests)  │ └─────────────┬─────────────┘
└───────────────────────────┘               │
                                            ▼
                                   ┌────────────────┐
                                   │  PostgreSQL    │
                                   │  table: articles│
                                   └────────────────┘
```

### 2.2 Runtime model (Stage 1)

- **Synchronous request/response.** One HTTP call runs the full generation flow and returns the completed (or failed) outcome.
- **Status fields** (`pending` → `processing` → `completed` | `failed`) record lifecycle **within that single request**, enabling observability and future async workers without changing the data model.
- **No background workers, queues, or Redis** in Stage 1.
- **No authentication.** The API is assumed reachable only on a trusted network (local / Docker Compose). Auth is a later stage.

### 2.3 Dependency direction (must remain one-way)

```text
api → services → { ai, repositories } → database
```

- `api` may depend on schemas, services, and DI factories.
- `services` may depend on AI abstractions and repositories — **not** on FastAPI request objects.
- `ai` and `repositories` must **not** depend on `services` or `api`.
- Concrete OpenAI client code lives only under `ai/`.

### 2.4 Configuration

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy / async or sync PG connection string |
| `OPENAI_API_KEY` | OpenAI authentication |
| `OPENAI_MODEL` | Model name (default documented in `.env.example`) |
| `APP_ENV` | `local` / `test` / `production`-like flag for logging verbosity |
| `LOG_LEVEL` | Optional override: `DEBUG` / `INFO` / `WARNING` / `ERROR` (empty → from `APP_ENV`) |

Secrets never appear in code, prompts committed to git (except template placeholders), logs, n8n workflows, or API responses.

---

## 3. Directory structure

Proposed repository layout for Stage 1:

```text
ai-content-factory/
├── ARCHITECTURE.md
├── PROJECT.md
├── README.md                 # setup / run docs (implementation phase)
├── .env.example              # non-secret defaults + required var names
├── .gitignore
├── pyproject.toml            # or requirements.txt + optional requirements-dev.txt
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
│
├── prompts/
│   ├── article_writer.md     # whole article in one request
│   ├── article_meta.md       # title / meta description / slug
│   ├── article_section.md    # one outline section
│   └── article_expand.md     # grow a draft that came back too short
│
├── alembic/
│   ├── env.py
│   └── versions/
│       └── <revision>_create_articles.py
│
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app factory / lifespan
│   ├── config.py             # settings from env (Pydantic Settings)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py           # dependency injection providers
│   │   ├── router.py         # aggregate routers
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py     # GET /health
│   │       └── articles.py   # POST /api/v1/articles/generate
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── articles.py       # request / response / AI output DTOs
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── article_service.py
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── base.py           # AIWriter protocol / ABC
│   │   ├── openai_writer.py  # OpenAIWriter
│   │   ├── mock_writer.py    # MockAIWriter
│   │   ├── section_plan.py   # split a brief into per-section tasks
│   │   └── prompt_loader.py  # load prompts from prompts/
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── article_repository.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py           # DeclarativeBase
│   │   └── article.py        # SQLAlchemy Article model
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── session.py        # engine, session factory
│   │
│   └── core/
│       ├── __init__.py
│       ├── exceptions.py     # domain / app exceptions
│       └── word_count.py     # content_markdown → word_count
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_article_service.py
│   │   ├── test_ai_writer.py
│   │   ├── test_mock_ai_writer.py
│   │   ├── test_schemas.py
│   │   └── test_word_count.py
│   ├── api/
│   │   └── test_articles_api.py
│   └── integration/
│       └── test_article_flow.py
│
└── n8n/
    └── workflows/
        └── stage1_generate_article.json  # exportable workflow (no secrets)
```

### Notes on layout choices

- **`prompts/` at repo root** — matches PROJECT.md; loadable by path relative to the working directory or a configurable `PROMPTS_DIR`.
- **`app/core/`** — shared utilities (exceptions, word count) that are not layer-specific.
- **`n8n/workflows/`** — version-controlled workflow export; credentials stay in n8n’s own env/UI.
- Package name **`app`** keeps imports short (`from app.services...`).

---

## 4. Module responsibilities

### 4.1 `app.main`

- Create FastAPI application.
- Register routers and exception handlers.
- Manage lifespan (DB engine connect/dispose).
- **Does not** implement generation logic.

### 4.2 `app.config`

- Load and validate environment settings once.
- Expose typed settings object for DI.
- **Does not** contain secrets in defaults; only var names and non-secret defaults (e.g. model name, language).

### 4.3 `app.api` (routes + deps)

| Module | Responsibility |
|--------|----------------|
| `routes/health.py` | `GET /health` — process liveness + DB ping |
| `routes/articles.py` | `POST /api/v1/articles/generate` — parse body, call service, map result/errors to HTTP |
| `deps.py` | Wire DB session, `ArticleRepository`, `AIWriter`, `ArticleService` |
| `router.py` | Mount `/health` and `/api/v1/...` |

**Forbidden in API:** OpenAI calls, prompt assembly, word-count business rules beyond mapping, SQL.

### 4.4 `app.schemas`

- Pydantic v2 models for:
  - `ArticleGenerateRequest`
  - `ArticleGenerateResponse`
  - `AIArticleOutput` (structured AI payload)
  - `HealthResponse`
- Request defaults: `language="ru"`, `audience="general"`, `keywords=[]`.
- Validation: `topic` required, non-empty after strip.

### 4.5 `app.services.article_service`

Owns the Stage 1 generation **orchestration** (PROJECT.md §7):

1. Create article row (`status=pending`).
2. Set `status=processing`.
3. Call `AIWriter.generate(...)`.
4. Validate AI payload with `AIArticleOutput`.
5. Recalculate `word_count` from `content_markdown` (ignore AI’s word_count for persistence).
6. Persist title, meta, content, word_count; set `status=completed`.
7. On failure: set `status=failed`, store **safe** `error_message`, re-raise / map to API error.

**Forbidden in Service:** raw HTTP handling, raw SQL strings, direct OpenAI SDK usage.

### 4.6 `app.ai`

| Component | Responsibility |
|-----------|----------------|
| `AIWriter` | Protocol/ABC: input topic context → structured article fields |
| `OpenAIWriter` | Call OpenAI Chat Completions with structured JSON; one request per outline section, or a single request plus expansion passes when the brief has no outline |
| `MockAIWriter` | Deterministic fake output for unit/API/integration tests |
| `section_plan` | Turn a brief into per-section word budgets and placeholder numbering |
| `prompt_loader` | Read prompt files and substitute brief/section placeholders |

**Forbidden in AI layer:** persistence, status transitions, FastAPI types.

### 4.7 `app.repositories.article_repository`

- CRUD/persistence helpers for `Article`:
  - `create(...)`
  - `update(...)` / `save(...)`
  - `get_by_id(...)` (useful for tests and future GET endpoints)
- Maps between ORM entity and values passed by the service.
- **Forbidden:** AI calls, status-machine rules beyond applying fields the service sets.

### 4.8 `app.models` / `app.db`

- SQLAlchemy 2.x declarative model for `articles`.
- Engine + session factory (sync or async — **choose one consistently** for Stage 1; recommendation in §5.3).

### 4.9 `app.core`

- Safe exception types (`ArticleGenerationError`, `AIValidationError`, etc.).
- `word_count` helper: count words in markdown in a defined, tested way (whitespace-split of text is acceptable for MVP; document the rule).
- `configure_logging`: stdout handler for `app.*` so Compose logs show generation progress. Secrets and prompts must never be logged.

### 4.10 `prompts/`

- Human-editable prompt text only.
- Instruct the model to return JSON matching `AIArticleOutput`.
- No API keys or environment-specific secrets.

### 4.11 `alembic/`

- Schema migrations; Stage 1 migration creates `articles`.

### 4.12 `n8n/`

- Exported workflow JSON calling the backend HTTP API.
- Parameter mapping only; no generation logic.

### 4.13 `tests/`

- See §8.

---

## 5. Database model

### 5.1 Table: `articles`

| Column | Type | Constraints / notes |
|--------|------|---------------------|
| `id` | `UUID` | Primary key; generated in app or DB (`gen_random_uuid()`) |
| `topic` | `Text` | NOT NULL |
| `language` | `String(16)` | NOT NULL; default `ru` |
| `audience` | `Text` | NOT NULL; default `general` |
| `keywords` | `JSONB` | NOT NULL; default `[]` |
| `title` | `Text` | NULL until completed |
| `meta_description` | `Text` | NULL until completed |
| `content_markdown` | `Text` | NULL until completed |
| `word_count` | `Integer` | NULL until completed; backend-calculated |
| `status` | `String(32)` | NOT NULL; enum-like values below |
| `error_message` | `Text` | NULL; safe message only when `failed` |
| `created_at` | `timestamptz` | NOT NULL; set on insert |
| `updated_at` | `timestamptz` | NOT NULL; updated on every change |

### 5.2 Status values

```text
pending      → row created, generation not started
processing   → AI call in progress
completed    → content persisted successfully
failed       → generation or validation failed; error_message set
```

Stage 1 does not require a PostgreSQL `ENUM` type; a check constraint or application-level validation is enough. Prefer a Python `StrEnum` mirrored in the service/repository.

### 5.3 ORM / migration recommendations

- **SQLAlchemy 2.x** mapped class `Article`.
- **Alembic** for the initial migration (async `env.py`).
- **Decision (implemented): async SQLAlchemy + asyncpg** end to end — `AsyncSession`, async routes, async service and repository, async tests via `pytest-asyncio`. A sync stack with psycopg was considered and rejected to keep one consistent concurrency model across FastAPI, the AI client and the database.
- Index: primary key on `id`; optional index on `status` / `created_at` (nice-to-have, not required for MVP volume).

### 5.4 What is intentionally absent

No documents, chunks, embeddings, users, agents, or CMS tables. Adding them later must not require redesigning `articles` — only extension tables and new services.

---

## 6. API contract

Base URL (Docker Compose): `http://localhost:<APP_PORT>` (e.g. `8000`).

### 6.1 `GET /health`

**Purpose:** liveness + database connectivity.

**Success `200`:**

```json
{
  "status": "ok",
  "database": "ok"
}
```

**Degraded `503` (recommended):**

```json
{
  "status": "degraded",
  "database": "error"
}
```

`PROJECT.md` only shows the happy path. Architecture decision: if DB ping fails, return **503** with `database: "error"` and do not leak connection strings.

### 6.2 `POST /api/v1/articles/generate`

**Request body:**

```json
{
  "topic": "string (required, non-empty)",
  "language": "string (optional, default: ru)",
  "audience": "string (optional, default: general)",
  "keywords": ["string", "..."] 
}
```

| Field | Required | Default | Validation |
|-------|----------|---------|------------|
| `topic` | yes | — | non-empty after trim |
| `language` | no | `ru` | non-empty string if provided |
| `audience` | no | `general` | string |
| `keywords` | no | `[]` | list of strings |

**Success `200`:**

```json
{
  "id": "<uuid>",
  "status": "completed",
  "title": "...",
  "meta_description": "...",
  "content_markdown": "...",
  "word_count": 1800
}
```

**Client / validation error `422`:** missing `topic`, empty `topic`, wrong types (FastAPI/Pydantic).

**Generation failure `502` or `500` (recommendation):**

- Persist article with `status=failed` and safe `error_message`.
- Return JSON error body **without** secrets/stack traces, e.g.:

```json
{
  "detail": "Article generation failed",
  "id": "<uuid>",
  "status": "failed"
}
```

Architecture decision: use **502** when the upstream AI provider fails; **500** for unexpected internal errors; both must sanitize messages. Include `id` when a row was created so operators can inspect the DB.

**Not in Stage 1:** auth headers, webhooks.
`GET /api/v1/articles` and `GET /api/v1/articles/{id}` are Stage 8a F0
(operator catalog). Auth is still out of scope.

### 6.3 Error sanitization checklist

Never return or log in client-visible payloads:

- API keys, DB credentials, internal file paths, raw provider payloads containing secrets, full stack traces (log server-side only at appropriate level).

---

## 7. AIWriter abstraction

### 7.1 Interface

```text
AIWriter
  generate(request: ArticleWriteInput) -> AIArticleOutput
```

**`ArticleWriteInput`** (internal DTO; may live in `schemas` or `ai`):

```text
topic: str
language: str
audience: str
keywords: list[str]
```

**`AIArticleOutput`** (Pydantic — PROJECT.md §8):

```text
title: str
meta_description: str
content_markdown: str
word_count: int   # accepted from model but NOT trusted for persistence
```

### 7.2 Implementations

| Class | Used when | Behavior |
|-------|-----------|----------|
| `OpenAIWriter` | Runtime (Docker / local with key) | Loads `prompts/article_writer.md`, calls OpenAI, parses JSON, validates with Pydantic |
| `MockAIWriter` | pytest | Returns valid deterministic content derived from topic; can be configured to raise or return invalid shapes for negative tests |

### 7.3 DI rule

- `ArticleService` depends only on `AIWriter`.
- FastAPI `deps` selects `OpenAIWriter` vs `MockAIWriter` via settings / test overrides.
- Swapping providers later (Anthropic, local LLM) = new class implementing `AIWriter`, no service rewrite.

### 7.4 Prompt contract

- Prompt file instructs JSON-only output matching `AIArticleOutput`.
- Writer implementation is responsible for JSON extraction/parse errors → domain exception.
- Backend **recalculates** `word_count` from `content_markdown` after validation.

### 7.5 Future-ready (without implementing now)

- Same interface can later accept optional `context: str | list[Chunk]` for RAG.
- Multi-agent Stage 4 can introduce `ResearchAgent`, `EditorAgent`, etc., still feeding a final `AIWriter` or a higher-level orchestrator service — `ArticleService` today remains the single orchestrator.

---

## 8. Testing strategy

### 8.1 Principles

- **No real OpenAI key required** for CI or local default test runs.
- Prefer `MockAIWriter` everywhere except optional manual smoke tests.
- Use a real PostgreSQL when possible for integration (Docker Compose test DB or pytest fixture with ephemeral DB); alternatively Testcontainers / compose `postgres` service. SQLite is **discouraged** because of JSONB and parity with production.
- **Implemented:** the suite runs against a dedicated database on the same server (`<database>_test`, override via `TEST_DATABASE_URL`), created and migrated by `tests/db_setup.py`. Since fixtures truncate tables, the application database must never be the test target.

### 8.2 Unit tests

| Target | Assert |
|--------|--------|
| `ArticleService` | Status transitions; calls writer; persists completed fields; on AI error → failed + safe message; word_count from markdown |
| `OpenAIWriter` | Prompt loading; request shaping; parsing valid JSON; raising on invalid JSON (mock HTTP/OpenAI client) |
| `MockAIWriter` | Deterministic valid output; configurable failure modes |
| Pydantic schemas | Defaults; reject missing/empty topic; keywords default `[]` |
| `word_count` | Known markdown → expected count |

Unit tests mock repository and/or AI at boundaries as appropriate; service tests typically mock `AIWriter` + repository **or** use in-memory fakes.

### 8.3 API tests

Drive FastAPI via `httpx.AsyncClient` / `TestClient` with overridden deps:

| Case | Expectation |
|------|-------------|
| Successful generation | `200`, body matches contract, DB row `completed` |
| Missing `topic` | `422` |
| Empty `topic` | `422` |
| AI error | failed status persisted; sanitized error response |
| Invalid AI response | validation failure path; `failed`; sanitized error |

### 8.4 Integration tests

Full path:

```text
HTTP → FastAPI → ArticleService → MockAIWriter → PostgreSQL → Response
```

Assert end-to-end persistence and response fields. Still **no** real OpenAI.

### 8.5 Tooling

- `pytest` + `pytest-asyncio` (if async client/stack).
- `httpx` for API client.
- Ruff for lint in CI (implementation phase).
- Coverage target: not mandated by PROJECT.md; aim to cover all listed mandatory cases.

### 8.6 Out of scope for Stage 1 tests

- Load/performance tests.
- Real OpenAI billed calls in CI.
- n8n automated UI tests (manual verification of workflow is enough for DoD).

---

## 9. Docker architecture

### 9.1 Compose services (MVP)

```text
services:
  app        # FastAPI (uvicorn)
  postgres   # PostgreSQL 16 (or 15+)
  n8n        # thin HTTP orchestrator UI (no provider secrets)
```

Optional later: `redis`, `worker`.

### 9.2 `app` container

- Build from repo `Dockerfile` (Python 3.12+).
- Install dependencies; run migrations on startup **or** document a one-shot migrate command (recommendation: entrypoint runs `alembic upgrade head` then uvicorn).
- Env: `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, etc. via Compose `env_file: .env`.
- Expose port `8000` (host mapping in compose).
- Depends on `postgres` healthy.

### 9.3 `postgres` container

- Official Postgres image.
- Volume for data persistence.
- Credentials only via env (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) — not committed.
- Healthcheck so `app` starts after DB is ready.

### 9.4 Networking

- Internal Docker network: `app` connects to `postgres` hostname; `n8n` calls `http://app:8000/...`.
- Host access: `localhost:8000` → API; `localhost:15678` → n8n UI;
  `127.0.0.1:15432` → Postgres; `127.0.0.1:15173` → operator UI (Vite).
- **Do not** publish Postgres to the public internet in examples; publish only if needed for local tools (bind to localhost).

### 9.5 What Docker does not include in Stage 1

- Multi-replica app, K8s, reverse proxy, TLS termination.
- Redis / workers / cloud deployment.

---

## 10. How n8n communicates with the backend

### 10.1 Stage 1 workflow (PROJECT.md §10)

```text
Manual Trigger
  → Set Article Parameters   (topic, language, audience, keywords)
  → HTTP Request             (POST /api/v1/articles/generate)
  → IF Success
  → Result                   (show title / content / id)
```

### 10.2 Contract from n8n’s perspective

- **Method:** `POST`
- **URL:** `http://<host>:8000/api/v1/articles/generate`  
  - If n8n runs in this Compose project: `http://app:8000/...` (default in the exported workflow)  
  - If n8n runs on the host and API in Docker: `http://localhost:8000/...`  
  - If n8n runs in a separate Docker container: `http://host.docker.internal:8000/...` (Windows/macOS)
- **Headers:** `Content-Type: application/json`
- **Body:** JSON matching §6.2
- **Auth:** none in Stage 1
- **Timeout:** set generously (article generation may take tens of seconds)

### 10.3 Division of responsibility

| n8n | Backend |
|-----|---------|
| Trigger & parameter entry | Validation, persistence, AI, word count |
| HTTP call & branch on status code | All generation business logic |
| Display / pass-through of result | Sanitized errors |

n8n **must not**: craft prompts, call OpenAI, compute word counts, or write to Postgres.

### 10.4 Secrets

- `OPENAI_API_KEY` stays on the **backend** only.
- n8n workflow JSON in git must not embed API keys or DB URLs with passwords.

### 10.5 Relation to later n8n / CMS stages

Stage 1 already uses n8n as a thin HTTP client. **Stage 7** is richer automation (schedules, multi-step pipelines, HTML packaging) — not “introduce n8n for the first time.” **CMS hooks / publish** wait for **Stage 8**, after images and quality checks.

---

## 11. Supporting future RAG and multi-agent functionality

Stage 1 must remain simple while preserving extension points.

### 11.1 RAG (Stage 2) — implemented

```text
Documents → Parser → Chunking → Embeddings → Vector Search → context
                                                              ↓
                                         ArticleService (+ RAG context)
                                                              ↓
                                                         AIWriter
```

**What Stage 2 added:**

1. **`ArticleWriteInput.knowledge_context`** — optional string filled by `RagService` before `AIWriter.generate`.
2. **Modules:** `app/services/rag_service.py`, `app/services/document_service.py`, `app/repositories/document_repository.py`, `app/services/ai/embedder.py` + `OpenAIEmbedder` / `MockEmbedder`.
3. **Tables** `documents` and `chunks` (`chunks.embedding vector(1536)` via pgvector). Cosine distance search (`<=>`).
4. **`ArticleService`** retrieves context when `use_knowledge_base` is true and ready chunks exist; empty KB is a no-op.
5. **Prompts** keep a `{{knowledge_context}}` placeholder (empty KB → explicit “no extra sources” line).

Parser/chunking live in `app/core/` (no AI, no SQL). Embedding HTTP stays in the AI layer. Repositories run the vector SQL only.

**How to use it (ingest → search → generate):** `GUIDE.md` §5.1. Remaining product stages: `GUIDE.md` §11 / `PROJECT.md` §15.

**Not in Stage 2:** `article_sources` join table, async ingest workers.

### 11.1a Competitor research (Stage 3) — implemented

```text
Topic → SearchProvider (Serper) → PageFetcher → parse_html
                                              ↓
                            CompetitorAnalyst → improved outline
                                              ↓
                         ArticleService (optional) → AIWriter
```

**What Stage 3 added:**

1. **`POST /api/v1/research`** — persist competitors + outline.
2. **`ArticleWriteInput.use_competitor_research` / `research_id`** — generate uses the research outline; default off (Stage 1–2 generate unchanged).
3. **`{{competitor_context}}`** in writer/meta/section/expand prompts (SEO hints, not full page text).
4. **Modules:** `ResearchService`, `SearchProvider` / `SerperSearchProvider` / `MockSearchProvider`, `PageFetcher`, `CompetitorAnalyst`.
5. **Tables** `research_runs` and `research_competitors` (structure JSON, no raw HTML).
6. **Analyzed competitor URLs** — JSONB `articles.competitor_sources`, a
   trailing block in `article.md`, plus `competitors.txt`, `research.md`,
   `stage3_research.json` and `stage3_generate.json` in the article folder
   (not in `content_markdown` / HTML).

Parser lives in `app/core/page_structure.py` (including photos per heading).
URL/content article filters live in `app/core/competitor_filter.py`
(video, marketplaces, shop paths, short pages). Average photo counts per
outline section are planned in `app/core/section_images.py` and stored as
`section_image_placeholders`. Target `word_count`, tables/lists/FAQ flags and
infographic slots come from `app/core/competitor_brief.py` when research
attaches. SERP HTTP stays out of API routes and repositories.

**How to use it:** `GUIDE.md` §5.2.

**Not in Stage 3:** Google Search Console, CMS (Stage 8). Multi-agent
research/SEO/editor is Stage 4 (implemented in §11.2). Topic Discovery
(content plan from Google + Yandex) is a sibling module (§11.1b), not a
replacement for competitor research.

### 11.1b Topic Discovery — implemented

```text
Seeds → SerpSnapshotProvider (Google Serper + Yandex SerpAPI)
                 ↓
        normalize / dedupe candidates
                 ↓
        TopicPlanner → ArticleGenerateRequest briefs
                 ↓
        content_plans → export → topics.json
```

**What Topic Discovery added:**

1. **`POST /api/v1/discovery`** — persist a content plan of article briefs.
2. **`POST /api/v1/discovery/{id}/export`** — append unique topics to
   `TOPICS_FILE_PATH` (default `topics/topics.json`). Does not generate articles.
3. **Modules:** `DiscoveryService`, `SerpSnapshotProvider` /
   `SerperSnapshotProvider` / `YandexSerpApiProvider` / `MockSerpSnapshotProvider`,
   `TopicPlanner`.
4. **Tables** `content_plans` and `content_plan_topics` (brief JSONB, no SERP payload).
5. **`app/core/topic_candidates.py`** — deterministic normalize / Jaccard dedupe.
6. Snapshot HTTP stays in `app/services/discovery/`. Stage 3 `SearchProvider`
   is unchanged (organic Google + competitor URL filter only).

**How to use it:** `GUIDE.md` §5.2a.

**Not in this module:** HTML scrape of google.com / yandex.ru, Wordstat,
Search Console, recursive related-search expansion, auto-generate from the plan.

### 11.1c Competitor topic files — implemented

```text
xlsx / csv / txt / json dumps     content-plan-[domain].json
        │                                    │
        ▼                                    │
app/core/competitor_sources.py               │
        │                                    │
        ▼                                    │
ContentGapAnalyst (rewrite titles)           │
        │                                    │
        └────────────┬───────────────────────┘
                     ▼
        CompetitorTopicsService
                     ▼
        app/core/competitor_plan.py  (map → ArticleGenerateRequest)
                     ▼
        content_plans (source=competitor_gap) + content_plan_topics
                     ▼
        POST .../export → merge_topics() → topics.json
                     ▼
        existing generate / Stage 3 research
```

First substep of competitor analysis. Discovery (§11.1b) stays a sibling.
Stage 3 research stays the second substep.

**What this slice added:**

1. **`POST /api/v1/competitor-topics`** and **`/upload`** — persist briefs from
   a competitor-topics JSON plan. `GET` / `export` mirror Discovery.
2. **`POST /api/v1/competitor-topics/sources`** — parse xlsx/csv/txt/json dumps,
   cluster via `ContentGapAnalyst`, persist the same briefs. A single ready
   `content-plan-*.json` on this endpoint skips the analyst.
3. **`content_plans.source`** (`serp` | `competitor_gap`) and JSONB `context`.
   Topic rows store `source_competitors`, `is_gap`, `priority`, `category`
   beside the generate `brief`. Discovery list/get stay SERP-only.
4. **`app/core/competitor_plan.py`** — deterministic mapping, no outline /
   word_count / research_id (Stage 3 fills those).
5. **`app/core/competitor_sources.py`** — ZIP+XML xlsx and csv/txt/json hits
   (no openpyxl). Service/pagination URLs are dropped; Jaccard dedupe.
6. **`ContentGapAnalyst`** (`OpenAI*` runtime, `Mock*` in tests) +
   `prompts/competitor_gap.md`. Empty analyst output falls back to unique hits.
7. **`scripts/import_competitor_plan.py`** — JSON mapping without HTTP.
8. **`knowledge/<project>-brief.md`** — RAG project context (local, not in git).
   The topic table stays out of the knowledge base.

**How to use it:** `GUIDE.md` §5.2b.

**Not in this slice:** auto-generate from the plan, stuffing the 163-row
topic table into RAG.

### 11.2 Multi-agent (Stage 4) — implemented

```text
Research Agent → SEO Agent → Writer Agent → Fact Checker → Editor
```

**What Stage 4 added:**

1. **`use_multi_agent`** on `POST /api/v1/articles/generate` (default `false`).
   Stage 1–3 generate is unchanged when the flag is off.
2. **`PipelineService`** orchestrates the chain. `ArticleService` still owns
   status transitions and persistence; the API route still calls one service method.
3. **Research Agent** reuses `ResearchService` (auto-runs SERP research unless
   `research_id` is set). Missing SERP config → step skipped, pipeline continues.
4. **New AI ports:** `SeoAgent`, `FactChecker`, `Editor` under `app/services/ai/`
   (`OpenAI*` runtime, `Mock*` in tests).
5. **`articles.pipeline` JSONB** — compact step trace (names, status, fact-check
   verdict/issue_count). No article body, vectors, or secrets.
6. **Prompts:** `prompts/seo_brief.md`, `prompts/fact_check.md`,
   `prompts/article_editor.md`.

**How to use it:** `GUIDE.md` §5.3.

**Not in Stage 4:** LangChain / agent frameworks, extra fact-check loops,
detectors, CMS. Images and internal linking are Stage 5 (§11.3).

### 11.3 Images and internal links (Stage 5) — implemented

```text
Writer / Editor markdown
        │
        ├─ ImageService  → ImageProvider → images/*.png (opt-in use_images)
        └─ LinkingService → completed articles → [anchor](/slug)
```

**What Stage 5 added:**

1. **`use_images`** on generate (default `false`). Opt-in because image APIs
   are billed separately. `IMAGES_ENABLED` can disable the feature globally.
2. **`use_internal_links`** (default `true`). No-op when the catalog is empty.
   `INTERNAL_LINKS_ENABLED` / `INTERNAL_LINK_MAX` / `INTERNAL_LINK_PREFIX`.
3. **`ImageProvider`** in the AI layer (`OpenAIImageProvider` / `MockImageProvider`).
   `ImageService` orchestrates placeholder → file path. Failures skip that
   token only; missing API key skips the rest. Article generation still completes.
4. **`LinkingService`** scores other completed articles (same language, slug +
   title) by keyword/topic overlap and inserts markdown links in the body.
   Skips headings, existing links, images, and fenced code. Max 5. No extra LLM.
5. **JSONB** `articles.assets` and `articles.internal_links` — metadata only
   (paths, alts, slugs). Image bytes are written next to `article.md`, never
   stored in PostgreSQL or returned in the API.
6. **Prompt** `prompts/image_generate.md`. The article hero (`COVER_PLACEHOLDER`
   → `images/cover.png`) is generated from the **title**. In-body slots use
   the nearest heading plus a short excerpt. Editor prompt keeps
   `COVER_PLACEHOLDER`, `IMAGE_PLACEHOLDER_N` and
   `INFOGRAPHIC_PLACEHOLDER_N` for the backend to replace. With competitor
   research, photo counts per outline section come from
   `section_image_placeholders`.

Placeholder parse, section-image allocation, and link insertion live in
`app/core/` (no AI, no SQL).
Image HTTP stays in the AI layer. Repositories only list completed link targets.

**How to use it:** `GUIDE.md` §5.4.

**Not in Stage 5:** stock-photo search, CMS media libraries, detectors, Dzen
(Dzen is Stage 6, §11.4).

### 11.4 Dzen channel (Stage 6) — implemented

```text
Main article title + markdown
        │
        └─ DzenService → DzenWriter → shorter markdown
                         └─ optional ImageProvider (cover + 2 in-body)
```

**What this slice added:**

1. **`use_dzen`** on generate (default `false`). Extra chat call; opt-in.
2. **Same article, fewer characters** — written from the main **title**,
   compressing the main markdown. Target: `DZEN_TARGET_CHAR_COUNT` (default 4000).
3. **Three image slots:** `DZEN_COVER_PLACEHOLDER` (hero) and
   `DZEN_IMAGE_PLACEHOLDER_1` / `_2` in the body. Real files when `use_images`.
4. **`DzenWriter`** in the AI layer (`OpenAIDzenWriter` / `MockDzenWriter`).
   `DzenService` orchestrates write + images. Failure does not fail the main article.
5. **JSONB** `articles.dzen` — title, markdown, char_count, asset metadata.
   Bytes stay on disk (`dzen.md`, `dzen.html`, `images/dzen-*.png`).
6. **Prompt** `prompts/dzen_article.md`.

**How to use it:** `GUIDE.md` §5.5.

**Not in this slice:** CMS publish to Dzen. Quality checks are §11.5.

### 11.5 Quality checks (Stage 6) — implemented

```text
Main article (after images / links)
        │
        ├─ QualityService → AiDetector   (scores only)
        ├─ QualityService → Humanizer    (optional rewrite)
        ├─ QualityService → Summarizer   (short excerpt)
        └─ then DzenService (uses post-humanizer title + body)
```

**What this slice added:**

1. **`use_detectors` / `use_humanizer` / `use_summary`** on generate (all default
   `false`). Extra chat calls; opt-in.
2. **Detectors** estimate `ai_likelihood` and stylistic `uniqueness` (0–100).
   Verdict `pass` / `review` is computed in `app/core/quality.py`, not trusted
   from the model. This is **not** Copyscape, GPTZero, or a web plagiarism search.
3. **Humanizer** may rewrite paragraphs. It must keep facts, H2/tables/FAQ,
   markdown images `![...](...)`, and internal links `[text](/slug)`. Own chat
   via `Humanizer` — not a third-party Humanizer SaaS.
4. **Summary** is a short excerpt from the **final** markdown (after humanizer).
5. **`QualityService`** orchestrates the three steps. Failure of a step skips
   that step only; the main article still completes. Dzen runs after quality.
6. **JSONB** `articles.quality` — scores, humanizer flag, summary text.
   No full article body, no image bytes. Optional disk file `summary.md`.
7. **Prompts** `prompts/ai_detector.md`, `article_humanizer.md`, `article_summary.md`.

**How to use it:** `GUIDE.md` §5.6.

**Not in this slice:** GPTZero / Copyscape HTTP, Undetectable.ai, CMS.

### 11.6 What we deliberately do *not* pre-build

- Abstract “Agent framework” or plugin system.
- Event bus / Kafka.
- Premature microservice split.

Yagni for Stage 1: **one service, one writer port, one table** — with dependency inversion so Stage 2–6 add modules instead of rewriting the API skin.

---

## 12. End-to-end Stage 1 sequence

```text
Client (n8n)
  │  POST /api/v1/articles/generate { topic, ... }
  ▼
API (validate Pydantic)
  │  ArticleService.generate(...)
  ▼
Repository.create(status=pending)
  │
Repository.update(status=processing)
  │
AIWriter.generate(...)  →  AIArticleOutput (Pydantic)
  │
word_count(content_markdown)
  │
Repository.update(title, meta, content, word_count, status=completed)
  │
API 200 { id, status, title, meta_description, content_markdown, word_count }
```

Failure branch: update `failed` + safe `error_message` → sanitized HTTP error (with `id` if available).

---

## 13. Definition of Done mapping

| DoD item (PROJECT.md §17) | Architectural coverage |
|---------------------------|------------------------|
| Docker works | §9 compose `app` + `postgres` |
| PostgreSQL works | §5 model + Alembic |
| FastAPI works | §3–4 `app.main` / API layer |
| `GET /health` | §6.1 |
| `POST .../generate` | §6.2 + §12 |
| OpenAI generates article | `OpenAIWriter` §7 |
| AI response validated | `AIArticleOutput` Pydantic |
| Article saved | `ArticleRepository` + statuses |
| `status=completed` | Service flow §4.5 |
| API returns article | Response schema §6.2 |
| n8n calls API | §10 |
| Tests pass | §8 |

---

## 14. Assumptions

1. **Synchronous generation** is acceptable for MVP latency (no job queue).
2. **No API authentication** in Stage 1; deployment is local/trusted Docker network.
3. **Async SQLAlchemy + asyncpg** is used end-to-end (decided during implementation; see §5.3).
4. **Health check** returns 503 when DB is down (extension of PROJECT.md happy-path example).
5. **Failed generation** persists a row and returns an error response that may include `id` and `status=failed`.
6. **n8n** runs as a Compose service (`localhost:15678`); the exported workflow calls `http://app:8000/...` on the internal network.
7. **`word_count`** is whitespace-based on markdown source for MVP; exact algorithm documented in code/tests later.
8. **Stage 7 “n8n automation”** means schedules and HTML packaging, not first introduction of n8n. CMS publish is Stage 8.
9. **OpenAI structured output** may be achieved via JSON mode / schema or prompt-enforced JSON; implementation chooses the simplest reliable approach behind `OpenAIWriter`.
10. **Single `articles` table** is sufficient; no soft-delete or versioning in Stage 1.

---

## 15. Unclear or contradictory items in PROJECT.md

| Item | Notes |
|------|--------|
| **Stage 1 vs Stage 7 n8n** | Stage 1 DoD requires n8n to call the API; Stage 7 is titled “n8n automation.” Treated as: Stage 1 = thin manual HTTP workflow; Stage 7 = schedules / HTML packaging; CMS publish = Stage 8. |
| **Failed response shape** | PROJECT.md says save failed status and “return API error” but does not specify HTTP status code or whether `id` is returned. Architecture recommends sanitized error + optional `id` (§6.2). |
| **Health on DB failure** | Only success JSON is specified. Architecture recommends 503 + `database: "error"`. |
| **Sync vs async stack** | Not specified in `PROJECT.md`. Resolved during implementation: async SQLAlchemy + asyncpg end-to-end. |
| **OpenAI API style** | Chat Completions vs Responses API / structured outputs not specified. Hidden behind `OpenAIWriter`. |
| **Word count definition** | “Calculate from content_markdown” — tokenization rules unspecified (markdown syntax, CJK, etc.). MVP assumption: whitespace split. |
| **Idempotency / retries** | Not specified. Stage 1: each POST creates a new article row. |
| **GET article by id** | Model supports it; API not required for Stage 1. |
| **Default model / max tokens / temperature** | Not specified; belong in settings + `.env.example` at implementation time. |
| **Language of codebase/docs** | `PROJECT.md` is Russian; this architecture doc is English for implementation clarity. No conflict, but team should pick a convention for code comments/README. |

None of the above block Stage 1 design; they are decisions captured here for implementation to follow consistently.

---

## 16. Next step (out of scope for this document)

Stages 1–6 are in the codebase. Further work (Stage 7 n8n HTML packaging,
Stage 8 CMS publish, analytics, auth) starts only after an explicit
assignment and must keep the layering in §2–§7.
