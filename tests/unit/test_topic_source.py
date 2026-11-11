"""Tests for the Discovery vs competitor topic-source switch."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.topic_source import (
    TopicSourceMode,
    split_seeds,
    validate_topic_source,
)


def test_split_seeds_dedupes_and_splits_commas() -> None:
    assert split_seeds("матрасы Минск, жесткость", "жесткость", "  ") == (
        "матрасы Минск",
        "жесткость",
    )


def test_discovery_requires_seeds() -> None:
    with pytest.raises(ValueError, match="at least one --seed"):
        validate_topic_source(mode="discovery")


def test_discovery_rejects_files_and_plan() -> None:
    with pytest.raises(ValueError, match="does not accept --files or --plan"):
        validate_topic_source(mode="discovery", seeds=["матрас"], files=["a.csv"])
    with pytest.raises(ValueError, match="does not accept --files or --plan"):
        validate_topic_source(mode="discovery", seeds=["матрас"], plan="plan.json")


def test_discovery_accepts_seeds() -> None:
    choice = validate_topic_source(mode="Discovery", seeds=[" матрас "])
    assert choice.mode is TopicSourceMode.DISCOVERY
    assert choice.seeds == ("матрас",)
    assert choice.files == ()
    assert choice.plan is None


def test_competitor_requires_files_or_plan() -> None:
    with pytest.raises(ValueError, match="requires --files or --plan"):
        validate_topic_source(mode="competitor")


def test_competitor_rejects_seeds_and_mixed_inputs() -> None:
    with pytest.raises(ValueError, match="does not accept --seed"):
        validate_topic_source(mode="competitor", seeds=["матрас"], files=["a.csv"])
    with pytest.raises(ValueError, match="not both"):
        validate_topic_source(
            mode="competitor", files=["a.csv"], plan="plan.json"
        )


def test_competitor_accepts_files_or_plan() -> None:
    files = validate_topic_source(mode="competitor", files=["dumps/a.csv"])
    assert files.mode is TopicSourceMode.COMPETITOR
    assert files.files == ("dumps/a.csv",)
    plan = validate_topic_source(mode="competitor", plan="topics/plan.json")
    assert plan.plan == "topics/plan.json"


def test_mode_must_be_known() -> None:
    with pytest.raises(ValueError, match="discovery or competitor"):
        validate_topic_source(mode="both")
    with pytest.raises(ValueError, match="mode is required"):
        validate_topic_source(mode="  ")


def _load_script():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "build_topics.py"
    spec = importlib.util.spec_from_file_location("build_topics", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_usage_error_without_mode() -> None:
    script = _load_script()
    with pytest.raises(SystemExit) as excinfo:
        script.main([])
    assert excinfo.value.code == 2


def test_main_discovery_usage_without_seed() -> None:
    script = _load_script()
    assert script.main(["--mode", "discovery"]) == 2


def test_run_discovery_posts_then_exports(tmp_path: Path) -> None:
    script = _load_script()
    dest = tmp_path / "topics.json"
    posted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append({"method": request.method, "path": request.url.path})
        if request.url.path == "/api/v1/discovery":
            body = json.loads(request.content)
            assert body["seeds"] == ["матрас"]
            assert body["niche"] == "сон"
            return httpx.Response(
                201,
                json={
                    "id": "11111111-1111-1111-1111-111111111111",
                    "status": "completed",
                    "topics": [{"brief": {"topic": "Как выбрать матрас"}}],
                },
            )
        if request.url.path.endswith("/export"):
            export = json.loads(request.content)
            assert export["path"] == str(dest)
            return httpx.Response(
                200, json={"path": str(dest), "added": 1, "skipped": 0}
            )
        return httpx.Response(404, json={"detail": "nope"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://app:8000",
    )
    result = script.run_discovery(
        api_base_url="http://app:8000",
        seeds=("матрас",),
        topics_file=dest,
        niche="сон",
        client=client,
    )
    assert result["added"] == 1
    assert result["plan_id"] == "11111111-1111-1111-1111-111111111111"
    assert [row["path"] for row in posted] == [
        "/api/v1/discovery",
        "/api/v1/discovery/11111111-1111-1111-1111-111111111111/export",
    ]


def test_run_competitor_files_uploads_then_exports(tmp_path: Path) -> None:
    script = _load_script()
    dump = tmp_path / "keys.csv"
    dump.write_text("keyword\nжесткость матраса\n", encoding="utf-8")
    dest = tmp_path / "topics.json"
    seen_upload = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_upload
        if request.url.path == "/api/v1/competitor-topics/sources":
            seen_upload = True
            assert b"keys.csv" in request.content
            return httpx.Response(
                201,
                json={
                    "id": "22222222-2222-2222-2222-222222222222",
                    "status": "completed",
                    "topics": [{"brief": {"topic": "Жесткость матраса"}}],
                },
            )
        if request.url.path.endswith("/export"):
            return httpx.Response(
                200, json={"path": str(dest), "added": 1, "skipped": 0}
            )
        return httpx.Response(404)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://app:8000",
    )
    result = script.run_competitor_files(
        api_base_url="http://app:8000",
        files=(str(dump),),
        topics_file=dest,
        client=client,
    )
    assert seen_upload
    assert result["added"] == 1


def test_run_competitor_plan_is_local(tmp_path: Path) -> None:
    script = _load_script()
    plan = tmp_path / "content-plan.json"
    plan.write_text(
        json.dumps(
            {
                "domain": "example.by",
                "topics": [{"title": "Какой матрас выбрать"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    dest = tmp_path / "topics.json"
    dest.write_text("[]\n", encoding="utf-8")
    result = script.run_competitor_plan(plan_file=plan, topics_file=dest)
    assert result["added"] == 1
    assert result["plan_id"] is None
    assert "Какой матрас выбрать" in dest.read_text(encoding="utf-8")


def test_run_discovery_fails_on_http_error() -> None:
    script = _load_script()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"detail": "SERP failed"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://app:8000",
    )
    with pytest.raises(RuntimeError, match="HTTP 502"):
        script.run_discovery(
            api_base_url="http://app:8000",
            seeds=("матрас",),
            topics_file=Path("topics/topics.json"),
            client=client,
        )
