"""Per-project topic file and article output folder."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.topics_file import load_topics
from app.db.models.project import DEFAULT_PROJECT_SLUG


def topics_root() -> Path:
    """Folder that holds every project's topics file (``TOPICS_DIR``)."""
    return Path(get_settings().topics_dir.strip() or "topics")


def topics_file_for_slug(slug: str) -> Path:
    """Default keeps ``TOPICS_FILE_PATH``; others use ``{TOPICS_DIR}/{slug}/``."""
    if slug == DEFAULT_PROJECT_SLUG:
        configured = get_settings().topics_file_path.strip()
        if configured:
            return Path(configured)
    return topics_root() / slug / "topics.json"


def confined_topics_path(raw: str) -> Path:
    """A caller-supplied export path. Must be a ``.json`` file under ``TOPICS_DIR``."""
    candidate = Path(raw.strip())
    if candidate.suffix.lower() != ".json":
        raise ValueError("Export path must be a .json file")
    root = topics_root().resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Export path must stay inside the topics folder")
    return resolved


def read_project_topics(slug: str) -> list[dict[str, Any]]:
    """Briefs from the project topics file. Missing file is an empty queue."""
    path = topics_file_for_slug(slug)
    if not path.is_file():
        return []
    return load_topics(path)


def remove_project_files(slug: str) -> None:
    """Delete a non-default project's topic folder and article files."""
    if slug == DEFAULT_PROJECT_SLUG or "/" in slug or "\\" in slug or ".." in slug:
        return
    topics_dir = topics_root() / slug
    if topics_dir.is_dir():
        shutil.rmtree(topics_dir)
    output = articles_output_for_slug(slug)
    if output:
        folder = Path(output)
        if folder.is_dir():
            shutil.rmtree(folder)


def articles_output_for_slug(slug: str) -> str:
    """``output/articles/{slug}``. Empty when file output is disabled."""
    base = get_settings().articles_output_dir.strip()
    if not base:
        return ""
    return str(Path(base) / slug)
