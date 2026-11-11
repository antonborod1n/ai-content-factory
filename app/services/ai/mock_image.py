"""Deterministic ImageProvider for tests."""

from __future__ import annotations

from app.core.exceptions import AIError

# 1×1 transparent PNG. Not a secret; used so tests never call a real image API.
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MockImageProvider:
    """Returns a tiny PNG; never calls a provider."""

    def __init__(
        self,
        *,
        payload: bytes | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.payload = payload if payload is not None else MINIMAL_PNG
        self.fail_with = fail_with
        self.calls: list[tuple[str, str]] = []

    async def generate(self, prompt: str, *, kind: str) -> bytes:
        self.calls.append((prompt, kind))
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock image provider failed") from self.fail_with
        return self.payload
