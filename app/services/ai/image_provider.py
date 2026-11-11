"""ImageProvider protocol — generate PNG bytes from a prompt."""

from __future__ import annotations

from typing import Protocol


class ImageProvider(Protocol):
    """Creates one image. AI layer only — no persistence."""

    async def generate(self, prompt: str, *, kind: str) -> bytes:
        """Return PNG (or JPEG) bytes. ``kind`` is ``image`` or ``infographic``."""
        ...
