"""Unit tests for health schema."""

from app.schemas.health import HealthResponse


def test_health_response_ok() -> None:
    payload = HealthResponse(status="ok", database="ok")
    assert payload.model_dump() == {"status": "ok", "database": "ok"}


def test_health_response_degraded() -> None:
    payload = HealthResponse(status="degraded", database="error")
    assert payload.model_dump() == {"status": "degraded", "database": "error"}
