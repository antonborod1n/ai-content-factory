"""Import a competitor-topics content-plan JSON into a topics file.

Thin file mapper: no HTTP, OpenAI, or database access.

Examples::

    python scripts/import_competitor_plan.py topics/content-plan-example.com.json

    python scripts/import_competitor_plan.py topics/content-plan-example.com.json --topics-file topics/topics.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.competitor_plan import import_competitor_plan

DEFAULT_TOPICS_FILE = Path("topics/topics.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append competitor-plan topics to a topics JSON file"
    )
    parser.add_argument(
        "plan_file",
        type=Path,
        help="content-plan-[domain].json (for example topics/content-plan-example.com.json)",
    )
    parser.add_argument(
        "--topics-file",
        type=Path,
        default=DEFAULT_TOPICS_FILE,
        help=f"JSON topics file (default: {DEFAULT_TOPICS_FILE})",
    )
    args = parser.parse_args(argv)

    if not args.plan_file.is_file():
        print(f"Plan file not found: {args.plan_file}", file=sys.stderr)
        return 1

    try:
        result = import_competitor_plan(args.plan_file, args.topics_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to import competitor plan: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {result.added} new topic(s) "
        f"({result.skipped} skipped) to {result.path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
