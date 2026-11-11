"""Export a stored content plan into a topics JSON file.

Thin HTTP client: GET /api/v1/discovery/{id} then merge_topics locally.
Does not call OpenAI or SERP providers.

Examples::

    python scripts/export_content_plan.py <plan-id>

    python scripts/export_content_plan.py <plan-id> --topics-file topics/topics.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.topics_file import merge_topics

DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_TOPICS_FILE = Path("topics/topics.json")


def fetch_plan(*, api_base_url: str, plan_id: UUID, timeout_seconds: float) -> dict:
    url = api_base_url.rstrip("/") + f"/api/v1/discovery/{plan_id}"
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a content plan to a topics JSON file"
    )
    parser.add_argument("plan_id", type=UUID, help="Content plan UUID")
    parser.add_argument(
        "--topics-file",
        type=Path,
        default=DEFAULT_TOPICS_FILE,
        help=f"JSON topics file (default: {DEFAULT_TOPICS_FILE})",
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
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )
    args = parser.parse_args(argv)
    api_base_url = (
        args.api_base_url
        or os.environ.get("API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )

    try:
        plan = fetch_plan(
            api_base_url=api_base_url,
            plan_id=args.plan_id,
            timeout_seconds=args.timeout,
        )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} fetching content plan: {body}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Failed to reach API: {exc}", file=sys.stderr)
        return 1

    if plan.get("status") != "completed":
        print(
            f"Content plan status is {plan.get('status')!r}, expected completed",
            file=sys.stderr,
        )
        return 1

    briefs = [item.get("brief") or {} for item in plan.get("topics") or []]
    if not briefs:
        print("Content plan has no topics", file=sys.stderr)
        return 1

    result = merge_topics(args.topics_file, briefs)
    print(
        f"Wrote {result.added} new topic(s) "
        f"({result.skipped} skipped) to {result.path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
