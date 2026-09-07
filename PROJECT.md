# AI Content Factory

## 1. Цель проекта

Создать автоматизированную систему для производства экспертных B2B-статей с использованием AI.

Конечный pipeline:

Topic Discovery
→ Research
→ Knowledge Base / RAG
→ Content Brief
→ AI Writer
→ Fact Check
→ Editing
→ Images
→ Internal Linking
→ CMS
→ Publication
→ Analytics
→ Optimization

Проект разрабатывается поэтапно.

---

## 2. Текущий этап

Сейчас реализуется только Stage 1 — MVP.

Цель MVP:

```text
n8n
↓
FastAPI
↓
ArticleService
↓
OpenAI
↓
PostgreSQL
```

MVP должен принимать тему статьи и возвращать готовую статью, сохраняя её в PostgreSQL.

---

## 3. Технологический стек MVP

Использовать:

* Python 3.12+
* FastAPI
* Pydantic 2
* SQLAlchemy 2.x
* PostgreSQL
* Alembic
* OpenAI API
* pytest
* pytest-asyncio
* httpx
* Ruff
* Docker
* Docker Compose
* Git
* GitHub
* n8n

Cursor используется как основной инструмент разработки.

---

## 4. Архитектура

Использовать layered architecture:

```text
API
↓
Services
↓
AI / Repositories
↓
PostgreSQL
```

Ответственность:

### API

Отвечает только за:

* HTTP;
* request validation;
* response;
* dependency injection.

API не содержит бизнес-логику.

### Services

Содержит бизнес-логику и orchestration.

Например:

```text
ArticleService
```

### AI Layer

Отвечает за взаимодействие с AI-провайдерами.

Использовать абстракцию:

```text
AIWriter
```

Первая реализация:

```text
OpenAIWriter
```

Для тестов:

```text
MockAIWriter
```

### Repository Layer

Отвечает только за работу с PostgreSQL.

Например:

```text
ArticleRepository
```

### Database

PostgreSQL.

---

## 5. MVP Article Model

Создать таблицу:

```text
articles
```

Поля:

```text
id
topic
language
audience
keywords
title
meta_description
content_markdown
word_count
status
error_message
created_at
updated_at
```

`id` должен быть UUID.

`keywords` хранить как JSONB.

Статусы:

```text
pending
processing
completed
failed
```

---

## 6. API

### Health

```http
GET /health
```

Пример ответа:

```json
{
  "status": "ok",
  "database": "ok"
}
```

### Generate Article

```http
POST /api/v1/articles/generate
```

Request:

```json
{
  "topic": "Как выбрать промышленный насос",
  "language": "ru",
  "audience": "Инженеры и закупщики",
  "keywords": [
    "промышленный насос",
    "как выбрать насос"
  ]
}
```

Обязательное поле:

```text
topic
```

Defaults:

```text
language = ru
audience = general
keywords = []
```

Response:

```json
{
  "id": "UUID",
  "status": "completed",
  "title": "...",
  "meta_description": "...",
  "content_markdown": "...",
  "word_count": 1800
}
```

---

## 7. Article Generation Flow

Использовать следующий flow:

```text
Request
↓
Validate request
↓
Create Article
status = pending
↓
status = processing
↓
AIWriter
↓
Validate AI response
↓
Calculate word_count
↓
Save article
↓
status = completed
↓
Return response
```

При ошибке:

```text
AI error
↓
status = failed
↓
save safe error message
↓
return API error
```

Не возвращать пользователю:

* API keys;
* stack traces;
* database credentials;
* внутренние пути;
* другие secrets.

---

## 8. AI Output

AI должен возвращать structured output:

```json
{
  "title": "...",
  "meta_description": "...",
  "content_markdown": "...",
  "word_count": 0
}
```

Результат обязательно валидируется через Pydantic.

`word_count` должен дополнительно рассчитываться backend из `content_markdown`.

---

## 9. Prompts

AI prompts не должны находиться непосредственно внутри Python-кода.

Хранить prompts в:

```text
prompts/
```

Первый prompt:

```text
prompts/article_writer.md
```

---

## 10. n8n

MVP workflow:

```text
Manual Trigger
↓
Set Article Parameters
↓
HTTP Request
↓
IF Success
↓
Result
```

n8n должен отправлять:

```text
topic
language
audience
keywords
```

n8n не должен содержать бизнес-логику генерации статьи.

---

## 11. Testing

Обязательно создать:

### Unit tests

Для:

* ArticleService;
* AIWriter;
* MockAIWriter;
* Pydantic schemas.

### API tests

Проверить:

* успешную генерацию;
* отсутствие topic;
* пустой topic;
* AI error;
* invalid AI response.

### Integration tests

Проверить:

```text
HTTP
↓
FastAPI
↓
Service
↓
MockAIWriter
↓
PostgreSQL
↓
Response
```

Тесты не должны требовать настоящий OpenAI API key.

---

## 12. Security

Все секреты должны храниться в environment variables.

Например:

```text
OPENAI_API_KEY
DATABASE_URL
```

`.env` нельзя коммитить в Git.

Никогда не помещать API keys:

* в Python code;
* в Git;
* в README;
* в n8n workflow;
* в logs;
* в API response.

---

## 13. Docker

MVP должен запускаться через Docker Compose.

Минимальные контейнеры:

```text
app
postgres
```

Позже можно добавить:

```text
n8n
redis
workers
```

Но в MVP они не обязательны.

---

## 14. Что НЕ реализовывать в Stage 1

Не добавлять:

* RAG;
* vector database;
* pgvector;
* PDF parsing;
* document processing;
* SEO automation;
* Google Search Console;
* Google Analytics;
* CMS;
* automatic publishing;
* image generation;
* image search;
* internal linking automation;
* multi-agent system;
* frontend;
* dashboard;
* authentication;
* billing;
* Redis;
* Kafka;
* Kubernetes;
* cloud deployment.

Эти функции будут реализовываться на следующих этапах.

---

## 15. Будущее развитие

Архитектура должна позволять постепенно добавить:

### Stage 2

Knowledge Base:

```text
Documents
↓
Parser
↓
Chunking
↓
Embeddings
↓
Vector Search
↓
RAG
```

### Stage 3

Research + SEO:

```text
Topic
↓
Research
↓
SERP
↓
Competitor Analysis
↓
SEO Brief
↓
Writer
```

### Stage 4

Multi-Agent:

```text
Research Agent
↓
SEO Agent
↓
Writer Agent
↓
Fact Checker
↓
Editor
```

### Stage 5

CMS:

```text
Article
↓
Review
↓
Approved
↓
CMS
↓
Published
```

### Stage 6

Images + Internal Links.

### Stage 7

n8n automation.

### Stage 8

Analytics.

### Stage 9

Content optimization.

---

## 16. Главные архитектурные правила

1. API routes не содержат бизнес-логику.
2. API routes не вызывают OpenAI напрямую.
3. Repository не содержит бизнес-логику.
4. Repository не вызывает OpenAI.
5. OpenAI вызывается только через AI layer.
6. ArticleService работает через AIWriter abstraction.
7. n8n не содержит бизнес-логику.
8. Secrets никогда не хранятся в source code.
9. Все новые функции должны иметь тесты.
10. Не добавлять функции следующих этапов без отдельного задания.
11. Архитектура должна оставаться простой.
12. Предпочитать понятный и поддерживаемый код сложным решениям.

---

## 17. Definition of Done для Stage 1

Stage 1 считается завершённым, когда:

```text
Docker работает
↓
PostgreSQL работает
↓
FastAPI работает
↓
GET /health работает
↓
POST /api/v1/articles/generate работает
↓
OpenAI генерирует статью
↓
AI response валидируется
↓
Article сохраняется в PostgreSQL
↓
status = completed
↓
API возвращает статью
↓
n8n вызывает API
↓
тесты проходят
```

После этого можно переходить к Stage 2 — Knowledge Base / RAG.
