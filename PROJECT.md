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

Сейчас реализуется только **Stage 1 — MVP** (генерация статьи по brief).

Цель MVP:

```text
n8n / topics.json / API
↓
FastAPI
↓
ArticleService
↓
OpenAI
↓
PostgreSQL + файлы .md/.html
```

MVP принимает тему (и brief) и возвращает готовую статью, сохраняя её в PostgreSQL и в `output/articles/`.

### Целевой контент-пайплайн (все требования)

Ниже — полный список желаемого процесса. **Не всё входит в Stage 1**; колонка «Этап» показывает, когда пункт появляется.

| № | Что делаем | Простыми словами | Этап |
| --- | --- | --- | --- |
| 1 | Анализ конкурентов, ТОП статей по теме | Смотрим, кто уже в топе выдачи по теме | **Stage 3** |
| 2 | Анализ структуры конкурентов + улучшенная структура | Сколько текста, картинок, видео, какие фишки; собираем свой лучший план | **Stage 3** |
| 3 | Генерация статьи по структуре конкурентов | Пишем текст по плану, собранному после п. 1–2 | **Stage 3** (после анализа конкурентов) |
| 4 | Места для изображений и инфографики | В тексте помечаем, где будут картинки | **Stage 1** (плейсхолдеры) → реальные картинки в **Stage 6** |
| 5 | Title, description, URL | Заголовок, мета-описание, ЧПУ/slug для страницы | **Stage 1** (правила в промпте + поля в ответе) |
| 6 | Текст для Дзена | Короткая **100% уникальная** версия той же темы | **Stage 1.1 / Stage 9** |
| 7 | Перелинковка | Ссылки на другие страницы сайта | **Stage 6** |
| 8 | Проверка детекторами / Humanizer | AI-детектор, уникальность, «очеловечивание» текста | **Stage 9** |
| 9 | Оптимизация + краткое содержание | Доработка текста, summary | **Stage 9** |
| 10 | Блоки «Совет / Важно / Подсказка / Лайфхак / Рекомендация» | Вставки по месту, не все подряд | **Stage 1** (правила в промпте) |

**Stage 1 сейчас:** п. **4, 5, 10** (+ базовая генерация по `outline` из brief, без конкурентного анализа).  
**После Stage 3:** п. **1 → 2 → 3** (сначала конкуренты и структура, потом статья по ней).  
Пункты **6–9** — по плану следующих этапов.

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

Дополнительно в текущем стеке:

```text
n8n
```

n8n поднимается вместе с app и postgres (порт 5678) и обращается к API по
внутреннему имени `app:8000`. Секретов провайдера в нём нет.

Позже можно добавить:

```text
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

Архитектура должна позволять постепенно добавить полный пайплайн из §2.

### Stage 1 — MVP (сейчас)

Тема/brief → статья (MD/HTML) → БД + файлы.  
Плейсхолдеры картинок (п. 4), title / meta_description / url_slug (п. 5),
блоки «Совет/Важно/…» (п. 10). Базовая генерация по `outline` из brief
(без конкурентного анализа).

### Stage 1.1 — Мультиформат (рядом со Stage 1)

Отдельный короткий уникальный текст для Дзена (п. 6) и при необходимости другие каналы.

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

Research + SEO + конкуренты (п. 1–2, затем п. 3):

```text
Topic
↓
ТОП конкурентов по теме (п. 1)
↓
Разбор структуры: объём, H2, картинки, видео, фишки (п. 2)
↓
Улучшенный outline / SEO Brief
↓
Writer — статья по этой структуре (п. 3)
↓
Усиление Title / description / URL (п. 5)
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

Images + Internal Links (п. 4 → реальные картинки, п. 7 перелинковка).

### Stage 7

n8n automation (расписание, цепочки, в т.ч. HTML-доставка — см. `.cursor/rules/future-n8n-html-export.mdc`).

### Stage 8

Analytics.

### Stage 9

Content optimization:

* п. 8 — проверка детекторами AI / уникальности; опционально прогон через
  Humanizer (или аналог) для снижения «AI-отпечатка»;
* п. 9 — оптимизация текста и краткое содержание (summary);
* доработка формата для Дзена (п. 6), если не сделано в Stage 1.1.

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
