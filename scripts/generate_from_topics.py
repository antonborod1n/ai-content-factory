"""Generate articles from a topics file via the HTTP API.

This script is a thin client: it does not call OpenAI, write prompts, or touch
the database. All generation stays in the backend.

Supported formats: see ``app.core.topics_file.load_topics``.

Examples::

    # From the host (API must be on localhost:8000):
    python scripts/generate_from_topics.py topics/topics.json

    # Inside Compose (API reachable as service ``app``):
    docker compose run --rm \\
      -e PYTHONPATH=/app -e API_BASE_URL=http://app:8000 \\
      -v ${PWD}/scripts:/app/scripts -v ${PWD}/topics:/app/topics \\
      --entrypoint python app scripts/generate_from_topics.py topics/topics.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.topics_file import load_topics

DEFAULT_API_BASE_URL = "http://localhost:8000"
GENERATE_PATH = "/api/v1/articles/generate"


def generate_article(
    *,
    api_base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    url = api_base_url.rstrip("/") + GENERATE_PATH
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate articles from a topics file via the HTTP API"
    )
    parser.add_argument(
        "topics_file",
        type=Path,
        help="Path to topics.json / topics.txt (see topics/*.example.*)",
    )
    parser.add_argument(
        "--api-base-url",
        default=None,
        help=(
            "Backend base URL "
            f"(default: env API_BASE_URL or {DEFAULT_API_BASE_URL})"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-request timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Abort on the first failed topic (default: continue)",
    )
    args = parser.parse_args(argv)

    path = args.topics_file
    if not path.is_file():
        print(f"Topics file not found: {path}", file=sys.stderr)
        return 2

    try:
        topics = load_topics(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to read topics: {exc}", file=sys.stderr)
        return 2

    api_base_url = (
        args.api_base_url
        or os.environ.get("API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )

    print(f"api: {api_base_url.rstrip('/')}{GENERATE_PATH}")
    print(f"topics: {len(topics)} from {path}")

    failures = 0
    for index, payload in enumerate(topics, start=1):
        topic = payload["topic"]
        print(f"[{index}/{len(topics)}] {topic}")
        try:
            result = generate_article(
                api_base_url=api_base_url,
                payload=payload,
                timeout_seconds=args.timeout,
            )
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            print(f"  FAILED HTTP {exc.code}: {detail}", file=sys.stderr)
            failures += 1
            if args.stop_on_error:
                return 1
            continue
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failures += 1
            if args.stop_on_error:
                return 1
            continue

        status = result.get("status")
        article_id = result.get("id")
        word_count = result.get("word_count")
        title = result.get("title")
        print(f"  status={status} id={article_id} words={word_count}")
        if title:
            print(f"  title={title}")

    if failures:
        print(f"Done with {failures} failure(s)", file=sys.stderr)
        return 1
    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
