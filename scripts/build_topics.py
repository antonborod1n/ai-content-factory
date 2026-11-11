"""Build topics.json from Discovery or competitor files.

Thin client: no OpenAI, no SQL. Discovery and raw competitor dumps go through
the running API; a ready content-plan JSON is mapped locally.

Examples::

    python scripts/build_topics.py --mode discovery --seed "матрасы Минск"

    python scripts/build_topics.py --mode competitor --files dumps/keys.csv

    python scripts/build_topics.py --mode competitor \\
        --plan topics/content-plan-example.com.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from app.core.competitor_plan import import_competitor_plan
from app.core.project_paths import topics_file_for_slug
from app.core.topic_source import split_seeds, validate_topic_source

DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_TOPICS_FILE = Path("topics/topics.json")
DISCOVERY_PATH = "/api/v1/discovery"
COMPETITOR_SOURCES_PATH = "/api/v1/competitor-topics/sources"


def _api_base_url(value: str | None) -> str:
    return (value or os.environ.get("API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip(
        "/"
    )


def _error_body(response: httpx.Response) -> str:
    text = (response.text or "").strip().replace("\n", " ")
    return text[:500]


def _raise_for_status(response: httpx.Response, *, action: str) -> None:
    if response.is_success:
        return
    detail = _error_body(response) or response.reason_phrase
    raise RuntimeError(f"{action} failed: HTTP {response.status_code} {detail}")


def _export(
    client: httpx.Client,
    *,
    prefix: str,
    plan_id: str,
    topics_file: Path,
) -> dict[str, Any]:
    response = client.post(
        f"{prefix}/{plan_id}/export",
        json={"path": str(topics_file)},
    )
    _raise_for_status(response, action="Export")
    return response.json()


def run_discovery(
    *,
    api_base_url: str,
    seeds: tuple[str, ...],
    topics_file: Path,
    niche: str = "",
    language: str = "ru",
    audience: str = "general",
    timeout: float = 180.0,
    client: httpx.Client | None = None,
    project_slug: str = "default",
) -> dict[str, Any]:
    """POST /discovery then export briefs into the topics file."""
    own_client = client is None
    http = client or httpx.Client(
        base_url=api_base_url,
        timeout=timeout,
        headers={"X-Project-Slug": project_slug},
    )
    try:
        response = http.post(
            DISCOVERY_PATH,
            json={
                "seeds": list(seeds),
                "niche": niche,
                "language": language,
                "audience": audience,
            },
        )
        _raise_for_status(response, action="Discovery")
        plan = response.json()
        status = plan.get("status")
        plan_id = plan.get("id")
        if status != "completed" or not plan_id:
            raise RuntimeError(
                f"Discovery did not complete (status={status!r} id={plan_id})"
            )
        exported = _export(
            http,
            prefix=DISCOVERY_PATH,
            plan_id=str(plan_id),
            topics_file=topics_file,
        )
        exported["plan_id"] = plan_id
        exported["topic_count"] = len(plan.get("topics") or [])
        return exported
    finally:
        if own_client:
            http.close()


def run_competitor_files(
    *,
    api_base_url: str,
    files: tuple[str, ...],
    topics_file: Path,
    domain: str = "",
    niche: str = "",
    audience: str = "",
    language: str = "ru",
    timeout: float = 180.0,
    client: httpx.Client | None = None,
    project_slug: str = "default",
) -> dict[str, Any]:
    """POST /competitor-topics/sources then export briefs."""
    uploads: list[tuple[str, tuple[str, bytes]]] = []
    for raw in files:
        path = Path(raw)
        if not path.is_file():
            raise FileNotFoundError(f"Competitor file not found: {path}")
        uploads.append(("files", (path.name, path.read_bytes())))

    own_client = client is None
    http = client or httpx.Client(
        base_url=api_base_url,
        timeout=timeout,
        headers={"X-Project-Slug": project_slug},
    )
    try:
        response = http.post(
            COMPETITOR_SOURCES_PATH,
            files=uploads,
            data={
                "domain": domain,
                "niche": niche,
                "audience": audience,
                "language": language,
            },
        )
        _raise_for_status(response, action="Competitor topics")
        plan = response.json()
        status = plan.get("status")
        plan_id = plan.get("id")
        if status != "completed" or not plan_id:
            raise RuntimeError(
                "Competitor topics did not complete "
                f"(status={status!r} id={plan_id})"
            )
        exported = _export(
            http,
            prefix="/api/v1/competitor-topics",
            plan_id=str(plan_id),
            topics_file=topics_file,
        )
        exported["plan_id"] = plan_id
        exported["topic_count"] = len(plan.get("topics") or [])
        return exported
    finally:
        if own_client:
            http.close()


def run_competitor_plan(*, plan_file: Path, topics_file: Path) -> dict[str, Any]:
    """Map a ready content-plan JSON locally (no HTTP)."""
    if not plan_file.is_file():
        raise FileNotFoundError(f"Plan file not found: {plan_file}")
    result = import_competitor_plan(plan_file, topics_file)
    return {
        "path": str(result.path),
        "added": result.added,
        "skipped": result.skipped,
        "plan_id": None,
        "topic_count": result.added,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fill a topics JSON file from Discovery (seeds) or competitor files. "
            "Does not generate articles."
        )
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("discovery", "competitor"),
        help="discovery = search seeds; competitor = dumps or content-plan JSON",
    )
    parser.add_argument(
        "--seed",
        action="append",
        default=[],
        dest="seeds",
        help="Discovery seed (repeat or comma-separate). Discovery mode only.",
    )
    parser.add_argument(
        "--files",
        action="append",
        default=[],
        dest="files",
        help="Competitor dump (xlsx/csv/txt/json). Repeatable. Competitor mode.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Ready content-plan-*.json (local import, no API). Competitor mode.",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("ACF_PROJECT", "default"),
        help="Project slug (default: env ACF_PROJECT or default)",
    )
    parser.add_argument(
        "--topics-file",
        type=Path,
        default=None,
        help=(
            "Topics JSON to append "
            f"(default: {DEFAULT_TOPICS_FILE} for project default, "
            "topics/{slug}/topics.json otherwise)"
        ),
    )
    parser.add_argument(
        "--niche",
        default="",
        help="Optional niche / site context",
    )
    parser.add_argument(
        "--audience",
        default="general",
        help="Audience for Discovery briefs (default: general)",
    )
    parser.add_argument(
        "--language",
        default="ru",
        help="Brief language (default: ru)",
    )
    parser.add_argument(
        "--domain",
        default="",
        help="Site domain for competitor dumps (optional)",
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
        help="HTTP timeout in seconds (default: 180)",
    )
    args = parser.parse_args(argv)

    try:
        choice = validate_topic_source(
            mode=args.mode,
            seeds=split_seeds(*args.seeds),
            files=args.files,
            plan=str(args.plan) if args.plan is not None else None,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    api_base_url = _api_base_url(args.api_base_url)
    topics_file = args.topics_file or topics_file_for_slug(args.project)

    try:
        if choice.mode.value == "discovery":
            print(f"mode=discovery api={api_base_url}{DISCOVERY_PATH}")
            print(f"seeds={list(choice.seeds)}")
            result = run_discovery(
                api_base_url=api_base_url,
                seeds=choice.seeds,
                topics_file=topics_file,
                niche=args.niche,
                language=args.language,
                audience=args.audience,
                timeout=args.timeout,
                project_slug=args.project,
            )
        elif choice.plan:
            print(f"mode=competitor plan={choice.plan}")
            result = run_competitor_plan(
                plan_file=Path(choice.plan),
                topics_file=topics_file,
            )
        else:
            print(
                f"mode=competitor api={api_base_url}{COMPETITOR_SOURCES_PATH}"
            )
            print(f"files={list(choice.files)}")
            result = run_competitor_files(
                api_base_url=api_base_url,
                files=choice.files,
                topics_file=topics_file,
                domain=args.domain,
                niche=args.niche,
                audience=args.audience if args.audience != "general" else "",
                language=args.language,
                timeout=args.timeout,
                project_slug=args.project,
            )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
        httpx.HTTPError,
    ) as exc:
        print(f"Failed to build topics: {exc}", file=sys.stderr)
        return 1

    added = result.get("added")
    skipped = result.get("skipped")
    path = result.get("path") or topics_file
    plan_id = result.get("plan_id")
    extra = f" plan_id={plan_id}" if plan_id else ""
    print(f"Wrote {added} new topic(s) ({skipped} skipped) to {path}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
