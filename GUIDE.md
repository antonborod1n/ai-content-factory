# Инструкция по работе с AI Content Factory (Stage 1–6)

Практическое руководство: что где лежит, куда писать промпты, куда попадает готовая статья, как пользоваться базой знаний, откуда собираются конкуренты, как включить мультиагентов, картинки, перелинковку, Дзен, детекторы / Humanizer / summary, и что ещё осталось.

Связанные документы:

- [PROJECT.md](PROJECT.md) — требования Stage 1–6
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура
- [README.md](README.md) — быстрый старт

База знаний: [§5.1](#51-база-знаний-stage-2--как-пользоваться).
Конкуренты / SEO: [§5.2](#52-конкуренты--seo-stage-3--как-это-работает).
Контент-план из выдачи: [§5.2a](#52a-контент-план-topic-discovery).
Темы из файлов конкурентов: [§5.2b](#52b-темы-из-файлов-конкурентов).
Как переключать режимы тем: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics).
Мультиагенты: [§5.3](#53-мультиагенты-stage-4--как-это-работает).
Картинки и перелинковка: [§5.4](#54-картинки-и-перелинковка-stage-5).
Дзен: [§5.5](#55-дзен-stage-6).
Детекторы, Humanizer, summary: [§5.6](#56-детекторы-humanizer-и-summary-stage-6).
Что осталось: [§11](#11-что-осталось-сделать).
План UI: [§11.Д](#д-план-операторского-ui).
Как запустить панель: [§5.7](#57-панель-оператора-stage-8a).
Несколько проектов: [§11.Е](#е-план-несколько-проектов).

---

## 1. Что делает проект

Система по запросу генерирует B2B-статью через AI-провайдер, сохраняет её в PostgreSQL и возвращает JSON.

```text
Клиент (curl / n8n / Swagger)
        │
        ▼
FastAPI  POST /api/v1/articles/generate
        │
        ▼
ArticleService  (оркестрация статусов)
        │
        ▼
AIWriter (OpenAI / OpenRouter)
        │
        ▼
PostgreSQL  таблица articles
        │
        ▼
HTTP-ответ с готовой статьёй
```

---

## 2. Порядок включения

Команды из корня репозитория (`ai-content-factory`). Если `.env` уже есть,
шаг 1 пропускается.

1. Один раз скопировать и заполнить `.env` (если файла ещё нет):

```powershell
cp .env.example .env
```

Нужны `POSTGRES_PASSWORD` (тот же пароль внутри `DATABASE_URL`) и `OPENAI_API_KEY`.

2. Поднять API, Postgres и n8n:

```powershell
docker compose up --build -d
```

3. Проверить API:

```powershell
curl.exe http://localhost:8000/health
```

Ожидается `{"status":"ok","database":"ok"}`.

4. Запустить панель (окно терминала не закрывать):

```powershell
cd web
npm run dev
```

`npm install` в `web/` нужен только в первый раз или после смены зависимостей.
Из корня `npm run dev` не работает: `package.json` лежит в `web/`.

5. Открыть панель: <http://127.0.0.1:15173>.

Остановка контейнеров: `docker compose down` из корня репозитория.

Swagger UI: <http://localhost:8000/docs>  
n8n UI: <http://localhost:15678> (инструкция: [`n8n/README.md`](n8n/README.md))

На Windows Hyper-V иногда резервирует порты `5432`, `5678` и `5173`.
Поэтому с хоста: Postgres `127.0.0.1:15432`, n8n `15678`, Vite `15173`.
Внутри Docker сервисы по-прежнему ходят на стандартные порты контейнеров.

Полезные команды (`Makefile`):

| Команда | Что делает |
| --- | --- |
| `make up` | Поднять app + postgres + n8n |
| `make down` | Остановить |
| `make logs` | Логи контейнеров |
| `make test` | pytest |
| `make lint` | Ruff |
| `make migrate` | Alembic upgrade |
| `make web` | Vite + React + MUI на :15173 |

---

## 3. Где задаются промпты

Промпты **не** хранятся в Python-коде. Они лежат в каталоге `prompts/`.

| Файл | Роль |
| --- | --- |
| [`prompts/article_writer_system.md`](prompts/article_writer_system.md) | System prompt: «отвечай только валидным JSON» |
| [`prompts/article_writer.md`](prompts/article_writer.md) | Статья одним запросом (когда в brief нет `outline`) |
| [`prompts/article_meta.md`](prompts/article_meta.md) | `title`, `meta_description`, `url_slug` для посекционного режима |
| [`prompts/article_section.md`](prompts/article_section.md) | Один раздел статьи по плану |
| [`prompts/article_expand.md`](prompts/article_expand.md) | Добор объёма, если черновик вышел слишком коротким |
| [`prompts/competitor_outline.md`](prompts/competitor_outline.md) | Улучшенный outline по структуре конкурентов |
| [`prompts/competitor_gap.md`](prompts/competitor_gap.md) | Контент-план из выгрузок URL/ключей конкурентов |
| [`prompts/seo_brief.md`](prompts/seo_brief.md) | SEO-агент: ключи, intent, title/meta/slug, outline |
| [`prompts/fact_check.md`](prompts/fact_check.md) | Фактчекер: вердикт и список замечаний |
| [`prompts/article_editor.md`](prompts/article_editor.md) | Редактор: вычитка черновика после фактчека |

### Два режима генерации

| Когда | Что происходит | Типичный объём |
| --- | --- | --- |
| В brief есть `outline` (≥ 2 пунктов) | `article_meta.md` + по одному запросу на каждый раздел (`article_section.md`); короткий раздел добирается до `ARTICLE_EXPAND_ATTEMPTS` раз через `article_section_expand.md` | близко к `word_count` |
| `outline` пустой (например, запуск из n8n) | один запрос `article_writer.md` + до `ARTICLE_EXPAND_ATTEMPTS` доборов `article_expand.md` | короче целевого объёма — модель обрывает длинный JSON |

Причина: небольшие модели обрывают ответ примерно на тысяче слов, сколько ни
проси в промпте. Поэтому длинная статья пишется по разделам.

Плейсхолдеры в промптах:

```text
{{topic}} {{language}} {{audience}} {{tone}} {{cta}}
{{word_count}} {{words_per_section}} {{brief_json}}
{{section_title}} {{section_index}} {{section_count}} {{section_word_count}}
{{knowledge_context}} {{competitor_context}}
```

Как они подставляются:

1. [`app/services/ai/prompt_loader.py`](app/services/ai/prompt_loader.py) читает файлы и подставляет значения
2. [`app/services/ai/openai_writer.py`](app/services/ai/openai_writer.py) отправляет system + user в API провайдера
3. Каталог промптов задаётся через `PROMPTS_DIR` (в Docker: `/app/prompts`)

**Чтобы изменить стиль или длину статьи** — правьте файлы в `prompts/`, перезапуск контейнера обычно не нужен (том смонтирован).

Параметры генерации (не текст промпта) — в `.env`:

| Переменная | Смысл | Пример |
| --- | --- | --- |
| `OPENAI_API_KEY` | Ключ провайдера | — |
| `OPENAI_MODEL` | Модель | `openai/gpt-4o-mini` |
| `OPENAI_BASE_URL` | OpenAI-совместимый endpoint | `https://openrouter.ai/api/v1` |
| `OPENAI_TEMPERATURE` | Креативность | `0.4` |
| `OPENAI_MAX_TOKENS` | Лимит ответа (с запасом над целевым объёмом: ~2.5–3 токена на русское слово) | `16000` |
| `ARTICLE_TARGET_WORD_COUNT` | Целевой объём (в промпт) | `3000` |
| `ARTICLE_MIN_WORD_RATIO` | Доля цели, ниже которой черновик добирается | `0.8` |
| `ARTICLE_EXPAND_ATTEMPTS` | Сколько доборов делать (0 — выключить) | `2` |
| `MAX_UPLOAD_MB` | Максимальный размер одного загружаемого файла (база знаний, выгрузки конкурентов); больше — ответ 413 | `20` |
| `OPENAI_EMBEDDING_MODEL` | Модель эмбеддингов (должна давать 1536 измерений) | `text-embedding-3-small` |
| `RAG_ENABLED` | Искать контекст в базе знаний при generate | `true` |
| `RAG_TOP_K` | Сколько чанков подмешивать в промпт | `5` |
| `RAG_CHUNK_SIZE` | Размер чанка в символах | `800` |
| `SERP_API_KEY` | Ключ Serper для ТОП выдачи (Stage 3) и Topic Discovery | — |
| `DISCOVERY_ENABLED` | Разрешить POST /discovery | `true` |
| `DISCOVERY_MAX_TOPICS` | Сколько тем в одном контент-плане | `10` |
| `DISCOVERY_SEARCH_N` | Organic-строк на сид на движок | `20` |
| `YANDEX_SERP_API_KEY` | Ключ SerpAPI для выдачи Яндекса (без ключа — только Google) | — |
| `YANDEX_SERP_BASE_URL` | Endpoint SerpAPI | `https://serpapi.com/search` |
| `TOPICS_FILE_PATH` | Куда export дописывает brief | `topics/topics.json` |
| `COMPETITOR_TOPICS_ENABLED` | Разрешить POST /competitor-topics | `true` |
| `COMPETITOR_TOPICS_MAX_TOPICS` | Потолок тем после ContentGapAnalyst | `80` |
| `COMPETITOR_TOPICS_MAX_HITS` | Потолок сигналов из файлов до LLM | `400` |
| `RESEARCH_ENABLED` | Разрешить POST /research и generate с research | `true` |
| `RESEARCH_TOP_N` | Сколько **статей**-конкурентов оставлять | `10` |
| `RESEARCH_SEARCH_N` | Сколько organic-ссылок запросить у Serper до фильтра | `40` |
| `RESEARCH_MIN_ARTICLE_CHARS` | Минимум видимых символов у страницы-конкурента | `300` |
| `MULTI_AGENT_ENABLED` | Разрешить generate с `use_multi_agent` | `true` |
| `IMAGES_ENABLED` | Разрешить замену плейсхолдеров при `use_images` | `true` |
| `OPENAI_IMAGE_MODEL` | Модель картинок (OpenAI Images / OpenRouter) | `x-ai/grok-imagine-image-2.0` |
| `OPENAI_IMAGE_SIZE` | Размер кадра (16:9) | `1792x1024` |
| `INTERNAL_LINKS_ENABLED` | Разрешить перелинковку при `use_internal_links` | `true` |
| `INTERNAL_LINK_MAX` | Максимум внутренних ссылок в одной статье | `5` |
| `INTERNAL_LINK_PREFIX` | Префикс href (`/slug`) | `/` |
| `DZEN_ENABLED` | Разрешить generate с `use_dzen` | `true` |
| `DZEN_TARGET_CHAR_COUNT` | Целевой объём Дзен-версии в символах | `4000` |
| `QUALITY_ENABLED` | Разрешить шаги качества при соответствующих флагах | `true` |
| `DETECTOR_AI_REVIEW_THRESHOLD` | `ai_likelihood` ≥ порога → `review` | `70` |
| `DETECTOR_UNIQUENESS_FLOOR` | `uniqueness` ниже порога → `review` | `50` |
| `SUMMARY_TARGET_CHAR_COUNT` | Целевой объём summary в символах | `500` |
| `APP_ENV` | Окружение (влияет на уровень логов, если `LOG_LEVEL` пуст) | `local` |
| `LOG_LEVEL` | Уровень логов: `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |

Логи приложения идут в stdout контейнера `app`:

```bash
docker compose logs -f app
```

---

## 4. Где лежит готовая статья

### 4.1 В ответе API

После успешной генерации статья сразу в HTTP-ответе:

```json
{
  "id": "uuid",
  "status": "completed",
  "title": "...",
  "meta_description": "...",
  "content_markdown": "...",
  "word_count": 632
}
```

Текст статьи — поле **`content_markdown`** (Markdown).

### 4.2 В базе данных

Таблица PostgreSQL: **`articles`**.

Посмотреть последние статьи:

```bash
docker compose exec postgres psql -U acf -d acf -c \
  "SELECT id, status, word_count, left(title, 60), created_at FROM articles ORDER BY created_at DESC LIMIT 5;"
```

Полный текст одной статьи:

```bash
docker compose exec postgres psql -U acf -d acf -c \
  "SELECT content_markdown FROM articles WHERE id = '<UUID>';"
```

Ключевые колонки:

| Колонка | Что хранит |
| --- | --- |
| `topic`, `language`, `audience`, `keywords` | Входные параметры |
| `title`, `meta_description`, `content_markdown` | Результат AI |
| `word_count` | Пересчёт бэкендом из markdown |
| `status` | `pending` → `processing` → `completed` / `failed` |
| `error_message` | Безопасное сообщение при ошибке |

### 4.3 В файле на диске

После успешной генерации статья также пишется в каталог
`output/articles/` (настраивается через `ARTICLES_OUTPUT_DIR`):

```text
output/articles/{ДД-ММ-ГГГГ}-{uuid}_{slug-темы}/
  article.md
  article.html
  competitors.txt   # только URL конкурентов, по одному на строку
  research.md       # план + заголовки и ссылки (без HTML чужих страниц)
  stage3_research.json  # тот же JSON, что отдаёт POST /research
  stage3_generate.json  # тот же JSON, что отдаёт POST /articles/generate
```

Пример: `08-09-2026-bd48d569-25e0-4b48-9500-9e2c683d5464_жесткий-или-мягкий-матрас-какой-лучше-выбрать`

- папка на каждую статью (статьи не свалены в один каталог)
- `.md` — исходник (YAML front matter + `content_markdown`)
- `.html` — простая HTML-страница, сконвертированная из Markdown на бэкенде
  (не AI). Позже экспорт HTML планируется вынести в n8n
  (см. `.cursor/rules/future-n8n-html-export.mdc`).
- при Stage 3: `competitors.txt`, `research.md`, `stage3_research.json`;
  у каждой статьи также `stage3_generate.json` (ответ generate).

Открой файлы в редакторе или:

```powershell
Get-ChildItem output\articles -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

Пустой `ARTICLES_OUTPUT_DIR=` отключает запись на диск (статья остаётся только в БД).

### Что ещё имеет смысл позже (не Stage 1)

* В Stage 1 достаточно сильных правил «живого» языка в
  `prompts/article_writer.md`. Детекторы / Humanizer / summary уже есть:
  [§5.6](#56-детекторы-humanizer-и-summary-stage-6). Это эвристика своего
  чата, не Copyscape / GPTZero и не сторонний Humanizer API.
  Дзен-версия: [§5.5](#55-дзен-stage-6).

---

## 5. Процесс: от темы до готовой статьи

```text
1. Клиент отправляет POST /api/v1/articles/generate
   body: { topic, language?, audience?, keywords? }
                    │
2. API-слой (routes/articles.py)
   - валидирует тело (schemas/articles.py)
   - вызывает ArticleService через DI (api/deps.py)
                    │
3. ArticleService (services/article_service.py)
   - создаёт строку в БД: status = pending
   - обновляет: status = processing
                    │
4. AIWriter.generate (services/ai/openai_writer.py)
   - загружает промпты из prompts/
   - подставляет topic / language / audience / keywords / target_word_count
   - вызывает OpenAI-совместимый API
   - парсит JSON и валидирует через AIArticleOutput (schemas/ai.py)
                    │
5. ArticleService (продолжение)
   - пересчитывает word_count из content_markdown (core/word_count.py)
   - сохраняет title, meta_description, content_markdown, word_count
   - status = completed
                    │
6. API возвращает ArticleGenerateResponse клиенту
```

### Пример вызова

```bash
curl -X POST http://localhost:8000/api/v1/articles/generate \
  -H "Content-Type: application/json" \
  -d "{\"topic\":\"Как выбрать промышленный насос\",\"language\":\"ru\",\"audience\":\"Инженеры\",\"keywords\":[\"промышленный насос\"]}"
```

### Если что-то пошло не так

```text
Ошибка провайдера / невалидный JSON от модели
  → status = failed, error_message сохранён
  → HTTP 502 { detail, id, status: "failed" }

Внутренний сбой / нет ключа
  → status = failed
  → HTTP 500 { detail: "Article generation failed", id, status: "failed" }

Невалидный запрос (пустой topic)
  → HTTP 422 (статья в БД не создаётся)
```

Секреты, stack traces и пароли в ответ **никогда** не попадают.

---

## 5.1 База знаний (Stage 2) — как пользоваться

База знаний — это ваши материалы (спеки, гайды, FAQ, внутренние тексты).
Система режет их на фрагменты, считает эмбеддинги и при генерации статьи
подмешивает ближайшие выдержки в промпт (`{{knowledge_context}}`).

Пустая база **не ломает** generate: поведение как в Stage 1.

Интерактивные формы всех запросов: <http://localhost:8000/docs>
(раздел **documents** и **articles**).

### Что положить в базу

Имеет смысл загружать тексты, на которые статья должна опираться:

- описания товаров, линейки, отличия моделей;
- внутренние гайды, FAQ, регламенты;
- факты, которые модель не должна выдумывать (размеры, составы, гарантии).

Не нужно: случайные веб-страницы, чужие статьи целиком, секреты и ключи.
Форматы файлов: **`.md`**, **`.txt`**, **`.pdf`**. Лимит размера —
`RAG_MAX_FILE_BYTES` (по умолчанию 2 МБ).

Контекст клиента (сайт, гео, конкуренты, запреты) — локальный файл, в git не попадает:
`knowledge/<проект>-brief.md`.
Это **не** таблица тем: темы импортируются в `topics/` ([§5.2b](#52b-темы-из-файлов-конкурентов)).

Готовые учебные файлы под тему из `topics/topics.json`: каталог
[`knowledge/`](knowledge/README.md).

### Шаг 0. Подготовка один раз

1. В `.env` должны быть `OPENAI_API_KEY` и (при OpenRouter) `OPENAI_BASE_URL`.
   Эмбеддинги идут **тем же ключом**, что и генерация.
2. Добавьте переменные из [`.env.example`](.env.example), если их ещё нет:

```text
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
RAG_ENABLED=true
RAG_TOP_K=5
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=120
RAG_MAX_FILE_BYTES=2000000
```

   На **OpenRouter** модель эмбеддингов обычно с префиксом:

```text
OPENAI_EMBEDDING_MODEL=openai/text-embedding-3-small
```

   Менять `EMBEDDING_DIMENSIONS` нельзя без новой миграции (колонка vector(1536)).

3. Поднять стек и дождаться health:

```powershell
docker compose up --build -d
curl.exe http://localhost:8000/health
```

Ожидается: `{"status":"ok","database":"ok"}`.

Compose использует том `postgres_pgvector_data` (образ `pgvector/pgvector:pg16`).
Старый том Stage 1 `postgres_data` не подключается. Файлы в `output/articles/`
на месте.

После правок `.env`:

```powershell
docker compose up -d --force-recreate app
```

### Шаг 1. Загрузить документ

**Вариант A — JSON (текст в теле запроса)**

В Swagger проще всего: `POST /api/v1/documents`. Из терминала:

```powershell
$body = '{"title":"Спека насоса","filename":"pumps.md","content":"# Насос\n\nВыбирайте по напору и подаче."}'
curl.exe -X POST http://localhost:8000/api/v1/documents `
  -H "Content-Type: application/json" `
  -d $body
```

Тело запроса:

```json
{
  "title": "Спека насоса",
  "filename": "pumps.md",
  "content": "# Насос\n\nВыбирайте по напору и подаче."
}
```

**Вариант B — файл**

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/upload `
  -F "file=@C:\path\to\notes.md" `
  -F "title=Заметки"
```

Успех: HTTP **201**, в ответе `id`, `status: ready`, `chunk_count` > 0.

Ошибки ингеста:

| Код | Когда |
| --- | --- |
| 400 | пустой текст, неподдерживаемый тип файла, файл больше лимита |
| 502 | провайдер эмбеддингов недоступен / неверная модель |
| 500 | внутренняя ошибка |

Пока документ не `ready`, в поиске и в generate он не участвует.

### Шаг 2. Проверить, что документы на месте

```powershell
curl.exe http://localhost:8000/api/v1/documents
```

Один документ (включая извлечённый текст): `GET /api/v1/documents/{id}`.

Удалить документ и все его чанки: `DELETE /api/v1/documents/{id}`.

### Шаг 3. Проверить поиск (без генерации статьи)

Запрос должен быть похож на тему будущей статьи:

```json
{
  "query": "как выбрать жесткость матраса",
  "top_k": 5
}
```

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/search `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"как выбрать жесткость матраса\",\"top_k\":5}"
```

В ответе — ближайшие чанки, `score` (меньше = ближе по cosine distance) и
`document_id`. Если список пустой: база пуста, документ не `ready`, или
эмбеддинги не посчитались.

### Шаг 4. Сгенерировать статью с базой

Обычный `POST /api/v1/articles/generate`. Поле `use_knowledge_base` по
умолчанию **true** — отдельно включать не нужно.

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "language": "ru",
  "use_knowledge_base": true
}
```

Отключить RAG для одного запроса: `"use_knowledge_base": false`.
Выключить для всех запросов: `RAG_ENABLED=false` в `.env` и пересоздать `app`.

Пакет из `topics/topics.json` (`make generate-topics`) тоже ходит в generate
с RAG по умолчанию, если в JSON не указано иное.

### Что происходит внутри

```text
документ → parser (md/txt/pdf) → чанки → Embedder → таблица chunks
                                                    ↓
generate → RagService ищет top_k чанков по теме     ↓
         → {{knowledge_context}} в prompts/*.md     ↓
         → AIWriter пишет статью
```

Эмбеддинги только в `app/services/ai/` (`OpenAIEmbedder`). В тестах —
`MockEmbedder`, реальный API не вызывается.

---

## 5.2 Конкуренты / SEO (Stage 3) — как это работает

Stage 3 отвечает на вопрос: **что уже стоит в топе поиска по теме, какая у
этих статей структура, и как нам написать лучше**. Это не база знаний (§5.1)
и не ручной `outline` из `topics.json`.

Обычный `POST /api/v1/articles/generate` **сам в поиск не ходит**.
Конкуренты подключаются только если вы вызвали research или явно включили флаг.

### Откуда берутся конкуренты

Источник — **органическая выдача Google**, не Яндекс, не наши документы и не
список URL из запроса.

Цепочка:

```text
тема (+ keywords)
        │
        ▼
Serper API  →  те же organic-результаты, что в Google по запросу
        │        (title, url, snippet, позиция 1…N)
        ▼
фильтр URL: только публичный http(s); без YouTube/соцсетей,
маркетплейсов и витрин (/catalog, /product, …)
        │
        ▼
для каждой ссылки: GET HTML страницы (обычный HTTP, без ключа Serper)
        │
        ▼
фильтр страницы: есть H1–H3, видимый текст ≥ 300 символов,
это не карточка товара (og:type/schema Product без Article)
        │
        ▼
парсер снимает СТРУКТУРУ, не копирует статью целиком
        │
        ▼
модель собирает улучшенный outline + подсказки title / meta / slug
        │
        ▼
PostgreSQL: research_runs + research_competitors
```

**Запрос в Google** собирается так: `topic`, затем через пробел ключевые слова
из поля `keywords` (дубли выкидываются). Пример: тема
«Жесткий или мягкий матрас…» + keyword `жесткость матраса` → в Serper уходит
одна строка `q` с этим текстом.

Сколько ссылок: `top_n` в теле запроса или `RESEARCH_TOP_N` в `.env`
(по умолчанию 10, максимум 10) — это уже **статьи после фильтра**.
У Serper запрашивается до `RESEARCH_SEARCH_N` organic-результатов
(по умолчанию 40, с пагинацией страниц выдачи), чтобы после отсева
YouTube / витрин всё ещё набрать 10 статей.
Берутся только элементы массива `organic` у Serper (не реклама, не knowledge
graph, не картинки).

В анализ **не попадают**:

- видео и соцсети: YouTube, Rutube, Vimeo, TikTok, VK, Instagram и т.п.;
- маркетплейсы: Wildberries, Ozon, Avito, Amazon, Яндекс Маркет и т.п.;
- витрины магазина: URL с сегментами `/catalog`, `/product`, `/tovar`, `/cart`…;
- страницы, которые не скачались, короче `RESEARCH_MIN_ARTICLE_CHARS`
  (по умолчанию 300 символов видимого текста) или без заголовков H1–H3;
- карточки товара (`og:type=product` / schema.org Product без Article).

Блог на сайте бренда (`/blog`, `/article`) остаётся, если это полноценная
статья. Карточка товара и каталог того же домена — нет.

Ключ: `SERP_API_KEY` в `.env` ([serper.dev](https://serper.dev/)). Без ключа
`POST /api/v1/research` падает с ошибкой конфигурации. Generate без флага
research по-прежнему работает.

### Что снимается со страницы конкурента

Бэкенд **не сохраняет** полный HTML и **не кладёт чужой текст в базу знаний**.
В `research_competitors` остаётся профиль:

| Поле | Откуда |
| --- | --- |
| `title`, `url`, `snippet` | выдача Serper (snippet — короткий абзац из SERP) |
| `headings` | тексты H1–H3 со страницы |
| `section_images` | сколько `img` стоит под каждым H1–H3 |
| `word_count` | оценка объёма видимого текста |
| `image_count` / `video_count` | теги `img`, `video`, iframe YouTube/Vimeo/Rutube/VK |
| `list_count` / `table_count` | списки и таблицы |
| `has_faq` / `features` | FAQ по заголовкам («FAQ», «часто задаваем…»), плюс lists/tables/video |
| `fetch_status` | в сохранённом списке только `fetched`: короткие, видео, витрины и сбой загрузки отбрасываются до записи |

Лимиты: таймаут `RESEARCH_FETCH_TIMEOUT_SECONDS` (15 с), размер
`RESEARCH_MAX_PAGE_BYTES` (1 МБ). Если страница не открылась или не прошла
фильтр статьи, URL **не** попадает в `competitors` и не участвует в outline.

Дальше **не копируется чужой текст**. Модель (`competitor_outline.md`) видит
только эти профили и должна:

1. покрыть темы, которые есть у нескольких конкурентов;
2. добавить разделы, которых у них нет, если они полезны;
3. выдать 6–10 пунктов плана (H2), FAQ/заключение при необходимости;
4. дать более сильные `title_hint`, `meta_description_hint`, `url_slug_hint`.

Если модель outline не ответила, бэкенд собирает запасной план из чужих H2
(без копирования абзацев).

### Чем это не является

| Это | Это не |
| --- | --- |
| ТОП органики Google через Serper | выгрузка из Яндекса / Search Console |
| структура (оглавление + счётчики) | рерайт чужой статьи |
| план для **нашей** статьи | загрузка конкурентов в RAG |
| подсказки SEO-обёртки | реальные картинки, перелинковка, CMS |

База знаний (§5.1) — **ваши** файлы. Research — **чужие URL из выдачи**.
Их можно сочетать: research задаёт оглавление, RAG подставляет ваши факты.

### Как запустить

Нужны `SERP_API_KEY` и тот же `OPENAI_API_KEY`, что для статей. После правки
`.env`: `docker compose up -d --force-recreate app`. Формы: <http://localhost:8000/docs>
(разделы **research** и **articles**).

**Шаг 1 — исследование** (`POST /api/v1/research`):

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "language": "ru",
  "keywords": ["жесткость матраса"],
  "top_n": 5
}
```

```powershell
curl.exe -X POST http://localhost:8000/api/v1/research `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"Жесткий или мягкий матрас: какой лучше выбрать?\",\"keywords\":[\"жесткость матраса\"]}"
```

Успех: HTTP **201**, `status: completed`. В ответе:

- `id` — сохранить, это `research_id`;
- `query` — фактическая строка, ушедшая в Google;
- `outline` — наш улучшенный план;
- `title_hint` / `meta_description_hint` / `url_slug_hint`;
- `competitors[]` — кто был в топе и какая у них структура.

Список прогонов: `GET /api/v1/research`. Один прогон: `GET /api/v1/research/{id}`.

**Шаг 2 — статья по этому плану** (`POST /api/v1/articles/generate`):

Вариант A (предпочтительный) — уже есть research:

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "research_id": "<uuid из шага 1>"
}
```

Вариант B — research внутри generate (дольше: Serper + скачивание + две модели):

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "use_competitor_research": true
}
```

Ручной `outline` в этом запросе **заменяется** планом из research. Вместе с
ним brief получает среднее по ТОП: `word_count`, `image_placeholders`,
`infographic_placeholders`, `include_tables` / `include_lists` /
`include_faq` / `faq_count`, и `article_goal` аналитика. Эти поля не нужно
зашивать в `topics.json`, если есть `research_id` или
`use_competitor_research`. Флаги `use_*` в файле остаются.

Writer пишет по разделам этого плана; в промпт ещё попадает блок
`{{competitor_context}}` (подсказки SEO и оглавления конкурентов, не полные
тексты). Модель не должна ссылаться на «конкурентов» и «выдачу» в самой статье.
URL проанализированных страниц пишутся в папку статьи:
`competitors.txt` (только ссылки), `research.md` (план + список),
`stage3_research.json` (полный ответ research), `stage3_generate.json`
(полный ответ generate), блок «Проанализированные конкуренты» в `article.md`
и JSONB `articles.competitor_sources`. В `content_markdown` и `article.html` их нет.

`make generate-topics` флаг research **не включает** — в `topics.json` нужно
явно добавить `"use_competitor_research": true` или сначала сделать
`POST /research` и передать `research_id`.

### Ошибки

| Код | Когда |
| --- | --- |
| 422 | пустой `topic` |
| 500 | нет `SERP_API_KEY`, `RESEARCH_ENABLED=false`, внутренний сбой |
| 502 | Serper недоступен / пустая выдача / нет статей после фильтра / сбой модели outline |
| 404 | `GET /research/{id}` — нет такого прогона |

В логах (`docker compose logs -f app`) нет HTML страниц и нет ключей.

В тестах сеть не дергается: `MockSearchProvider` (example.com),
`MockPageFetcher`, `MockCompetitorAnalyst`.

---

## 5.2a Контент-план (Topic Discovery)

Закрывает шаг **Topic Discovery** из `PROJECT.md` §1: из сидов собирается
список тем, который потом попадает в `topics.json`. Это **не** Stage 3
research — research анализирует уже выбранную тему.

```text
seeds (+ niche)
        │
        ▼
Google (Serper: organic + People Also Ask + related)
Яндекс (SerpAPI; без ключа шаг пропускается)
        │
        ▼
дедуп кандидатов (без AI)
        │
        ▼
TopicPlanner → brief как в topics.json
        │
        ▼
PostgreSQL: content_plans + content_plan_topics
        │
        ▼
POST /api/v1/discovery/{id}/export  →  append в topics.json
        │
        ▼
make generate-topics  (как раньше)
```

HTML `google.com` / `yandex.ru` не парсим. Рекурсивный обход related нет.

Как выбрать этот шаг или файлы конкурентов: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics).

**Шаг 1** — `POST /api/v1/discovery`:

```json
{
  "seeds": ["жесткость матраса"],
  "niche": "матрасы",
  "language": "ru",
  "audience": "Покупатели матрасов",
  "max_topics": 10
}
```

Нужен `SERP_API_KEY`. `YANDEX_SERP_API_KEY` опционален. Ответ: `topics[].brief`
совместим с `ArticleGenerateRequest`.

**Шаг 2** — экспорт (не запускает generate):

```bash
curl -X POST http://localhost:8000/api/v1/discovery/<id>/export
```

или с хоста:

```bash
python scripts/export_content_plan.py <id>
```

Существующие темы в файле не затираются. Дальше — `make generate-topics`.

| Код | Когда |
| --- | --- |
| 422 | пустые `seeds` |
| 500 | нет `SERP_API_KEY`, `DISCOVERY_ENABLED=false`, пустой путь export |
| 502 | Serper / SerpAPI / планировщик тем |
| 404 | нет такого плана |

В тестах: `MockSerpSnapshotProvider`, `MockTopicPlanner`.

---

## 5.2b Темы из файлов конкурентов

Первый подшаг анализа конкурентов: выгрузки URL/ключей → контент-план →
`topics.json`. **Discovery не заменяет** этот шаг. Stage 3 research — второй
подшаг: уже выбранная тема → структура ТОП-страниц.

```text
xlsx/csv/txt  ──►  POST /sources  ──►  ContentGapAnalyst
content-plan JSON  ►  POST /  или /upload
        │
        ▼
PostgreSQL: content_plans (source=competitor_gap)
        │
        ▼
POST /api/v1/competitor-topics/{id}/export  →  topics.json
        │
        ▼
Stage 3 research + generate
```

Контекст сайта — в RAG:
`knowledge/<проект>-brief.md`.
Таблицу тем в базу знаний не кладём. Generate из плана не запускается.
Заголовки из выгрузок не копируем дословно: `ContentGapAnalyst` переписывает
кластеры. Если аналитик вернул пустой список, остаётся по одной теме на
уникальный hit.

**Шаг 1** — бриф проекта в RAG:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/upload `
  -F "file=@knowledge/<проект>-brief.md" `
  -F "title=Контекст проекта"
```

**Шаг 2а** — сырьё конкурентов (xlsx / csv / txt / json):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/competitor-topics/sources `
  -F "files=@promatras.xlsx" `
  -F "files=@askona.csv" `
  -F "domain=example.com" `
  -F "niche=товары для сна" `
  -F "audience=Покупатели матрасов" `
  -F "geo=Беларусь"
```

**Шаг 2б** — уже готовый `content-plan-*.json`:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/competitor-topics `
  -H "Content-Type: application/json" `
  --data-binary "@topics\content-plan-example.com.json"
```

или файл:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/competitor-topics/upload `
  -F "file=@topics\content-plan-example.com.json"
```

**Шаг 3** — export (не generate):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/competitor-topics/<id>/export
```

Без API, только готовый JSON:

```powershell
python scripts/import_competitor_plan.py `
  topics\content-plan-example.com.json `
  --topics-file topics\topics.json
```

Существующие темы не затираются. В brief: `topic`, `audience`, `search_intent`,
`article_goal`, `cta`. `outline` / `word_count` / `research_id` заполнит research.
`priority`, `isGap`, `category` хранятся в плане, не в `topics.json`.

| Код | Когда |
| --- | --- |
| 422 | нет `topics` / битый JSON / пустой или неподдерживаемый dump |
| 502 | `ContentGapAnalyst` (OpenAI) не смог разобрать ответ |
| 500 | `COMPETITOR_TOPICS_ENABLED=false`, пустой путь export |
| 404 | нет такого плана (или это Discovery-план, не competitor_gap) |

Как выбрать этот шаг или поиск по тематике: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics).

---

## 5.2c Как переключать режимы Discovery / Competitor topics

Это выбор **источника тем**, не генерации статьи. Делается **до**
`make generate-topics`. n8n не нужен. Флаг в `POST /articles/generate` для
этого не существует.

Сначала поднимите API: `make up`. Проверка: `curl http://localhost:8000/health`.

| Что есть на входе | Режим | Команда |
| --- | --- | --- |
| Только тематика / запросы («матрасы Минск») | `discovery` | `make topics-discovery` |
| xlsx / csv / txt / json с темами или ключами конкурентов | `competitor` + файлы | `make topics-competitors` |
| Готовый `content-plan-*.json` | `competitor` + план | `make topics-competitors` с `CONTENT_PLAN` |

Оба режима **дописывают** briefs в [`topics/topics.json`](topics/topics.json)
и **не** пишут статьи. Потом пакет: экран «Генерация» → «Контент-план»,
или `make generate-topics`.

### Режим Discovery (есть тематика, нет файлов конкурентов)

Нужен `SERP_API_KEY` в `.env`. Яндекс опционален (`YANDEX_SERP_API_KEY`).

```bash
make topics-discovery SEEDS="матрасы Минск"
```

Несколько семян — через запятую. Ниша и аудитория по желанию:

```bash
make topics-discovery SEEDS="матрасы Минск,жесткость матраса" NICHE="товары для сна" AUDIENCE="Покупатели матрасов"
```

То же скриптом (API на localhost:8000):

```bash
python scripts/build_topics.py --mode discovery --seed "матрасы Минск"
```

`--mode discovery` обязателен. `--files` и `--plan` в этом режиме запрещены.

Подробности API: [§5.2a](#52a-контент-план-topic-discovery).

### Режим Competitor topics (есть файлы конкурентов)

Сырые выгрузки (пути от корня репозитория):

```bash
make topics-competitors COMPETITOR_FILES="topics/keys.csv"
```

Несколько файлов — пробелом: `COMPETITOR_FILES="topics/a.csv topics/b.xlsx"`.
Опционально: `DOMAIN=example.com NICHE="товары для сна"`.

Готовый контент-план (без HTTP, без SERP):

```bash
make topics-competitors CONTENT_PLAN=topics/content-plan-example.com.json
```

Скриптом:

```bash
python scripts/build_topics.py --mode competitor --files topics/keys.csv
python scripts/build_topics.py --mode competitor --plan topics/content-plan-example.com.json
```

`--mode competitor` обязателен. `--seed` в этом режиме запрещён.
`--files` и `--plan` вместе за один запуск нельзя.

Подробности API: [§5.2b](#52b-темы-из-файлов-конкурентов).

### Что нельзя

- запускать оба режима «на всякий случай» в одном вызове;
- ждать, что generate сам выберет Discovery или файлы;
- класть ключи OpenAI / Serper в команду — они только в `.env` бэкенда.

Ошибка без `--mode`, без `--seed` в discovery или без файлов/плана в
competitor — скрипт выходит с кодом 2 и ничего не пишет в `topics.json`.

### Что хранить в `topics/`

В папке только источники и рабочая очередь. Производные копии не нужны.

| Файл | Нужен | Зачем |
| --- | --- | --- |
| `topics.json` | да, рабочий (локально, в git не попадает) | очередь для `make generate-topics` и export Discovery/competitor |
| `topics.example.json` | да, шаблон | полный brief; **не** слать в generate |
| `topics.example.txt` | да, шаблон | одна тема на строку; **не** слать в generate |
| `content-plan-<домен>.json` | локально, если есть | вход `--mode competitor --plan` |

Не класть сюда:

- копии briefs после import — пишите сразу в `topics.json`;
- xlsx/csv выгрузки конкурентов на постоянку — передавайте через `--files` и не коммитьте;
- бриф сайта и FAQ — это [`knowledge/`](knowledge/), не темы;
- готовые статьи — это `output/articles/`.

Пустой `topics.json` — массив `[]`. Пустая строка `"topic": ""` generate не пройдёт.

---

## 5.3 Мультиагенты (Stage 4) — как это работает

Обычный `POST /api/v1/articles/generate` по-прежнему один вызов writer
(плюс RAG/research, если вы их включили). Stage 4 добавляет **цепочку агентов**
по флагу `"use_multi_agent": true`.

```text
Research Agent  →  SERP + структура (тот же ResearchService, что Stage 3)
SEO Agent       →  уточняет outline, ключи, title/meta/slug
Writer Agent    →  пишет статью (тот же AIWriter)
Fact Checker    →  сверяет черновик с базой знаний, ловит выдуманные цифры
Editor          →  вычитывает черновик и применяет замечания фактчекера
```

Это всё ещё **производство текста**, не публикация. Картинки и перелинковка —
[§5.4](#54-картинки-и-перелинковка-stage-5). Детекторы и CMS — следующие этапы.

### Как включить

В `.env` (`MULTI_AGENT_ENABLED=true` по умолчанию) и в теле generate:

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "use_multi_agent": true,
  "use_knowledge_base": true
}
```

```powershell
curl.exe -X POST http://localhost:8000/api/v1/articles/generate `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"Жесткий или мягкий матрас: какой лучше выбрать?\",\"use_multi_agent\":true}"
```

Без флага поведение как в Stage 1–3: лишние вызовы SEO / фактчека / редактора
не идут.

Можно передать уже готовый `research_id`. Если его нет, Research Agent сам
запустит Stage 3 research. Нет `SERP_API_KEY` — шаг research **пропускается**,
остальные агенты работают от brief.

`make generate-topics` флаг **не включает** — добавьте `"use_multi_agent": true`
в объекты `topics.json`.

### Что возвращается

Поля статьи те же (`title`, `meta_description`, `content_markdown`, …).
Дополнительно `pipeline` — короткая трасса шагов (имена, status, вердикт
фактчека, число замечаний). Тело статьи, векторы и HTML в трассу не пишутся.
Та же JSONB-колонка `articles.pipeline` в PostgreSQL.

Промпты агентов: `prompts/seo_brief.md`, `prompts/fact_check.md`,
`prompts/article_editor.md`.

В логах (`docker compose logs -f app`) нет полного текста статьи и нет ключей —
только шаг, id, число слов, вердикт фактчека.

В тестах провайдер не вызывается: `MockSeoAgent`, `MockFactChecker`, `MockEditor`.

---

## 5.4 Картинки и перелинковка (Stage 5)

После writer (или редактора мультиагентов) бэкенд может:

1. **Заменить плейсхолдеры** `![alt](IMAGE_PLACEHOLDER_N)` /
   `INFOGRAPHIC_PLACEHOLDER_N` на файлы `images/image-N.png` /
   `images/infographic-N.png`.
2. **Вставить внутренние ссылки** `[якорь](/slug)` на другие **completed**
   статьи того же языка.

Картинки **opt-in** (`"use_images": true`): тарифицируются отдельно,
тот же `OPENAI_API_KEY`. Перелинковка **по умолчанию включена** и бесплатная;
пустой каталог — no-op.

Переключатель текст / картинки (`topics/topics.json` или тело generate):

| Режим | Флаги |
| --- | --- |
| Только текст | `"use_text": true`, `"use_images": false` |
| Текст и картинки | `"use_text": true`, `"use_images": true` |
| Только картинки к готовой статье | `"use_text": false`, `"use_images": true`, `"article_id": "<uuid>"` |

Только картинки не вызывают writer: перерисовывают слоты
`IMAGE_PLACEHOLDER_N` или уже стоящие `images/*.png`. То же самое:
`POST /api/v1/articles/{id}/images`.

Пакетно: `--text-only` или `--images-only --article-id <uuid>`.

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "use_text": true,
  "use_images": true,
  "use_internal_links": true
}
```

```powershell
curl.exe -X POST http://localhost:8000/api/v1/articles/generate `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"Жесткий или мягкий матрас: какой лучше выбрать?\",\"use_images\":true}"
```

Сбой одного кадра **не валит статью**: плейсхолдер остаётся, статус ассета
`failed` / `skipped`. Нет ключа или `IMAGES_ENABLED=false` — остальные кадры
пропускаются. Байты картинок пишутся в папку статьи рядом с `article.md`;
в PostgreSQL и в HTTP-ответе только метаданные (`assets`, `internal_links`).

Перелинковка без отдельного LLM: пересечение keywords/темы, максимум 5 ссылок,
не трогает заголовки, уже существующие ссылки, картинки и fenced-блоки.

Промпт картинки: `prompts/image_generate.md`. Обложка `images/cover.png`
рисуется из **названия статьи** (`COVER_PLACEHOLDER` сразу после H1).
Остальные кадры берут **заголовок и текст своего блока**. Если включён
анализ конкурентов, число фото на раздел — среднее по их `section_images`
(поле `section_image_placeholders` у research и у brief). Редактор Stage 4
обязан оставить `COVER_PLACEHOLDER`, `IMAGE_PLACEHOLDER_N` и
`INFOGRAPHIC_PLACEHOLDER_N` как есть.

На OpenRouter модели вроде `x-ai/grok-imagine-image-2.0` идут в `POST /api/v1/images`.
`openai/gpt-image-*` по-прежнему через OpenAI Images API (`/images/generations`).

В тестах провайдер картинок не вызывается: `MockImageProvider`.

---

## 5.5 Дзен (Stage 6)

После готовой основной статьи бэкенд может написать **короткую версию для
Дзена**: та же тема и факты, меньше символов, заголовок берётся из названия
основной статьи. В тексте три картинки: главная (обложка) и две в теле.

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "use_dzen": true,
  "use_images": true
}
```

Выключить и включить обратно:

- **одна тема** — `"use_dzen": false` или `true` в `topics/topics.json`
  (или в теле `POST /api/v1/articles/generate`);
- **весь пакет** — `python scripts/generate_from_topics.py topics/topics.json --no-dzen`
  или `--dzen` (перебивает файл);
- **все запросы** — `DZEN_ENABLED=false` в `.env`, затем
  `docker compose up -d --force-recreate app`. Даже при `"use_dzen": true`
  Дзен будет `skipped`. Вернуть: `DZEN_ENABLED=true` и тот же recreate.

Без `"use_dzen": true` (и без `--dzen`) короткая версия не пишется.

Без `"use_images": true` в Дзен-тексте остаются плейсхолдеры
`DZEN_COVER_PLACEHOLDER` / `DZEN_IMAGE_PLACEHOLDER_1` / `_2`.
С картинками они становятся `images/dzen-cover.png`, `dzen-1.png`, `dzen-2.png`.

Целевой объём — `DZEN_TARGET_CHAR_COUNT` (по умолчанию 4000 символов с пробелами).
Бэкенд пересчитывает `char_count` сам.

Сбой Дзена **не валит** основную статью (`dzen.status`: `failed` / `skipped`).
В ответе поле `dzen`. В папке статьи — `dzen.md` и `dzen.html`.
В PostgreSQL — JSONB `articles.dzen` без байтов картинок.

Промпт: `prompts/dzen_article.md`. В тестах: `MockDzenWriter`.

---

## 5.6 Детекторы, Humanizer и summary (Stage 6)

После картинок и перелинковки бэкенд может оценить черновик, слегка
«очеловечить» его и написать короткое содержание. Все три шага **выключены**
по умолчанию — каждый стоит отдельный вызов чата.

```json
{
  "topic": "Жесткий или мягкий матрас: какой лучше выбрать?",
  "use_detectors": true,
  "use_humanizer": true,
  "use_summary": true
}
```

Это **не** Copyscape, **не** GPTZero и **не** веб-проверка уникальности.
Детектор смотрит на стиль (шаблонные связки, ровный ритм) и ставит
`ai_likelihood` / `uniqueness` от 0 до 100. Вердикт `pass` или `review`
считает бэкенд по порогам `DETECTOR_AI_REVIEW_THRESHOLD` (70) и
`DETECTOR_UNIQUENESS_FLOOR` (50). Humanizer — свой промпт, не SaaS вроде
Undetectable.ai. Он обязан сохранить markdown-картинки и внутренние ссылки.

Порядок: детекторы → humanizer → summary → Дзен. Summary и Дзен берут уже
финальный текст. Сбой шага не валит основную статью (`skipped` / `failed`).

В ответе поле `quality`. В PostgreSQL — JSONB `articles.quality` без тела
статьи. При готовом summary в папке статьи появляется `summary.md`.

Промпты: `prompts/ai_detector.md`, `prompts/article_humanizer.md`,
`prompts/article_summary.md`. В тестах: `MockAiDetector` / `MockHumanizer` /
`MockSummarizer`.

---

## 5.7 Панель оператора (Stage 8a)

Локальный UI в [`web/`](web/): Vite + React + TypeScript + MUI. Только HTTP
к FastAPI — без ключей и без логики generate.

Сначала API, затем панель. Полный порядок — [§2](#2-порядок-включения):

```powershell
docker compose up --build -d
curl.exe http://localhost:8000/health
cd web
npm run dev
```

Открыть <http://127.0.0.1:15173>. Vite проксирует `/api` и `/health` на
`:8000`. Если задать `VITE_API_BASE_URL=http://localhost:8000`, нужен CORS
(`APP_CORS_ORIGINS` в `.env`, по умолчанию origin Vite).

Панель не публикует статьи в CMS и не хранит ключи. Ключи остаются в `.env`.

### Как устроен экран

Слева меню. Сверху — текущий **проект**. Всё ниже (статьи, база, темы,
генерация) относится только к нему. Чужой проект эти данные не видит.
**Новый проект** — имя, slug и язык (`ru` или `en`). Slug потом не меняется:
от него зависят папки `topics/{slug}/` и `output/articles/{slug}/`.
Проект `default` использует общий `topics/topics.json`.

Внизу меню — **Настройки**.

Обычный порядок работы:

1. Выбрать проект.
2. Загрузить факты в **Базу знаний**, если статья должна на них опираться.
3. Собрать список тем на экране **Темы**.
4. Написать статьи на экране **Generate**.
5. Прочитать и поставить вердикт на экране **Статьи**.

### Обзор

Главная страница показывает, живы ли API и база. Если API недоступен,
снова выполните шаг 2 из [§2](#2-порядок-включения), затем `npm run dev` в `web/`.

### Темы

Здесь только список тем. Статья ещё не пишется.

- **Только тематика** — запросы вроде «матрасы Минск». Сервер снимает выдачу
  Google и, если ключ задан, Яндекса, и собирает briefs. Нужен ключ поиска.
- **Файлы конкурентов** — два подрежима. **Выгрузки** (xlsx, csv, txt):
  сырые ключи и темы, по ним ищутся пробелы. **Готовый content-plan JSON**:
  план уже собран, импорт без поиска и без нового разбора.

Язык в форме — только `ru` или `en`. Кнопка экспорта дописывает briefs в
файл тем проекта. Повторный экспорт не затирает уже лежащие темы.

### Generate

Два режима.

**Одна статья** открыта сразу. Поля: тема, аудитория, язык, ключевые слова.
Галочки по умолчанию сняты. Что они делают:

| Галочка | Что произойдёт |
| --- | --- |
| База знаний | В текст попадут фрагменты документов этого проекта |
| Конкуренты / SEO | По этой теме снимается топ выдачи, статья пишется по структуре этих страниц |
| Мультиагенты | После черновика его правят SEO-агент, проверка фактов и редактор |
| Картинки | Обложка и фото разделов заменяют метки в тексте |
| Дзен | Дополнительно пишется короткая версия: обложка и два фото в тексте |
| Детекторы | Считаются свои оценки, их видно на карточке |
| Humanizer | Текст переписывается ещё раз, с учётом оценок детекторов, если они включены |
| Краткое содержание | Считается короткий пересказ готовой статьи |

Перелинковки в этом режиме нет. Какие галочки и какой объём подставлять
сразу — задаётся в **Настройки → Одна статья** и хранится в этом браузере.
Пустой объём значит цель сервера (обычно 3000 слов).

Один запуск пишет одну статью и открывает её карточку. Ответ может идти
несколько минут, вкладку не закрывать.

**Контент-план** берёт очередь из файла тем текущего проекта и показывает
названия. **Сгенерировать все** пишет их по одной. Флаги берутся из каждого
brief, не из формы. Прогресс — «3 из N». Ошибка одной темы не останавливает
остальные. **Остановить** прекращает очередь, уже написанные статьи остаются.
Повторный запуск пишет те же темы ещё раз. Пустой файл — сначала соберите
список на экране **Темы**. Полный файл на сотню тем долгий и платный.

Тот же пакет из терминала: `make generate-topics`.

### Статьи

Таблица тем проекта. Фильтры **Статус** (готово, ошибка, в работе, ожидает)
и **Ревью** (на ревью, принято, отклонено). Клик по строке открывает карточку:
текст Markdown, картинки, Дзен, оценки quality. Кнопки **Принять**,
**Отклонить** и **Сбросить ревью** меняют только вердикт оператора.
Повтор картинок — отдельная кнопка на карточке, без новой статьи.

### База знаний

Загрузка `.md`, `.txt`, `.pdf` в выбранный проект. Файл режется на фрагменты.
Поиск по фразе показывает ближайшие фрагменты. Удаление убирает документ
только из этого проекта. Эти фрагменты попадают в статью, когда на генерации
включена **База знаний**.

### Настройки

Четыре вкладки.

- **Подключения** — заданы ли ключи OpenAI, поиска и Яндекса, какая модель,
  включены ли картинки и Discovery. Сами ключи не показываются.
- **Проект** — название, домен, язык. Slug только для чтения.
- **Одна статья** — галочки и объём по умолчанию для одноимённого режима
  генерации.
- **Промпты** — текст файлов из `prompts/`. Только чтение.

---

## 6. Карта файлов и ответственность

### Корень репозитория

| Путь | За что отвечает |
| --- | --- |
| `PROJECT.md` | Продуктовые требования Stage 1–6 |
| `ARCHITECTURE.md` | Архитектурный blueprint |
| `README.md` | Порядок включения и API-сводка |
| `GUIDE.md` | Эта инструкция |
| `web/` | Панель оператора (Vite + React + MUI) |
| `pyproject.toml` | Зависимости, pytest, Ruff |
| `Dockerfile` | Образ приложения; миграции при старте |
| `docker-compose.yml` | Сервисы `app` + `postgres` (pgvector) + `n8n` |
| `.env.example` | Шаблон переменных (без реальных секретов) |
| `.env` | Локальные секреты (**не в git**) |
| `.gitignore` / `.dockerignore` | Исключения для git и Docker |
| `Makefile` | Команды разработки |
| `alembic.ini` | Конфиг Alembic |

### Приложение `app/`

| Путь | За что отвечает |
| --- | --- |
| `app/main.py` | Создание FastAPI-приложения, lifespan, exception handlers |
| `app/config.py` | Settings из env (`DATABASE_URL`, OpenAI, target word count…) |
| `app/api/router.py` | Сборка маршрутов |
| `app/api/deps.py` | DI: сессия БД, repository, AIWriter, Embedder, сервисы |
| `app/api/errors.py` | Маппинг доменных ошибок → HTTP 500/502 |
| `app/api/routes/health.py` | `GET /health` |
| `app/api/routes/articles.py` | `POST /api/v1/articles/generate` |
| `app/api/routes/documents.py` | CRUD / search базы знаний |
| `app/api/routes/research.py` | Research конкурентов |
| `app/api/routes/discovery.py` | Topic Discovery: SERP → контент-план |
| `app/api/routes/competitor_topics.py` | Импорт JSON-плана или xlsx/csv dumps → briefs |
| `app/schemas/articles.py` | Request/response API (ArticleGenerateRequest/Response) |
| `app/schemas/documents.py` | Request/response документов |
| `app/schemas/ai.py` | Вход/выход AI-слоя (ArticleWriteInput, AIArticleOutput) |
| `app/schemas/health.py` | Ответ health |
| `app/services/pipeline_service.py` | Оркестрация Stage 4: research → SEO → writer → fact-check → editor |
| `app/services/article_service.py` | Оркестрация генерации, RAG-контекст, статусы; опционально PipelineService, картинки, ссылки, качество, Дзен |
| `app/services/image_service.py` | Stage 5: плейсхолдер → ImageProvider → путь в markdown |
| `app/services/linking_service.py` | Stage 5: каталог статей → вставка внутренних ссылок |
| `app/services/dzen_service.py` | Stage 6: короткая Дзен-версия + 3 картинки |
| `app/services/quality_service.py` | Stage 6: детекторы, humanizer, summary |
| `app/services/ai/dzen_writer.py` | Протокол `DzenWriter` |
| `app/services/ai/detector.py` | Протокол `AiDetector` |
| `app/services/ai/humanizer.py` | Протокол `Humanizer` |
| `app/services/ai/summarizer.py` | Протокол `Summarizer` |
| `app/services/ai/openai_dzen.py` | Чат для Дзен-версии |
| `app/services/ai/openai_detector.py` | Чат для оценок стиля |
| `app/services/ai/openai_humanizer.py` | Чат «очеловечивания» |
| `app/services/ai/openai_summarizer.py` | Чат краткого содержания |
| `app/services/ai/mock_dzen.py` | Короткий черновик для тестов |
| `app/services/ai/mock_detector.py` | Фиксированные баллы для тестов |
| `app/services/ai/mock_humanizer.py` | Пометка черновика для тестов |
| `app/services/ai/mock_summarizer.py` | Короткий summary для тестов |
| `app/schemas/dzen.py` | Вход/выход Дзена |
| `app/schemas/quality.py` | Вход/выход качества |
| `app/services/ai/image_provider.py` | Протокол `ImageProvider` |
| `app/services/ai/openai_image.py` | OpenAI Images API |
| `app/services/ai/mock_image.py` | Крошечный PNG для тестов |
| `app/schemas/enrichment.py` | `ArticleAsset`, `InternalLinkRef` (без байтов) |
| `app/core/placeholders.py` | Разбор `IMAGE_PLACEHOLDER_N` / `INFOGRAPHIC_PLACEHOLDER_N` + контекст блока |
| `app/core/section_images.py` | Среднее число фото конкурентов → слоты по пунктам outline |
| `app/core/competitor_brief.py` | Средние объём / таблицы / FAQ / инфографика → поля brief |
| `app/core/competitor_filter.py` | Только статьи: без видео/витрин, ≥ 300 символов |
| `app/core/internal_links.py` | Детерминированная вставка ссылок (без AI, без SQL) |
| `app/services/ai/seo_agent.py` | Протокол `SeoAgent` |
| `app/services/ai/fact_checker.py` | Протокол `FactChecker` |
| `app/services/ai/editor.py` | Протокол `Editor` |
| `app/schemas/pipeline.py` | Вход/выход агентов и трасса `pipeline` |
| `app/services/document_service.py` | Ингест: parse → chunk → embed → persist |
| `app/services/rag_service.py` | Векторный поиск и сборка `knowledge_context` |
| `app/services/research_service.py` | SERP → структура страниц → улучшенный outline |
| `app/services/research/` | `SearchProvider`, Serper, page fetch |
| `app/services/discovery_service.py` | Снимки выдачи → кластеризация тем → export |
| `app/services/competitor_topics_service.py` | JSON-план или dumps → briefs → export |
| `app/services/ai/content_gap.py` | Протокол `ContentGapAnalyst` |
| `app/services/ai/openai_content_gap.py` | Кластеризация hits через чат |
| `app/services/ai/mock_content_gap.py` | Детерминированный план из hits для тестов |
| `app/services/discovery/` | `SerpSnapshotProvider`, Serper snapshot, Yandex SerpAPI |
| `app/services/ai/topic_planner.py` | Протокол `TopicPlanner` |
| `app/schemas/discovery.py` | Снимок SERP, brief плана, API discovery |
| `app/schemas/competitor_topics.py` | Импорт JSON-плана и ContentGap I/O |
| `app/core/topic_candidates.py` | Нормализация и дедуп кандидатов (без AI) |
| `app/core/competitor_plan.py` | Маппинг content-plan JSON → briefs для topics.json |
| `app/core/competitor_sources.py` | Парсер xlsx/csv/txt/json выгрузок (без openpyxl) |
| `app/repositories/discovery_repository.py` | `content_plans` / `content_plan_topics` |
| `app/db/models/discovery.py` | ORM контент-плана |
| `app/services/ai/analyst.py` | Протокол `CompetitorAnalyst` |
| `app/services/ai/base.py` | Протокол `AIWriter` |
| `app/services/ai/embedder.py` | Протокол `Embedder` |
| `app/services/ai/openai_writer.py` | Реальный вызов провайдера (чат) |
| `app/services/ai/openai_embedder.py` | Реальный вызов провайдера (эмбеддинги) |
| `app/services/ai/mock_writer.py` | Детерминированный writer для тестов |
| `app/services/ai/mock_embedder.py` | Детерминированные эмбеддинги для тестов |
| `app/services/ai/prompt_loader.py` | Чтение и рендер промптов |
| `app/repositories/article_repository.py` | CRUD по таблице `articles` (без бизнес-логики) |
| `app/repositories/document_repository.py` | Документы, чанки, cosine search |
| `app/db/session.py` | Async engine / session / проверка БД |
| `app/db/models/article.py` | ORM-модель Article + enum статусов |
| `app/db/models/document.py` | ORM-модели Document и Chunk |
| `app/core/document_parser.py` | Извлечение текста из md/txt/pdf |
| `app/core/chunking.py` | Нарезка текста на пересекающиеся чанки |
| `app/db/models/base.py` | Declarative Base |
| `app/core/exceptions.py` | Доменные исключения |
| `app/core/word_count.py` | Подсчёт слов в markdown |
| `app/core/article_file.py` | Сохранение статьи в `.md`, `.html` и опционально `images/`, `dzen.*`, `summary.md` |
| `app/core/quality.py` | Пороги вердикта детектора (без AI) |
| `app/core/markdown_html.py` | Конвертация Markdown → HTML, блок `.toc` из H2 |
| `output/articles/` | Папки статей: `article.md|html`, `stage3_generate.json`, при Stage 3 `competitors.txt` + `research.md` + `stage3_research.json`, при Stage 5 `images/` |

### Промпты, миграции, n8n, тесты

| Путь | За что отвечает |
| --- | --- |
| `prompts/article_writer.md` | Статья одним запросом |
| `prompts/article_meta.md` | SEO-обёртка для посекционного режима |
| `prompts/article_section.md` | Один раздел статьи |
| `prompts/article_expand.md` | Добор объёма короткого черновика |
| `prompts/article_writer_system.md` | System-промпт |
| `prompts/seo_brief.md` | SEO-агент (Stage 4) |
| `prompts/fact_check.md` | Фактчекер (Stage 4) |
| `prompts/article_editor.md` | Редактор после фактчека (Stage 4) |
| `prompts/image_generate.md` | Промпт кадра для OpenAI Images (Stage 5) |
| `prompts/dzen_article.md` | Короткая статья для Дзена (Stage 6) |
| `prompts/topic_discovery.md` | Кластеризация тем из выдачи |
| `prompts/competitor_gap.md` | Контент-план из выгрузок конкурентов |
| `prompts/ai_detector.md` | Оценки AI-likeness / уникальности стиля (Stage 6) |
| `prompts/article_humanizer.md` | «Очеловечивание» черновика (Stage 6) |
| `prompts/article_summary.md` | Краткое содержание (Stage 6) |
| `app/services/ai/section_plan.py` | Разбивка brief на разделы и бюджеты слов |
| `topics/topics.json` | Рабочая очередь тем для пакетной генерации |
| `topics/topics.example.*` | Шаблоны формата (не для generate) |
| `topics/content-plan-*.json` | Сырьё competitor `--plan`, не очередь generate |
| `scripts/build_topics.py` | Переключатель: Discovery или файлы конкурентов → topics.json |
| `scripts/generate_from_topics.py` | Клиент: файл → HTTP API |
| `scripts/export_content_plan.py` | Клиент: GET плана → merge в topics.json |
| `scripts/import_competitor_plan.py` | Клиент: content-plan JSON → merge в topics файл |
| `alembic/versions/0001_create_articles.py` | Создание таблицы `articles` |
| `alembic/versions/0002_add_url_slug.py` | Колонка `url_slug` |
| `alembic/versions/0003_knowledge_base.py` | pgvector, таблицы `documents` и `chunks` |
| `alembic/versions/0004_competitor_research.py` | таблицы `research_runs` и `research_competitors` |
| `alembic/versions/0005_article_pipeline.py` | колонка `articles.pipeline` (трасса агентов) |
| `alembic/versions/0006_article_assets.py` | колонки `articles.assets` и `articles.internal_links` |
| `alembic/versions/0007_article_dzen.py` | колонка `articles.dzen` |
| `alembic/versions/0008_article_quality.py` | колонка `articles.quality` |
| `alembic/versions/0009_article_competitor_sources.py` | колонка `articles.competitor_sources` |
| `alembic/versions/0010_section_images.py` | слоты картинок по разделам outline |
| `alembic/versions/0011_content_plans.py` | таблицы `content_plans` / `content_plan_topics` |
| `alembic/versions/0012_competitor_topics.py` | `source` плана и метаданные тем конкурентов |
| `alembic/env.py` | Async env для миграций |
| `n8n/workflows/stage1_generate_article.json` | Workflow: Manual Trigger → HTTP → Result |
| `scripts/smoke_openai.py` | Ручная проверка провайдера (не в pytest) |
| `tests/unit/` | Юнит-тесты (сервис, AI, схемы, архитектура, n8n) |
| `tests/api/` | HTTP-тесты эндпоинтов |
| `tests/integration/` | Тесты с реальной PostgreSQL |
| `tests/db_setup.py` | Создание/миграция отдельной БД `acf_test` |
| `tests/conftest.py` | Фикстуры pytest |
| `.github/workflows/ci.yml` | CI: ruff + pytest на каждый push |

### Правила слоёв (кратко)

1. **API** — только HTTP, валидация, DI. Без OpenAI, без SQL, без SERP/image HTTP
   (в том числе снимки Google/Яндекс для discovery).
2. **Service** — бизнес-логика и статусы.
3. **AI** (`app/services/ai/`) — единственное место вызова чата, эмбеддингов и картинок.
4. **Repository** — только PostgreSQL.

---

## 7. Как сгенерировать статью на практике

### Вариант A — Swagger

1. Открыть <http://localhost:8000/docs>
2. `POST /api/v1/articles/generate` → Try it out
3. Ввести `topic` (и опционально language / audience / keywords)
4. Execute → в Response Body будет `content_markdown`

### Вариант B — curl

См. раздел 5.

### Вариант C — n8n

Полная пошаговая инструкция (запуск контейнера, импорт, URL, ошибки):
[`n8n/README.md`](n8n/README.md).

### Вариант D — темы из файла

1. Отредактировать [`topics/topics.json`](topics/topics.json) в формате brief
   (`topic`, `word_count`, `primary_keywords`, `outline`, `use_dzen`, …)
2. Убедиться, что API запущен (`make up`)
3. Запустить:

```bash
make generate-topics
```

Скрипт шлёт каждый объект как тело `POST /api/v1/articles/generate`.
Промпт [`prompts/article_writer.md`](prompts/article_writer.md) подставляет
поля brief (включая весь JSON-план как `{{brief_json}}`).

Пример формата: [`topics/topics.example.json`](topics/topics.example.json).
Простой `.txt` (одна тема на строку) тоже поддерживается.
Список тем собирают переключателем режимов: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics)
(Discovery или файлы конкурентов).

---

## 8. Как изменить поведение генерации

| Задача | Что править |
| --- | --- |
| Список тем для пакетной генерации | `topics/topics.json`; режим сбора — [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics) |
| Текст/структура статьи | `prompts/article_writer.md`, `prompts/article_section.md` |
| System-инструкция JSON | `prompts/article_writer_system.md` |
| Модель / temperature / max tokens | `.env` → `OPENAI_*` |
| Целевой объём | `.env` → `ARTICLE_TARGET_WORD_COUNT` |
| Число разделов и их объём | `outline` в brief без research; с research — план и объём из анализа |
| Добор объёма | `.env` → `ARTICLE_MIN_WORD_RATIO`, `ARTICLE_EXPAND_ATTEMPTS` |
| Уровень логов | `.env` → `LOG_LEVEL` (`docker compose logs -f app`) |
| Материалы для RAG | `POST /api/v1/documents` или `/upload` |
| Число чанков в промпте | `.env` → `RAG_TOP_K` |
| Выключить базу знаний | `.env` → `RAG_ENABLED=false` или `"use_knowledge_base": false` |
| Мультиагенты (SEO / фактчек / редактор) | `"use_multi_agent": true` в generate |
| Картинки вместо плейсхолдеров | `"use_images": true` в generate |
| Только текст / только картинки | `"use_text"` + `"use_images"`; картинки: `POST /articles/{id}/images` |
| Выключить перелинковку | `"use_internal_links": false` |
| Короткая версия для Дзена | `"use_dzen": true` в generate / topics.json; выкл.: `false` или `DZEN_ENABLED=false` |
| Детекторы стиля | `"use_detectors": true` в generate |
| «Очеловечить» черновик | `"use_humanizer": true` в generate |
| Краткое содержание | `"use_summary": true` в generate |
| Валидация полей ответа AI | `app/schemas/ai.py` |
| Статусы и сохранение | `app/services/article_service.py` |
| Формат HTTP-запроса/ответа | `app/schemas/articles.py` |

После смены переменных в `.env`:

```bash
docker compose up -d --force-recreate app
```

После правки промптов (том смонтирован) — достаточно нового запроса generate.

---

## 9. Тесты и проверка провайдера

```bash
make test    # pytest: MockAIWriter / MockEmbedder, БД acf_test (не трогает рабочие статьи)
make lint
```

Ручной smoke реального провайдера (тратит кредиты):

```bash
docker compose run --rm -e PYTHONPATH=/app -v ${PWD}/scripts:/app/scripts \
  --entrypoint python app scripts/smoke_openai.py
```

---

## 10. Частые вопросы

**Где «файл» готовой статьи?**  
Его нет. Статья в колонке `articles.content_markdown` и в JSON-ответе API.

**Можно ли править промпт без пересборки Docker?**  
Да: `./prompts` смонтирован в контейнер. Достаточно сохранить файл и вызвать generate снова.

**Почему word_count не совпадает с ответом модели?**  
Бэкенд всегда пересчитывает `word_count` сам из `content_markdown` (`app/core/word_count.py`). Число от модели игнорируется.

**Тесты стёрли статьи?**  
Нет. Pytest работает с отдельной БД `acf_test`. Рабочая БД `acf` не трогается.

**Ключ API попал в git?**  
Не должен. Секреты только в `.env`. Workflow n8n и исходники ключей не содержат.

**Статья не использует загруженные документы?**  
Проверьте: документ `status: ready` и `chunk_count` > 0; `RAG_ENABLED=true`;
в запросе нет `"use_knowledge_base": false`; поиск по той же теме возвращает
чанки. На OpenRouter задайте `OPENAI_EMBEDDING_MODEL=openai/text-embedding-3-small`.

**Откуда взять список тем для `topics.json`?**  
Переключатель режимов: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics).
Discovery — `make topics-discovery`; файлы конкурентов —
`make topics-competitors`. Generate после этого: `make generate-topics`.

**Откуда в статье берутся конкуренты?**  
Из органики Google через Serper (`POST /api/v1/research` или
`"use_competitor_research": true`). Не из базы знаний и не из Яндекса.
YouTube, маркетплейсы, витрины и страницы короче 300 символов отбрасываются.
Подробно: [§5.2](#52-конкуренты--seo-stage-3--как-это-работает).

**Как включить мультиагентов?**  
`"use_multi_agent": true` в generate. Появится `pipeline` в ответе.
Подробно: [§5.3](#53-мультиагенты-stage-4--как-это-работает).

**Как получить реальные картинки?**  
`"use_images": true`. Нужен `OPENAI_API_KEY` с доступом к Images API.
Сбой кадра не валит статью. Подробно: [§5.4](#54-картинки-и-перелинковка-stage-5).

**Откуда внутренние ссылки?**  
Из других completed-статей того же языка с `url_slug` и `title`. По умолчанию
включено; выключить: `"use_internal_links": false`.

**Как получить версию для Дзена?**  
`"use_dzen": true`. Та же статья, меньше символов, 3 картинки (обложка + две
в тексте) при `"use_images": true`. Подробно: [§5.5](#55-дзен-stage-6).

**Как включить детекторы / Humanizer / summary?**  
`"use_detectors": true`, `"use_humanizer": true`, `"use_summary": true`.
Это эвристика своего чата, не Copyscape / GPTZero. Подробно: [§5.6](#56-детекторы-humanizer-и-summary-stage-6).

---

## 11. Что осталось сделать

Stage 1–6 **в коде готовы**. Ниже — шаги, которые ещё за вами, и этапы
продукта, которые ещё не реализованы.

### А. Чтобы начать пользоваться базой знаний

1. **Дописать `.env`**, если копировали его до Stage 2: блок `OPENAI_EMBEDDING_MODEL`
   / `RAG_*` из [`.env.example`](.env.example). На OpenRouter — модель
   `openai/text-embedding-3-small`. Затем `docker compose up -d --force-recreate app`.
2. **Загрузить свои материалы** (`POST /api/v1/documents` или `/upload`) — без
   документов RAG ничего не добавит в промпт.
3. **Проверить поиск** (`POST /api/v1/documents/search`) по формулировке темы.
   Пустой ответ = эмбеддинги не работают или база пуста.
4. **Сгенерировать статью** как обычно (`generate` или `make generate-topics`).
   Убедиться по тексту, что факты из документов попали в статью.
5. **Старый том Postgres** `postgres_data` (Stage 1, alpine) больше не
   используется. Строки статей из него сами не переедут. Файлы в
   `output/articles/` остаются. Том можно удалить позже, когда старые строки
   в БД точно не нужны (`docker volume ls` → `docker volume rm …`). Не
   удаляйте `postgres_pgvector_data`.

### А2. Чтобы включить Stage 3 (конкуренты)

1. Зарегистрироваться в Serper и прописать `SERP_API_KEY` в `.env`.
2. `docker compose up -d --force-recreate app` (подтянется миграция `0004`).
3. `POST /api/v1/research` по теме, затем generate с `research_id`
   или сразу `"use_competitor_research": true`.

### А3. Чтобы включить Stage 4 (мультиагенты)

1. `docker compose up -d --force-recreate app` (подтянется миграция `0005`).
2. Generate с `"use_multi_agent": true`. Нужен `OPENAI_API_KEY`; `SERP_API_KEY`
   желателен (без него шаг research пропускается).
3. В ответе смотрите `pipeline.steps` — все пять шагов и вердикт фактчека.

### А4. Чтобы включить Stage 5 (картинки и ссылки)

1. `docker compose up -d --force-recreate app` (подтянется миграция `0006`).
2. Для картинок: `"use_images": true` и рабочий `OPENAI_API_KEY` (Images API).
   Без ключа плейсхолдеры остаются, статья всё равно `completed`.
3. Перелинковка работает сама, когда в БД уже есть другие completed-статьи
   с `url_slug`. Первая статья в каталоге ссылок не получит.

### А5. Чтобы включить Дзен

1. `docker compose up -d --force-recreate app` (подтянется миграция `0007`).
2. Generate с `"use_dzen": true`. Для трёх реальных картинок добавьте
   `"use_images": true`.
3. В ответе смотрите `dzen.title`, `dzen.content_markdown`, `dzen.char_count`.
   В папке статьи появятся `dzen.md` и `dzen.html`.

### А6. Чтобы включить качество (детекторы / Humanizer / summary)

1. `docker compose up -d --force-recreate app` (подтянется миграция `0008`).
2. Generate с нужными флагами: `"use_detectors": true`, `"use_humanizer": true`,
   `"use_summary": true`. Все три по умолчанию выключены.
3. В ответе смотрите `quality.detectors.verdict`, `quality.humanizer.applied`,
   `quality.summary.text`. При summary в папке статьи появится `summary.md`.
   Это не проверка интернета и не GPTZero.

### А7. Темы из файлов конкурентов (подшаг 1)

1. `docker compose up -d --force-recreate app` (подтянется миграция `0012`).
2. Загрузить `knowledge/<проект>-brief.md`
   в базу знаний (`POST /api/v1/documents/upload`).
3. Сырьё: `POST /api/v1/competitor-topics/sources` с xlsx/csv/txt.
   Или готовый план: `POST /api/v1/competitor-topics` (или `/upload`) с
   `content-plan-*.json`. Затем `POST /api/v1/competitor-topics/{id}/export`.
4. Без API (только JSON): `python scripts/import_competitor_plan.py … --topics-file topics/topics.json`.
5. Generate по-прежнему из `topics/` + Stage 3 research.

### Б. Следующие этапы продукта (ещё не в коде)

Полная таблица — [PROJECT.md](PROJECT.md) §2 и §15. Кратко:

| Когда | Что осталось |
| --- | --- |
| **CLI** | Переключатель Discovery / Competitor topics (`scripts/build_topics.py`) |
| **Отложено** | Несколько проектов ([§11.Е](#е-план-несколько-проектов)) |
| **Stage 7** | n8n: HTML-упаковка, расписание (не бизнес-логика generate) |
| **Stage 8a** | F0–F5 сделаны ([§5.7](#57-панель-оператора-stage-8a)) |
| **Stage 8** | Ревью, CMS, публикация |
| **Stage 9** | Аналитика и оптимизация после публикации |

Это **не** делать без отдельного задания: Redis/Kafka,
auth/биллинг, Kubernetes. Фронт — только по плану Stage 8a (F2–F5).

### В. Необязательные доработки Stage 2 (только по заданию)

- таблица источников / цитирование чанков в ответе API;
- смена размерности эмбеддингов (нужна миграция);
- пересчёт эмбеддингов при смене модели;
- workflow n8n на загрузку документов.

### Г. Переключатель источника тем (CLI)

Сделано. Как переключать: [§5.2c](#52c-как-переключать-режимы-discovery--competitor-topics).
n8n не используется. Generate по-прежнему отдельно (`make generate-topics`).

### Д. План операторского UI

Не CMS. **Сделано F0–F5:** каталог, темы, база, generate и ревью
(`PATCH /api/v1/articles/{id}/review`). Как запустить:
[§5.7](#57-панель-оператора-stage-8a).

Полный план: [PROJECT.md §15 «План: операторский UI»](PROJECT.md).

### Е. Несколько проектов

Сделано. У каждого проекта свои документы, статьи, research, контент-планы
и внутренние ссылки. Рабочие запросы передают `X-Project-Id` или
`X-Project-Slug`. Без заголовка — 422. CLI: `--project slug` (или
`ACF_PROJECT`), без флага это `default` и прежний `topics/topics.json`.
В UI проект выбирается в боковой панели. Ключи провайдеров остаются в `.env`.

Полный план: [PROJECT.md §15 «План: несколько проектов»](PROJECT.md).
