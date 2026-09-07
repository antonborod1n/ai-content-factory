"""Manual smoke check: performs ONE real OpenAI call via OpenAIWriter.

Not part of the test suite. Requires OPENAI_API_KEY and costs API credits.

Run:
    docker compose run --rm -e PYTHONPATH=/app -v ${PWD}/scripts:/app/scripts \
        --entrypoint python app scripts/smoke_openai.py
"""

import asyncio
import re
import sys

from app.core.exceptions import AIError
from app.schemas.ai import ArticleWriteInput
from app.services.ai.openai_writer import OpenAIWriter

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


def _sanitize(text: str) -> str:
    return _SECRET_RE.sub("sk-***", text)


async def main() -> int:
    writer = OpenAIWriter()
    print(f"model: {writer.model}")
    print(f"configured: {writer.is_configured}")

    request = ArticleWriteInput(
        topic="Как выбрать промышленный насос",
        language="ru",
        audience="Инженеры и закупщики",
        keywords=["промышленный насос", "как выбрать насос"],
    )

    try:
        result = await writer.generate(request)
    except AIError as exc:
        print(f"AI error: {_sanitize(str(exc))}", file=sys.stderr)
        cause = exc.__cause__
        if cause is not None:
            detail = _sanitize(f"{type(cause).__name__}: {cause}")
            print(f"cause: {detail[:500]}", file=sys.stderr)
        return 1

    print(f"title: {result.title}")
    print(f"meta_description: {result.meta_description}")
    print(f"reported word_count: {result.word_count}")
    print(f"actual words in markdown: {len(result.content_markdown.split())}")
    print("--- content_markdown (first 600 chars) ---")
    print(result.content_markdown[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
