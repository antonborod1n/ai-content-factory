# n8n в AI Content Factory (Stage 1)

Пошаговая инструкция: как поднять n8n вместе со стеком проекта и
сгенерировать статью через готовый workflow.

## 1. Зачем нужен n8n

n8n — **тонкий клиент**, не генератор статей.

```text
Manual Trigger
  → параметры темы
  → POST /api/v1/articles/generate
  → показать результат или ошибку
```

| Делает n8n | Не делает n8n |
| --- | --- |
| Запуск по кнопке | Вызов OpenAI / OpenRouter |
| Передача topic / language / audience / keywords | Промпты и бизнес-логика |
| Ветвление по HTTP-статусу | Запись в PostgreSQL |
| Показ ответа API | Подсчёт `word_count` |

Секреты провайдера и БД живут только в `.env` бэкенда. В workflow и в env
сервиса `n8n` их быть не должно.

Готовый экспорт: [`workflows/stage1_generate_article.json`](workflows/stage1_generate_article.json).

```text
Manual Trigger
  → Set Article Parameters
  → Generate Article (HTTP)
  → IF Success
       → Result
       → Error Result
```

## 2. Предусловия

1. Скопирован и заполнен `.env` (`POSTGRES_PASSWORD`, `DATABASE_URL`, `OPENAI_API_KEY`, …).
2. Опционально: порт и URL UI n8n в `.env` (см. `.env.example`: `N8N_PORT`, `N8N_WEBHOOK_URL`).

## 3. Запуск n8n (Compose)

Сервис `n8n` входит в [`docker-compose.yml`](../docker-compose.yml). Поднимается
вместе с `app` и `postgres`:

```powershell
cd C:\Users\User\Desktop\ai-content-factory
docker compose up --build -d
```

Или: `make up`.

Проверь API:

```powershell
curl.exe http://localhost:8000/health
```

Ожидается: `{"status":"ok","database":"ok"}`.

UI n8n: <http://localhost:5678> (или порт из `N8N_PORT`).

При первом входе создай локальный аккаунт владельца (email + пароль). Данные
хранятся в томе Compose `n8n_data`.

Логи:

```powershell
docker compose logs -f n8n
```

Если порт `5678` занят — задай в `.env`, например `N8N_PORT=5679`, и
пересоздай сервис: `docker compose up -d n8n`.

## 4. Импорт workflow

1. В n8n: **Workflows** → меню (⋯) → **Import from File**.
2. Выбери файл:

```text
n8n/workflows/stage1_generate_article.json
```

(полный путь от корня репозитория).

3. Должна появиться цепочка из шести узлов: Manual Trigger, Set Article
   Parameters, Generate Article, IF Success, Result, Error Result.

## 5. URL к API

В экспорте у узла **Generate Article** стоит URL для **той же Compose-сети**:

`http://app:8000/api/v1/articles/generate`

Его менять не нужно, если n8n запущен через `docker compose` этого проекта.

| Где запущен n8n | URL |
| --- | --- |
| В этом Compose (рекомендуется) | `http://app:8000/api/v1/articles/generate` |
| Отдельный Docker на Windows / macOS | `http://host.docker.internal:8000/api/v1/articles/generate` |
| На хосте (не в контейнере) | `http://localhost:8000/api/v1/articles/generate` |

`localhost` внутри контейнера n8n — это сам n8n, а не API.

Таймаут в workflow уже **180 секунд**. Параметры `neverError` и `fullResponse`
включены, чтобы ветка **Error Result** работала при 4xx/5xx.

## 6. Параметры статьи

Открой узел **Set Article Parameters** и задай:

| Поле | Обязательно | По умолчанию на бэкенде |
| --- | --- | --- |
| `topic` | да | — |
| `language` | нет | `ru` |
| `audience` | нет | `general` |
| `keywords` | нет | `[]` |

Полный brief из `topics/topics.json` в этом Stage 1 workflow **не обязателен**:
бэкенд подставит дефолты.

## 7. Запуск

Нажми **Execute Workflow**.

**Успех (HTTP 200):** IF уходит в **Result** (`id`, `status`, `title`,
`meta_description`, `url_slug`, `content_markdown`, `word_count`).

**Ошибка:** IF уходит в **Error Result**.

## 8. Где смотреть готовую статью

1. Узел **Result** в n8n.
2. **База:**

```powershell
docker compose exec postgres psql -U acf -d acf -c "SELECT id, status, word_count, left(title, 50) FROM articles ORDER BY created_at DESC LIMIT 3;"
```

3. **Файлы:** `output/articles/{uuid}_{slug}/article.md` и `article.html`.

## 9. Типичные ошибки

| Симптом | Что проверить |
| --- | --- |
| `ECONNREFUSED` / connection error | URL должен быть `http://app:8000/...` в Compose. `docker compose ps` — сервисы `app` и `n8n` healthy/up? |
| HTTP **422** | Пустой или пробельный `topic` |
| HTTP **502** | Провайдер / JSON модели — `docker compose logs app` |
| HTTP **500** | Внутренняя ошибка / нет ключа — логи `app` |
| Долго висит / timeout | Timeout HTTP-узла ≥ 180000 мс |
| Порт 5678 занят | `N8N_PORT` в `.env` |

## 10. Чего нельзя делать в n8n

- Класть `OPENAI_API_KEY`, пароли БД, connection strings в workflow или env `n8n`.
- Писать промпты и вызывать OpenAI из Code / AI-нод.
- Считать `word_count` или писать в PostgreSQL из n8n.
- Дублировать бизнес-логику `ArticleService`.

## 11. Остановка

Остановить весь стек (том `n8n_data` сохранится):

```powershell
docker compose down
```

Только n8n:

```powershell
docker compose stop n8n
```

Удалить том n8n (сотрёт owner-аккаунт и импортированные workflows):

```powershell
docker compose down
docker volume rm ai-content-factory_n8n_data
```

Имя тома может отличаться (`docker volume ls | findstr n8n`).

## 12. Что дальше (Stage 7)

Сейчас n8n — ручной запуск одной генерации. Позже: расписание, цепочки,
доставка HTML — см. [`.cursor/rules/future-n8n-html-export.mdc`](../.cursor/rules/future-n8n-html-export.mdc).

## Связанные документы

- [GUIDE.md](../GUIDE.md) — карта проекта и поток генерации
- [README.md](../README.md) — быстрый старт
- [PROJECT.md](../PROJECT.md) §10 — требования к n8n
- [ARCHITECTURE.md](../ARCHITECTURE.md) §10 — контракт n8n ↔ backend
