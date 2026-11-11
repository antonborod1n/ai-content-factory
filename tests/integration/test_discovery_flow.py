"""Integration: discovery → export → topics file is readable by load_topics."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.topics_file import load_topics


@pytest.mark.asyncio
async def test_discovery_export_is_valid_topics_file(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    created = await client.post(
        "/api/v1/discovery",
        json={
            "seeds": ["жесткость матраса"],
            "niche": "матрасы",
            "audience": "Покупатели матрасов",
            "word_count": 2500,
        },
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["topics"]

    dest = tmp_path / "topics.json"
    exported = await client.post(
        f"/api/v1/discovery/{plan['id']}/export",
        json={"path": str(dest)},
    )
    assert exported.status_code == 200
    assert exported.json()["added"] >= 1

    topics = load_topics(dest)
    assert topics[0]["topic"]
    assert topics[0]["audience"] == "Покупатели матрасов"
    assert topics[0]["word_count"] == 2500
