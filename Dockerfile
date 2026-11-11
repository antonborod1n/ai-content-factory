FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY tests ./tests
COPY alembic ./alembic
COPY prompts ./prompts
COPY n8n ./n8n
COPY topics/topics.example.json topics/topics.example.txt ./topics/
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

EXPOSE 8000

# One uvicorn process only: on startup recovery marks interrupted work failed.
# Do not pass --workers > 1 — a second process would kill the first's jobs.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
