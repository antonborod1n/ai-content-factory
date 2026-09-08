# Инструкция по работе с AI Content Factory (Stage 1)

Практическое руководство: что где лежит, куда писать промпты, куда попадает готовая статья и как устроен полный цикл генерации.

Связанные документы:

- [PROJECT.md](PROJECT.md) — требования Stage 1
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура
- [README.md](README.md) — быстрый старт

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

## 2. Быстрый старт

```bash
cp .env.example .env
# Заполнить: POSTGRES_PASSWORD, DATABASE_URL, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL

docker compose up --build -d
curl http://localhost:8000/health
# → {"status":"ok","database":"ok"}
```

Swagger UI: <http://localhost:8000/docs>  
n8n UI: <http://localhost:5678> (инструкция: [`n8n/README.md`](n8n/README.md))

Полезные команды (`Makefile`):

| Команда | Что делает |
| --- | --- |
| `make up` | Поднять app + postgres + n8n |
| `make down` | Остановить |
| `make logs` | Логи контейнеров |
| `make test` | pytest |
| `make lint` | Ruff |
| `make migrate` | Alembic upgrade |

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

### Два режима генерации

| Когда | Что происходит | Типичный объём |
| --- | --- | --- |
| В brief есть `outline` (≥ 2 пунктов) | `article_meta.md` + по одному запросу на каждый раздел (`article_section.md`) | близко к `word_count` |
| `outline` пустой (например, запуск из n8n) | один запрос `article_writer.md` + до `ARTICLE_EXPAND_ATTEMPTS` доборов `article_expand.md` | ~1000–1300 слов на `gpt-4o-mini` |

Причина: небольшие модели обрывают ответ примерно на тысяче слов, сколько ни
проси в промпте. Поэтому длинная статья пишется по разделам.

Плейсхолдеры в промптах:

```text
{{topic}} {{language}} {{audience}} {{tone}} {{cta}}
{{word_count}} {{words_per_section}} {{brief_json}}
{{section_title}} {{section_index}} {{section_count}} {{section_word_count}}
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
| `OPENAI_MAX_TOKENS` | Лимит ответа | `8000` |
| `ARTICLE_TARGET_WORD_COUNT` | Целевой объём (в промпт) | `3000` |
| `ARTICLE_MIN_WORD_RATIO` | Доля цели, ниже которой черновик добирается | `0.8` |
| `ARTICLE_EXPAND_ATTEMPTS` | Сколько доборов делать (0 — выключить) | `2` |

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
output/articles/{uuid}_{slug-темы}/
  article.md
  article.html
```

- папка на каждую статью (статьи не свалены в один каталог)
- `.md` — исходник (YAML front matter + `content_markdown`)
- `.html` — простая HTML-страница, сконвертированная из Markdown на бэкенде
  (не AI). Позже экспорт HTML планируется вынести в n8n
  (см. `.cursor/rules/future-n8n-html-export.mdc`).

Открой файлы в редакторе или:

```powershell
Get-ChildItem output\articles -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

Пустой `ARTICLES_OUTPUT_DIR=` отключает запись на диск (статья остаётся только в БД).

### Что ещё имеет смысл позже (не Stage 1)

* **Humanizer / AI-rewriter** — отдельный шаг «очеловечивания» после генерации
  (Stage 9, рядом с детекторами).
* **Детекторы AI / уникальности** — п. 8 пайплайна (Stage 9).
* **Краткое содержание (summary)** — п. 9 (Stage 9).
* **Дзен-версия** — п. 6 (Stage 1.1 или 9).
* В Stage 1 достаточно сильных правил «живого» языка в
  `prompts/article_writer.md`; сторонние Humanizer API не подключаем.

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

## 6. Карта файлов и ответственность

### Корень репозитория

| Путь | За что отвечает |
| --- | --- |
| `PROJECT.md` | Продуктовые требования Stage 1 |
| `ARCHITECTURE.md` | Архитектурный blueprint |
| `README.md` | Быстрый старт и API-сводка |
| `GUIDE.md` | Эта инструкция |
| `pyproject.toml` | Зависимости, pytest, Ruff |
| `Dockerfile` | Образ приложения; миграции при старте |
| `docker-compose.yml` | Сервисы `app` + `postgres` |
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
| `app/api/deps.py` | DI: сессия БД, repository, AIWriter, ArticleService |
| `app/api/errors.py` | Маппинг доменных ошибок → HTTP 500/502 |
| `app/api/routes/health.py` | `GET /health` |
| `app/api/routes/articles.py` | `POST /api/v1/articles/generate` |
| `app/schemas/articles.py` | Request/response API (ArticleGenerateRequest/Response) |
| `app/schemas/ai.py` | Вход/выход AI-слоя (ArticleWriteInput, AIArticleOutput) |
| `app/schemas/health.py` | Ответ health |
| `app/services/article_service.py` | Оркестрация генерации и статусов |
| `app/services/ai/base.py` | Протокол `AIWriter` |
| `app/services/ai/openai_writer.py` | Реальный вызов провайдера |
| `app/services/ai/mock_writer.py` | Детерминированный writer для тестов |
| `app/services/ai/prompt_loader.py` | Чтение и рендер промптов |
| `app/repositories/article_repository.py` | CRUD по таблице `articles` (без бизнес-логики) |
| `app/db/session.py` | Async engine / session / проверка БД |
| `app/db/models/article.py` | ORM-модель Article + enum статусов |
| `app/db/models/base.py` | Declarative Base |
| `app/core/exceptions.py` | Доменные исключения |
| `app/core/word_count.py` | Подсчёт слов в markdown |
| `app/core/article_file.py` | Сохранение статьи в `.md` и `.html` |
| `app/core/markdown_html.py` | Конвертация Markdown → HTML |
| `output/articles/` | Папки статей: `{id}_{slug}/article.md|html` |

### Промпты, миграции, n8n, тесты

| Путь | За что отвечает |
| --- | --- |
| `prompts/article_writer.md` | Статья одним запросом |
| `prompts/article_meta.md` | SEO-обёртка для посекционного режима |
| `prompts/article_section.md` | Один раздел статьи |
| `prompts/article_expand.md` | Добор объёма короткого черновика |
| `prompts/article_writer_system.md` | System-промпт |
| `app/services/ai/section_plan.py` | Разбивка brief на разделы и бюджеты слов |
| `topics/topics.json` | Список тем для пакетной генерации |
| `topics/topics.example.*` | Примеры форматов списка тем |
| `scripts/generate_from_topics.py` | Клиент: файл → HTTP API |
| `alembic/versions/0001_create_articles.py` | Создание таблицы `articles` |
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

1. **API** — только HTTP, валидация, DI. Без OpenAI и без SQL.
2. **Service** — бизнес-логика и статусы.
3. **AI** (`app/services/ai/`) — единственное место вызова провайдера.
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
   (`topic`, `word_count`, `primary_keywords`, `outline`, …)
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

---

## 8. Как изменить поведение генерации

| Задача | Что править |
| --- | --- |
| Список тем для пакетной генерации | `topics/topics.json` или `topics/*.txt` |
| Текст/структура статьи | `prompts/article_writer.md`, `prompts/article_section.md` |
| System-инструкция JSON | `prompts/article_writer_system.md` |
| Модель / temperature / max tokens | `.env` → `OPENAI_*` |
| Целевой объём | `.env` → `ARTICLE_TARGET_WORD_COUNT` |
| Число разделов и их объём | `outline` в brief (`topics/topics.json`) |
| Добор объёма | `.env` → `ARTICLE_MIN_WORD_RATIO`, `ARTICLE_EXPAND_ATTEMPTS` |
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
make test    # 86+ тестов, MockAIWriter, БД acf_test (не трогает рабочие статьи)
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
