"""Load prompt templates from the prompts/ directory."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.core.exceptions import AIConfigurationError

# Repo layout: app/services/ai/prompt_loader.py -> <root>/prompts
_SOURCE_TREE_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def get_prompts_dir(prompts_dir: Path | str | None = None) -> Path:
    """Resolve the prompts directory.

    Explicit argument wins, then the PROMPTS_DIR setting, then the working
    directory. The source-tree path is the last resort so an installed package
    does not look for prompts inside site-packages.
    """
    if prompts_dir is not None:
        return Path(prompts_dir)

    configured = get_settings().prompts_dir
    if configured:
        return Path(configured)

    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.is_dir():
        return cwd_prompts
    return _SOURCE_TREE_PROMPTS_DIR


def load_prompt(filename: str, prompts_dir: Path | str | None = None) -> str:
    """Read a prompt file from disk. Raises AIConfigurationError if missing."""
    path = get_prompts_dir(prompts_dir) / filename
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AIConfigurationError(
            f"Prompt file could not be loaded: {filename}"
        ) from exc


def load_system_prompt(prompts_dir: Path | str | None = None) -> str:
    """Read the writer system prompt. Prompts never live in Python code."""
    return load_prompt("article_writer_system.md", prompts_dir=prompts_dir).strip()


def render_article_writer_prompt(
    *,
    topic: str,
    language: str,
    audience: str,
    keywords: list[str],
    target_word_count: int | None = None,
    prompts_dir: Path | str | None = None,
) -> str:
    template = load_prompt("article_writer.md", prompts_dir=prompts_dir)
    keywords_text = ", ".join(keywords) if keywords else "(none)"
    if target_word_count is None:
        target_word_count = get_settings().article_target_word_count
    return (
        template.replace("{{topic}}", topic)
        .replace("{{language}}", language)
        .replace("{{audience}}", audience)
        .replace("{{keywords}}", keywords_text)
        .replace("{{target_word_count}}", str(target_word_count))
    )
