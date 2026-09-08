"""Load prompt templates from the prompts/ directory."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.core.exceptions import AIConfigurationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.section_plan import SectionPlan

# Used to size a per-section word budget when the brief has no outline.
_DEFAULT_SECTION_COUNT = 6

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


def target_word_count(
    request: ArticleWriteInput, default_word_count: int | None = None
) -> int:
    """Requested length, falling back to the configured target."""
    if default_word_count is None:
        default_word_count = get_settings().article_target_word_count
    return request.word_count or default_word_count


def words_per_section(request: ArticleWriteInput, target: int) -> int:
    """Per-section word budget used to stop the model from writing a stub."""
    sections = len(request.outline) or _DEFAULT_SECTION_COUNT
    return max(target // sections, 1)


def _render_brief(
    template: str, request: ArticleWriteInput, *, default_word_count: int
) -> str:
    """Substitute the placeholders shared by the writer and expand prompts."""
    target = target_word_count(request, default_word_count)
    brief = request.brief_for_prompt(default_word_count=default_word_count)
    brief_json = json.dumps(brief, ensure_ascii=False, indent=2)

    return (
        template.replace("{{language}}", request.language)
        .replace("{{word_count}}", str(target))
        .replace("{{words_per_section}}", str(words_per_section(request, target)))
        .replace("{{audience}}", request.audience)
        .replace("{{tone}}", request.tone or "(не задан)")
        .replace("{{article_goal}}", request.article_goal or "(не задана)")
        .replace("{{search_intent}}", request.search_intent)
        .replace("{{cta}}", request.cta or "(не задан)")
        .replace("{{brief_json}}", brief_json)
        .replace("{{topic}}", request.topic)
    )


def render_article_writer_prompt(
    request: ArticleWriteInput,
    *,
    default_word_count: int | None = None,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render the user prompt from ``article_writer.md`` and the request brief."""
    if default_word_count is None:
        default_word_count = get_settings().article_target_word_count
    template = load_prompt("article_writer.md", prompts_dir=prompts_dir)
    return _render_brief(template, request, default_word_count=default_word_count)


def render_article_meta_prompt(
    request: ArticleWriteInput,
    *,
    default_word_count: int | None = None,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_meta.md``: title, meta description and slug only."""
    if default_word_count is None:
        default_word_count = get_settings().article_target_word_count
    template = load_prompt("article_meta.md", prompts_dir=prompts_dir)
    return _render_brief(template, request, default_word_count=default_word_count)


def render_article_section_prompt(
    request: ArticleWriteInput,
    *,
    plan: SectionPlan,
    title: str,
    previous_sections: list[str],
    default_word_count: int | None = None,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_section.md`` for one section of a long article."""
    if default_word_count is None:
        default_word_count = get_settings().article_target_word_count
    template = load_prompt("article_section.md", prompts_dir=prompts_dir)
    rendered = _render_brief(
        template, request, default_word_count=default_word_count
    )
    written = (
        "\n".join(f"- {section}" for section in previous_sections)
        or "(это первый раздел)"
    )
    return (
        rendered.replace("{{current_title}}", title)
        .replace("{{section_title}}", plan.title)
        .replace("{{section_index}}", str(plan.index))
        .replace("{{section_count}}", str(plan.total))
        .replace("{{section_word_count}}", str(plan.word_count))
        .replace("{{section_image_placeholders}}", str(plan.image_placeholders))
        .replace(
            "{{section_infographic_placeholders}}",
            str(plan.infographic_placeholders),
        )
        .replace("{{first_image_number}}", str(plan.first_image_number))
        .replace(
            "{{first_infographic_number}}", str(plan.first_infographic_number)
        )
        .replace("{{is_last_section}}", "true" if plan.is_last else "false")
        .replace("{{previous_sections}}", written)
    )


def render_article_expand_prompt(
    request: ArticleWriteInput,
    *,
    current: AIArticleOutput,
    current_word_count: int,
    default_word_count: int | None = None,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_expand.md`` to grow a draft that came back too short."""
    if default_word_count is None:
        default_word_count = get_settings().article_target_word_count
    template = load_prompt("article_expand.md", prompts_dir=prompts_dir)
    rendered = _render_brief(
        template, request, default_word_count=default_word_count
    )
    return (
        rendered.replace("{{current_word_count}}", str(current_word_count))
        .replace("{{current_title}}", current.title)
        .replace("{{current_meta_description}}", current.meta_description)
        .replace("{{current_url_slug}}", current.url_slug or "")
        .replace("{{current_markdown}}", current.content_markdown)
    )
