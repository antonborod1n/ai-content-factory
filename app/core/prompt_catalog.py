"""Read prompt files for the operator. No writes, no path escape."""

from __future__ import annotations

from app.services.ai.prompt_loader import get_prompts_dir


def list_prompt_filenames() -> list[str]:
    directory = get_prompts_dir()
    if not directory.is_dir():
        return []
    return sorted(
        path.name
        for path in directory.glob("*.md")
        if path.is_file() and path.parent.resolve() == directory.resolve()
    )


def read_prompt_filename(filename: str) -> str:
    """Return the text of one prompt. Rejects names that leave the folder."""
    if not _safe_prompt_name(filename):
        raise ValueError("Unknown prompt")
    directory = get_prompts_dir().resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise FileNotFoundError(filename)
    return path.read_text(encoding="utf-8")


def _safe_prompt_name(filename: str) -> bool:
    if not filename.endswith(".md"):
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return filename.replace(".md", "").replace("_", "").isalnum()
