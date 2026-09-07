"""The exported n8n workflow must stay a thin, secret-free HTTP client."""

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.main import create_app
from app.schemas.articles import ArticleGenerateRequest

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / "n8n" / "workflows"
    / "stage1_generate_article.json"
)


@pytest.fixture(scope="module")
def workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nodes_by_name(workflow: dict) -> dict:
    return {node["name"]: node for node in workflow["nodes"]}


def test_workflow_has_the_stage1_node_chain(
    workflow: dict, nodes_by_name: dict
) -> None:
    assert set(nodes_by_name) == {
        "Manual Trigger",
        "Set Article Parameters",
        "Generate Article",
        "IF Success",
        "Result",
        "Error Result",
    }
    assert nodes_by_name["Manual Trigger"]["type"] == (
        "n8n-nodes-base.manualTrigger"
    )
    assert nodes_by_name["Generate Article"]["type"] == (
        "n8n-nodes-base.httpRequest"
    )
    assert nodes_by_name["IF Success"]["type"] == "n8n-nodes-base.if"

    connections = workflow["connections"]

    def targets(node_name: str, output: int = 0) -> list[str]:
        return [item["node"] for item in connections[node_name]["main"][output]]

    assert targets("Manual Trigger") == ["Set Article Parameters"]
    assert targets("Set Article Parameters") == ["Generate Article"]
    assert targets("Generate Article") == ["IF Success"]
    assert targets("IF Success", 0) == ["Result"]
    assert targets("IF Success", 1) == ["Error Result"]


def test_workflow_sends_exactly_the_request_fields(nodes_by_name: dict) -> None:
    assignments = nodes_by_name["Set Article Parameters"]["parameters"][
        "assignments"
    ]["assignments"]
    sent_fields = {assignment["name"] for assignment in assignments}

    assert sent_fields == set(ArticleGenerateRequest.model_fields)

    body_expression = nodes_by_name["Generate Article"]["parameters"]["jsonBody"]
    for field in sent_fields:
        assert f"{field}:" in body_expression


def test_workflow_posts_to_an_existing_route(nodes_by_name: dict) -> None:
    parameters = nodes_by_name["Generate Article"]["parameters"]
    assert parameters["method"] == "POST"

    path = urlparse(parameters["url"]).path
    paths = create_app().openapi()["paths"]
    assert path in paths
    assert "post" in paths[path]


def test_workflow_branches_on_the_http_status_code(nodes_by_name: dict) -> None:
    http_options = nodes_by_name["Generate Article"]["parameters"]["options"]
    response_options = http_options["response"]["response"]
    # Without these the node throws on 4xx/5xx and the failure branch is dead.
    assert response_options["neverError"] is True
    assert response_options["fullResponse"] is True

    condition = nodes_by_name["IF Success"]["parameters"]["conditions"][
        "conditions"
    ][0]
    assert "statusCode" in condition["leftValue"]
    assert condition["rightValue"] == 200


def test_workflow_contains_no_secrets_or_credentials() -> None:
    raw = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    for forbidden in (
        "openai_api_key",
        "api_key",
        "apikey",
        "sk-",
        "authorization",
        "credentials",
        "password",
        "postgresql://",
        "postgresql+asyncpg",
    ):
        assert forbidden not in raw, f"workflow must not contain {forbidden!r}"


def test_workflow_contains_no_generation_logic() -> None:
    raw = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    for forbidden in ("openai", "prompt", "chat/completions", "insert into"):
        assert forbidden not in raw, f"workflow must not contain {forbidden!r}"
