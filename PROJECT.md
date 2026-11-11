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

**Stage 1 (MVP), Stage 2 (Knowledge Base / RAG), Stage 3 (конкуренты / SEO),
Stage 4 (мультиагенты), Stage 5 (картинки + перелинковка)
и Stage 6 (Дзен + детекторы / Humanizer / summary) реализованы.**
**Topic Discovery** (контент-план из Google + Яндекс → `topics.json`) — рядом
со Stage 3, не вместо research. Следующий крупный этап по пайплайну — **Stage 7**
(n8n HTML-упаковка) и далее CMS.
**Stage 8a F0–F5:** панель оператора до ревью. CMS — Stage 8.
**Несколько проектов** (P0–P5) сделаны: таблица `projects`, заголовок
`X-Project-Id` / `X-Project-Slug`, файлы `topics/{slug}/` и
`output/articles/{slug}/`, CLI `--project`, селектор в UI. Auth нет.
Переключатель Discovery / Competitor topics уже в CLI:
`scripts/build_topics.py --mode discovery|competitor`.
Как пользоваться: [GUIDE.md](GUIDE.md) §5.1–§5.6, §5.7 и §11.

Stage 1:

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

Stage 2 добавляет базу знаний:

```text
Документ (JSON или файл)
↓
Parser (md / txt / pdf)
↓
Chunking
↓
Embeddings (AI layer)
↓
PostgreSQL + pgvector
↓
при generate — retrieve → {{knowledge_context}} в промпт
```

Генерация статьи без документов в базе работает как в Stage 1.

### Целевой контент-пайплайн (все требования)

Ниже — полный список желаемого процесса. **Не всё входит в Stage 1**; колонка «Этап» показывает, когда пункт появляется.

| № | Что делаем | Простыми словами | Этап |
| --- | --- | --- | --- |
| 1 | Анализ конкурентов, ТОП статей по теме | Смотрим, кто уже в топе выдачи по теме | **Stage 3** |
| 2 | Анализ структуры конкурентов + улучшенная структура | Сколько текста, картинок, видео, какие фишки; собираем свой лучший план | **Stage 3** |
| 3 | Генерация статьи по структуре конкурентов | Пишем текст по плану, собранному после п. 1–2 | **Stage 3** (после анализа конкурентов) |
| 4 | Места для изображений и инфографики | В тексте помечаем, где будут картинки | **Stage 1** (плейсхолдеры) → реальные картинки в **Stage 5** |
| 5 | Title, description, URL | Заголовок, мета-описание, ЧПУ/slug для страницы | **Stage 1** (правила в промпте + поля в ответе) |
| 6 | Текст для Дзена | Короткая **100% уникальная** версия той же темы | **Stage 1.1 / Stage 6** |
| 7 | Перелинковка | Ссылки на другие страницы сайта | **Stage 5** |
| 8 | Проверка детекторами / Humanizer | AI-детектор, уникальность, «очеловечивание» текста | **Stage 6** (до публикации) |
| 9 | Оптимизация + краткое содержание | Доработка текста, summary | **Stage 6** (до CMS) → повтор по метрикам в **Stage 9** |
| 10 | Блоки «Совет / Важно / Подсказка / Лайфхак / Рекомендация» | Вставки по месту, не все подряд | **Stage 1** (правила в промпте) |

**Stage 1:** п. **4, 5, 10** (+ базовая генерация по `outline` из brief, без конкурентного анализа).  
**Stage 2 (сделано):** Knowledge Base / RAG — документы, чанки, эмбеддинги, векторный поиск, контекст в generate.  
**Stage 3 (сделано):** Research / SEO — ТОП конкурентов, разбор структуры, улучшенный outline, generate по нему.  
**Stage 4 (сделано):** мультиагенты — Research → SEO → Writer → Fact Checker → Editor (флаг `use_multi_agent`).  
**Stage 5 (сделано):** реальные картинки вместо плейсхолдеров (`use_images`) и перелинковка на другие completed-статьи (`use_internal_links`, по умолчанию вкл.).  
**Stage 6 Дзен (сделано):** короткая версия той же статьи по заголовку основной (`use_dzen`), 3 картинки (обложка + две в тексте).  
**Stage 6 качество (сделано):** эвристические детекторы, опциональный Humanizer и summary (`use_detectors` / `use_humanizer` / `use_summary`). Это не Copyscape / GPTZero и не сторонний Humanizer SaaS.  
Ревью / CMS / публикация — **не** следующий этап: сначала Stage 7 (n8n HTML), потом выкладка, потом аналитика.  
Пункты **6, 8, 9** закрыты в Stage 6 — по плану следующих этапов (§15).

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

n8n поднимается вместе с app и postgres (на хосте порт 15678) и обращается к API по
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

Архитектура должна позволять постепенно добавить полный пайплайн из §1 и §2.

Номера **этапов разработки** совпадают с порядком статьи, не с «сначала CMS»:

```text
1–6 сделано: generate → RAG → конкуренты → мультиагенты → картинки/ссылки → Дзен/качество
   CLI: переключатель Discovery / Competitor topics (scripts/build_topics.py)
   8a F0–F5: панель до ревью. CMS — этап 8.
   отложено: несколько проектов (изоляция KB / тем / статей) — см. ниже
7  n8n: расписание и HTML-упаковка
8a операторский UI (ревью статей; не CMS) — каркас есть, не CMS
8  ревью → CMS → публикация
9  аналитика и доработка по метрикам
```

### Stage 1 — MVP (сделано)

Тема/brief → статья (MD/HTML) → БД + файлы.  
Плейсхолдеры картинок (п. 4), title / meta_description / url_slug (п. 5),
блоки «Совет/Важно/…» (п. 10). Базовая генерация по `outline` из brief
(без конкурентного анализа).

### Stage 1.1 — Мультиформат (рядом со Stage 1)

Отдельный короткий уникальный текст для Дзена (п. 6) и при необходимости другие каналы.

### Stage 2 — Knowledge Base / RAG (сделано)

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

Ингест: `POST /api/v1/documents` (текст) и `POST /api/v1/documents/upload` (файл).  
Поиск: `POST /api/v1/documents/search`.  
При `POST /api/v1/articles/generate` бэкенд (если база не пуста и `use_knowledge_base=true`) подмешивает ближайшие чанки в промпт.

### Stage 3 — Research / SEO / конкуренты (сделано)

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

Ингест research: `POST /api/v1/research`.  
Generate: `"use_competitor_research": true` или `"research_id"`. Без флага generate как в Stage 1–2.  
URL проанализированных конкурентов пишутся в `article.md`, `competitors.txt`,
`research.md`, `stage3_research.json` и в `articles.competitor_sources`, не в тело статьи.
`stage3_generate.json` — JSON ответа generate в папке каждой статьи.  
В список конкурентов попадают только статьи: без YouTube/соцсетей/маркетплейсов/витрин, видимый текст ≥ 300 символов. По умолчанию оставляем 10 статей, для этого Serper отдаёт до 40 organic-ссылок.

### Topic Discovery (сделано)

Первый шаг пайплайна из §1 — **найти темы**, а не разобрать уже выбранную.

```text
seeds
↓
снимок Google (Serper: organic + PAA + related)
снимок Яндекс (SerpAPI; без ключа — только Google)
↓
дедуп кандидатов
↓
TopicPlanner → brief как в topics.json
↓
content_plans + export / append в topics.json
↓
generate-from-topics (как раньше)
```

`POST /api/v1/discovery`, `GET /api/v1/discovery/{id}`,
`POST /api/v1/discovery/{id}/export`. HTML поисковиков не парсим.
`SearchProvider` Stage 3 не расширяем.

Рядом — импорт тем из файлов конкурентов: `POST /api/v1/competitor-topics/sources`
(xlsx/csv/txt → ContentGapAnalyst) или готовый `content-plan-*.json`
(`POST /api/v1/competitor-topics` → briefs → export). Это первый подшаг анализа
конкурентов, не замена Discovery и не Stage 3 research. Контекст сайта — в RAG
(`knowledge/<проект>-brief.md`, хранится локально, не в git), таблица тем — в `topics/`.
Подробно: GUIDE §5.2b.

### Stage 4 (сделано)

Multi-Agent (ещё производство текста, не публикация):

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

Generate: `"use_multi_agent": true`. Без флага generate как в Stage 1–3.
Research Agent переиспользует Stage 3 (`ResearchService`). Новые AI-порты:
`SeoAgent`, `FactChecker`, `Editor`. Трасса шагов — `articles.pipeline`.

### Stage 5 (сделано)

Images + Internal Links (п. 4 → реальные картинки, п. 7 перелинковка).  
Статья становится «как на сайте», но ещё не уходит в CMS.

Generate: `"use_images": true` (opt-in, DALL·E дорогой) и `"use_internal_links": true`
(по умолчанию). Картинки — через `ImageProvider` (AI layer); перелинковка
детерминированная, без отдельного LLM. Сбой картинки не валит статью:
плейсхолдер остаётся. Метаданные — `articles.assets` / `articles.internal_links`
(без байтов файлов и без полного текста в логах).

### Stage 6 — Дзен + качество (сделано)

Короткая версия **той же статьи** для Дзена (п. 6): из заголовка основной,
меньше по символам, три картинки (главная + две в тексте).

Generate: `"use_dzen": true`. Реальные кадры Дзена — вместе с `"use_images": true`.
Сбой Дзена не валит основную статью. JSONB `articles.dzen` (без байтов картинок).
Файлы: `dzen.md` / `dzen.html` в папке статьи.

Качество перед CMS (п. 8–9), все флаги **выключены** по умолчанию (лишние LLM-вызовы):

* `"use_detectors": true` — эвристические оценки AI-likeness и «уникальности стиля»
  (0–100). Вердикт `pass` / `review` считает бэкенд. Это **не** Copyscape / GPTZero
  и не веб-поиск.
* `"use_humanizer": true` — переписывает абзацы живее, сохраняя факты, картинки
  `![...](...)` и внутренние ссылки `[текст](/slug)`. Свой чат через `Humanizer`,
  не Undetectable.ai и не другой SaaS.
* `"use_summary": true` — короткое содержание по **финальному** markdown
  (после humanizer). Файл `summary.md`.

Порядок: картинки/ссылки → детекторы → humanizer → summary → Дзен
(Дзен берёт уже «очеловеченный» текст). Сбой шага качества не валит статью.
JSONB `articles.quality` — оценки, флаг humanizer, текст summary; **без** тела статьи.

### Stage 7

n8n automation: расписание, цепочки, HTML-упаковка
(см. `.cursor/rules/future-n8n-html-export.mdc`).  
Доставка **в CMS** — на Stage 8, когда CMS уже есть. Секреты провайдера по-прежнему не в n8n.

### Stage 8

Ревью + CMS + публикация (после того как статья собрана):

```text
Article (с картинками, ссылками, проверками)
↓
Review
↓
Approved
↓
CMS
↓
Published
```

Не делать CMS раньше Stage 5–6: в канал уйдёт черновик без картинок и ссылок.

### Stage 9

Analytics + оптимизация **после** публикации (и при необходимости повторная выкладка).

### Переключатель источника тем (CLI, сделано)

n8n для этого **не** используется. Перед generate выбирается, **откуда брать темы**.

| Вход | Режим | Куда |
| --- | --- | --- |
| Только тематика / семена поиска | `discovery` | `POST /api/v1/discovery` → export |
| Файлы конкурентов, их темы, ключи (xlsx/csv/txt/json) | `competitor --files` | `POST /api/v1/competitor-topics/sources` → export |
| Готовый `content-plan-*.json` | `competitor --plan` | локальный `import_competitor_plan` (без HTTP) |

Команда: `scripts/build_topics.py --mode discovery|competitor` или
`make topics-discovery` / `make topics-competitors`. Скрипт **не** вызывает generate.

Режим обязателен. Нет seeds при `discovery` — ошибка. Нет файлов/плана при
`competitor` — ошибка. `--files` и `--plan` вместе, или `--seed` в competitor —
ошибка. В БД: `content_plans.source` = `serp` | `competitor_gap`.

### План: операторский UI (Stage 8a, до CMS)

**Локальная панель оператора**, не публичный сайт и не замена Stage 8 CMS.
**Сделано:** F0–F5 (каталог, темы, база, generate, ревью).
CMS-публикация — Stage 8, не этот UI.

Зачем: вход был curl / Swagger / Makefile. Выбор Discovery vs файлы конкурентов — решение человека; UI — место для того же переключателя после CLI.

Порядок относительно других этапов: **можно до Stage 7** (n8n не обязателен). CMS / публикация — только после ревью в UI. Auth / биллинг / Redis / воркеры — не в первой версии UI.

```text
F0  Дыры API для каталога статей          сделано
F1  Оболочка web/ (Vite + React + TS + MUI), только HTTP к FastAPI  сделано
F2  Переключатель источника тем (как CLI выше)  сделано
F3  База знаний (API уже есть)  сделано
F4  Generate + просмотр статьи / Дзен / quality  сделано
F5  Каталог и ревью (старт Stage 8; без выгрузки в CMS)  сделано
```

**F0 — бэкенд (сделано).**

- `GET /api/v1/articles` и `GET /api/v1/articles/{id}`
- CORS для локального dev (`APP_CORS_ORIGINS`)
- generate остаётся **синхронным**; UI держит длинный timeout (минуты), без Redis/очереди

**F1 — оболочка (сделано).** Каталог `web/`, отдельно от Python. Никакой бизнес-логики генерации, никаких ключей провайдера во фронте. Compose-сервис не обязателен: `make web` → Vite на `127.0.0.1:15173`, proxy на `:8000`.

**F2 — источник тем.** Явный переключатель на экране:

- «Только тематика» → форма seeds / niche → Discovery → список briefs
- «Файлы конкурентов» → загрузка xlsx/csv/txt/json → Competitor topics → briefs
- кнопка export в `topics.json` (существующие export-эндпоинты)

Не запускать оба режима за один клик.

**F3 — знания.** Upload / список / поиск / удаление — эндпоинты Stage 2 уже есть.

**F4 — генерация.** Форма brief + флаги (`use_competitor_research`, `use_multi_agent`, `use_images`, `use_dzen`, качество). Экран ожидания. Просмотр markdown, картинок, Дзена, оценок quality. Повтор картинок: уже есть `POST /articles/{id}/images`.

**F5 — ревью, ещё не CMS.** Список статей по статусу, карточка, вердикт оператора (нужны новые поля вроде `review_status` — отдельное задание). Публикация в CMS — Stage 8, не этот план.

Не в этом UI: GPTZero / Copyscape, HTML-скрейп поиска, биллинг, Kubernetes, аналитика Stage 9.
Переключатель проекта (когда появится таблица `projects`) — экран в шапке UI,
см. план «Несколько проектов» ниже.

### План: несколько проектов (изоляция клиентов)

Не внедрять без отдельного задания. Сейчас инстанс **один на всех**: одна база
знаний, один `topics/topics.json`, все статьи и research в общих таблицах.
Контекст goodnight.by живёт в RAG-файле, а не как сущность «проект».

Зачем: второй сайт (другая ниша, другая база знаний, свои темы) не должен
подмешивать чанки, внутренние ссылки и контент-план первого.

**Что изолировать на проект:**

- документы и чанки RAG (поиск и `knowledge_context` только внутри проекта);
- статьи, внутренние ссылки (`list_link_targets` того же проекта и языка);
- research-прогоны и content plans (Discovery / competitor_gap);
- рабочий файл тем: `topics/{slug}/topics.json` (не общий корень);
- папка вывода: `output/articles/{slug}/…`.

**Что остаётся общим** (не плодить без нужды):

- ключи OpenAI / Serper / Яндекс в `.env`;
- промпты в `prompts/`;
- один PostgreSQL, один процесс FastAPI.

Auth, биллинг, отдельная БД на клиента, Kubernetes — **не** этот план.

```text
P0  таблица projects + project_id на существующих сущностях (миграция)
P1  API CRUD проектов; текущий проект в запросе (заголовок или поле)
P2  generate / documents / research / discovery / competitor-topics
    читают и пишут только свой project_id
P3  файлы: topics/{slug}/topics.json и output/articles/{slug}/
P4  CLI: --project slug у build_topics.py и generate_from_topics.py
P5  UI (Stage 8a): выбор проекта в шапке до остальных экранов
```

**P0 — модель.** Таблица `projects`: `id`, `slug` (уникальный, для папок),
`name`, `domain` (опционально, сейчас это поле только в competitor context),
`language` по умолчанию, `created_at`. Внешний ключ `project_id` на
`articles`, `documents` (и каскадно чанки через документ), `research_runs`,
`content_plans`. Миграция создаёт проект `default` и проставляет его всем
уже существующим строкам — пустая база после смены не нужна.

**P1 — API.** `POST/GET /api/v1/projects`, `GET /api/v1/projects/{id}`.
Рабочие эндпоинты принимают `project_id` (тело, query или заголовок
`X-Project-Id`). Без него — 422, не «все проекты сразу». Routes по-прежнему
без SQL и без OpenAI: скоуп в сервисах, фильтр в репозиториях.

**P2 — скоуп операций.** RAG `search` / `context_for_article` — только чанки
документов этого проекта. Перелинковка — только completed-статьи этого
проекта. Discovery export пишет в `topics/{slug}/topics.json`. Competitor
`--plan` и `--files` не пересекают проекты. Смена проекта посреди generate
запрещена.

**P3 — файлы.** Учебные образцы остаются в `knowledge/` и
`topics/topics.example.*` (не привязаны к клиенту). Боевые темы — не в корне
`topics/topics.json`, а в `topics/{slug}/`. `TOPICS_FILE_PATH` в settings —
шаблон или значение по умолчанию для `default`.

**P4 — CLI.** Явный `--project goodnight-by` (или env `ACF_PROJECT`). Без
флага — проект `default`, чтобы старые команды не сломались.

**P5 — UI.** После F1 оболочки: селектор проекта. F2–F5 работают в выбранном
проекте. Создать проект = имя + slug, затем база знаний и темы с нуля.

Не делать в первой версии: шаринг документов между проектами, мультиаккаунт,
разные API-ключи на проект, удаление проекта без явного каскада в задании.

---

## 16. Главные архитектурные правила

1. API routes не содержат бизнес-логику.
2. API routes не вызывают OpenAI напрямую.
3. Repository не содержит бизнес-логику.
4. Repository не вызывает OpenAI.
5. OpenAI вызывается только через AI layer.
6. ArticleService работает через AIWriter abstraction; эмбеддинги — через Embedder.
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

---

## 18. Definition of Done для Stage 2

Stage 2 считается завершённым, когда:

```text
PostgreSQL с расширением vector (pgvector)
↓
таблицы documents и chunks
↓
POST /api/v1/documents принимает текст, парсит, режет на чанки, эмбеддит
↓
POST /api/v1/documents/upload принимает .md / .txt / .pdf
↓
POST /api/v1/documents/search возвращает ближайшие чанки
↓
POST /api/v1/articles/generate подмешивает RAG-контекст, если база не пуста
↓
пустая база знаний не ломает генерацию (поведение Stage 1)
↓
эмбеддинги только через AI layer (Embedder), тесты на MockEmbedder
↓
тесты проходят
```

После этого можно переходить к Stage 3 — Research / SEO / конкуренты.

---

## 19. Definition of Done для Stage 3

Stage 3 считается завершённым, когда:

```text
SERP-поиск ТОП конкурентов через SearchProvider (не из API routes)
↓
загрузка страниц + разбор структуры (H2, объём, картинки, видео, списки)
↓
POST /api/v1/research сохраняет профили и улучшенный outline
↓
POST /api/v1/articles/generate с use_competitor_research или research_id
  пишет статью по этому outline
↓
без флага generate работает как Stage 1–2
↓
outline планируется через CompetitorAnalyst (AI layer), тесты на моках
↓
тесты проходят
```

После этого можно переходить к Stage 4 — Multi-Agent.

---

## 20. Definition of Done для Stage 4

Stage 4 считается завершённым, когда:

```text
POST /api/v1/articles/generate с use_multi_agent=true
  запускает Research → SEO → Writer → Fact Checker → Editor
↓
без флага generate работает как Stage 1–3
↓
SEO / fact-check / editor только через AI layer (моки в тестах)
↓
трасса шагов сохраняется в articles.pipeline (без тела статьи)
↓
тесты проходят
```

После этого можно переходить к Stage 5 — картинки и перелинковка.

---

## 21. Definition of Done для Stage 5

Stage 5 считается завершённым, когда:

```text
POST /api/v1/articles/generate с use_images=true
  заменяет IMAGE_/INFOGRAPHIC_PLACEHOLDER на images/*.png
↓
файлы картинок пишутся рядом с article.md (байты не в БД и не в API)
↓
сбой одного кадра не валит статью (плейсхолдер остаётся)
↓
use_internal_links (по умолчанию true) вставляет ссылки
  на другие completed-статьи того же языка
↓
без флагов generate работает как Stage 1–4
↓
картинки только через AI layer (ImageProvider), тесты на MockImageProvider
↓
перелинковка без LLM: overlap ключей/темы, не в заголовках/ссылках/картинках
↓
тесты проходят
```

После этого можно переходить к Stage 6 — Дзен и качество.

---

## 22. Definition of Done для Stage 6 (Дзен)

Дзен-версия считается готовой, когда:

```text
POST /api/v1/articles/generate с use_dzen=true
  пишет короткую версию из заголовка основной статьи
↓
объём меньше основной (цель — DZEN_TARGET_CHAR_COUNT символов)
↓
в тексте ровно 3 слота картинок: обложка + две в теле
↓
use_images=true заменяет их на images/dzen-cover.png и dzen-1/2.png
↓
сбой Дзена не валит основную статью
↓
метаданные в articles.dzen; файлы dzen.md / dzen.html
↓
чат только через DzenWriter (моки в тестах)
↓
тесты проходят
```

Детекторы, Humanizer и summary закрыты в §23.

---

## 23. Definition of Done для Stage 6 (качество)

Качество считается готовым, когда:

```text
POST /api/v1/articles/generate с use_detectors / use_humanizer / use_summary
  (все default false)
↓
детекторы только считают баллы; вердикт pass/review на бэкенде
↓
humanizer может переписать markdown, не ломая картинки и внутренние ссылки
↓
summary берётся из финального текста (после humanizer)
↓
сбой шага качества не валит основную статью
↓
метаданные в articles.quality (без тела статьи); опционально summary.md
↓
чат только через AiDetector / Humanizer / Summarizer (моки в тестах)
↓
это не Copyscape / GPTZero / Humanizer SaaS
↓
тесты проходят
```

CMS и публикация в этот DoD **не** входят — Stage 8.

