"""Load prompt templates from the prompts/ directory."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.core.exceptions import AIConfigurationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.schemas.competitor_topics import ContentGapInput
from app.schemas.discovery import TopicPlanInput
from app.schemas.dzen import DzenWriteInput
from app.schemas.pipeline import EditorInput, FactCheckInput, SeoPlanInput
from app.schemas.quality import DetectorInput, HumanizerInput, SummaryInput
from app.schemas.research import CompetitorPlanInput
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
        .replace("{{knowledge_context}}", _knowledge_context_block(request))
        .replace("{{competitor_context}}", _competitor_context_block(request))
    )


_EMPTY_KNOWLEDGE_CONTEXT = (
    "(дополнительных материалов из базы знаний нет — пишите по brief, "
    "не выдумывайте факты из несуществующих документов.)"
)

_EMPTY_COMPETITOR_CONTEXT = (
    "(анализа конкурентов нет — следуйте brief и outline, не выдумывайте "
    "чужие статьи.)"
)


def _knowledge_context_block(request: ArticleWriteInput) -> str:
    context = request.knowledge_context.strip()
    return context if context else _EMPTY_KNOWLEDGE_CONTEXT


def _competitor_context_block(request: ArticleWriteInput) -> str:
    context = request.competitor_context.strip()
    return context if context else _EMPTY_COMPETITOR_CONTEXT


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


def render_article_section_expand_prompt(
    section_prompt: str,
    *,
    plan: SectionPlan,
    current_markdown: str,
    current_word_count: int,
    prompts_dir: Path | str | None = None,
) -> str:
    """Append ``article_section_expand.md`` to the section prompt for a retry."""
    template = load_prompt("article_section_expand.md", prompts_dir=prompts_dir)
    addendum = (
        template.replace("{{section_title}}", plan.title)
        .replace("{{section_word_count}}", str(plan.word_count))
        .replace("{{current_section_word_count}}", str(current_word_count))
        .replace("{{current_section_markdown}}", current_markdown)
    )
    return f"{section_prompt}\n\n{addendum}"


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


def render_topic_discovery_prompt(
    request: TopicPlanInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``topic_discovery.md`` from SERP candidates."""
    template = load_prompt("topic_discovery.md", prompts_dir=prompts_dir)
    candidates = json.dumps(
        [item.model_dump(mode="json") for item in request.candidates],
        ensure_ascii=False,
        indent=2,
    )
    seeds = ", ".join(request.seeds) or "(не заданы)"
    niche = request.niche.strip() or "(не задана)"
    return (
        template.replace("{{niche}}", niche)
        .replace("{{seeds}}", seeds)
        .replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{max_topics}}", str(request.max_topics))
        .replace("{{candidates_json}}", candidates)
    )


def render_competitor_gap_prompt(
    request: ContentGapInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``competitor_gap.md`` from extracted competitor hits."""
    template = load_prompt("competitor_gap.md", prompts_dir=prompts_dir)
    hits = json.dumps(
        [item.model_dump(mode="json") for item in request.hits],
        ensure_ascii=False,
        indent=2,
    )
    return (
        template.replace("{{domain}}", request.domain.strip() or "(не задан)")
        .replace("{{niche}}", request.niche.strip() or "(не задана)")
        .replace("{{audience}}", request.audience.strip() or "(не задана)")
        .replace("{{geo}}", request.geo.strip() or "(не задано)")
        .replace("{{site_type}}", request.site_type.strip() or "(не задан)")
        .replace("{{language}}", request.language)
        .replace("{{max_topics}}", str(request.max_topics))
        .replace("{{hits_json}}", hits)
    )


def render_competitor_outline_prompt(
    request: CompetitorPlanInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``competitor_outline.md`` from competitor page structures."""
    template = load_prompt("competitor_outline.md", prompts_dir=prompts_dir)
    keywords = ", ".join(request.keywords) or "(не заданы)"
    profiles = json.dumps(
        [item.model_dump() for item in request.competitors],
        ensure_ascii=False,
        indent=2,
    )
    return (
        template.replace("{{topic}}", request.topic)
        .replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{word_count}}", str(request.word_count))
        .replace("{{keywords}}", keywords)
        .replace("{{competitor_profiles}}", profiles)
    )


def _join_or_none(items: list[str]) -> str:
    return ", ".join(items) or "(не заданы)"


def _outline_block(outline: list[str]) -> str:
    if not outline:
        return "(outline не задан — предложите 6–10 пунктов H2)"
    return "\n".join(f"- {item}" for item in outline)


def render_seo_brief_prompt(
    request: SeoPlanInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``seo_brief.md`` for the SEO agent."""
    template = load_prompt("seo_brief.md", prompts_dir=prompts_dir)
    competitor = request.competitor_context.strip() or _EMPTY_COMPETITOR_CONTEXT
    return (
        template.replace("{{topic}}", request.topic)
        .replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{word_count}}", str(request.word_count))
        .replace("{{search_intent}}", request.search_intent or "(не задан)")
        .replace("{{article_goal}}", request.article_goal or "(не задана)")
        .replace("{{keywords}}", _join_or_none(request.keywords))
        .replace("{{primary_keywords}}", _join_or_none(request.primary_keywords))
        .replace(
            "{{secondary_keywords}}", _join_or_none(request.secondary_keywords)
        )
        .replace("{{outline}}", _outline_block(request.outline))
        .replace("{{competitor_context}}", competitor)
    )


def render_fact_check_prompt(
    request: FactCheckInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``fact_check.md`` for the fact-checker agent."""
    template = load_prompt("fact_check.md", prompts_dir=prompts_dir)
    knowledge = request.knowledge_context.strip() or _EMPTY_KNOWLEDGE_CONTEXT
    competitor = request.competitor_context.strip() or _EMPTY_COMPETITOR_CONTEXT
    return (
        template.replace("{{topic}}", request.topic)
        .replace("{{language}}", request.language)
        .replace("{{title}}", request.title)
        .replace("{{meta_description}}", request.meta_description)
        .replace("{{knowledge_context}}", knowledge)
        .replace("{{competitor_context}}", competitor)
        .replace("{{content_markdown}}", request.content_markdown)
    )


def _fact_check_issues_block(request: EditorInput) -> str:
    issues = request.fact_check.issues
    if not issues:
        return "(замечаний нет — сделайте лёгкую вычитку)"
    lines: list[str] = []
    for index, issue in enumerate(issues, start=1):
        lines.append(
            f"{index}. [{issue.severity}] {issue.claim}\n"
            f"   проблема: {issue.problem}\n"
            f"   как исправить: {issue.suggestion or '(не указано)'}"
        )
    return "\n".join(lines)


def render_editor_prompt(
    request: EditorInput,
    *,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_editor.md`` for the editor agent."""
    template = load_prompt("article_editor.md", prompts_dir=prompts_dir)
    knowledge = request.knowledge_context.strip() or _EMPTY_KNOWLEDGE_CONTEXT
    competitor = request.competitor_context.strip() or _EMPTY_COMPETITOR_CONTEXT
    draft = request.draft
    return (
        template.replace("{{topic}}", request.topic)
        .replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{outline}}", _outline_block(request.outline))
        .replace("{{knowledge_context}}", knowledge)
        .replace("{{competitor_context}}", competitor)
        .replace("{{fact_check_verdict}}", request.fact_check.verdict)
        .replace(
            "{{fact_check_notes}}",
            request.fact_check.notes or "(нет)",
        )
        .replace("{{fact_check_issues}}", _fact_check_issues_block(request))
        .replace("{{current_title}}", draft.title)
        .replace("{{current_meta_description}}", draft.meta_description)
        .replace("{{current_url_slug}}", draft.url_slug or "")
        .replace("{{current_markdown}}", draft.content_markdown)
    )


_GENERIC_PHOTO_ALTS = frozenset(
    {
        "",
        "(без описания)",
        "описание изображения",
        "описание картинки",
        "изображение",
        "фото",
        "кадр",
        "главное описание",
        "кадр в тексте",
        "второй кадр",
        "обложка",
    }
)
_GENERIC_INFOGRAPHIC_ALTS = frozenset({"", "инфографика", "схема"})


def image_scene_alt(
    alt: str,
    *,
    topic: str,
    kind: str,
    heading: str = "",
    excerpt: str = "",
    title: str = "",
) -> str:
    """Turn copied placeholder alts into a usable scene description."""
    cleaned = " ".join((alt or "").split())
    lowered = cleaned.lower()
    block = heading.strip()
    detail = " ".join((excerpt or "").split())
    if kind == "hero":
        name = (title or heading or topic).strip()
        return (
            f"Главный кадр статьи «{name}»: реалистичное фото по названию, "
            "широкий hero 16:9, предмет или место по теме, без людей, "
            "без графики и текста"
        )
    if kind == "infographic":
        if lowered in _GENERIC_INFOGRAPHIC_ALTS:
            if block:
                return (
                    f"Простая схема к разделу «{block}»: {detail or block}. "
                    "Крупные блоки, почти без текста."
                )
            return f"Простая схема по теме: {topic}. Крупные блоки, почти без текста."
        return cleaned
    if lowered in _GENERIC_PHOTO_ALTS:
        if block:
            return (
                f"Реалистичное фото к разделу «{block}»: {detail or block}. "
                "Предмет, место или результат этого блока, естественный свет, "
                "без людей, без графики и текста"
            )
        return (
            f"Реалистичное фото по теме «{topic}»: предмет или место, "
            "естественный свет, без людей, без графики и текста"
        )
    if block and block.casefold() not in cleaned.casefold():
        return f"{cleaned}. Раздел: {block}"
    return cleaned


def render_image_generate_prompt(
    *,
    topic: str,
    alt: str,
    kind: str,
    heading: str = "",
    excerpt: str = "",
    title: str = "",
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``image_generate.md`` for one placeholder."""
    template = load_prompt("image_generate.md", prompts_dir=prompts_dir)
    scene = image_scene_alt(
        alt,
        topic=topic,
        kind=kind,
        heading=heading,
        excerpt=excerpt,
        title=title,
    )
    return (
        template.replace("{{topic}}", topic)
        .replace("{{section_heading}}", heading.strip() or "(раздел не указан)")
        .replace("{{section_excerpt}}", excerpt.strip() or "(нет текста блока)")
        .replace("{{alt}}", scene)
        .replace("{{kind}}", kind)
    )


def render_dzen_prompt(
    request: DzenWriteInput,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``dzen_article.md`` for the shorter channel version."""
    template = load_prompt("dzen_article.md", prompts_dir=prompts_dir)
    return (
        template.replace("{{source_title}}", request.source_title)
        .replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{target_char_count}}", str(request.target_char_count))
        .replace("{{source_markdown}}", request.source_markdown)
    )


def render_detector_prompt(
    request: DetectorInput,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``ai_detector.md``."""
    template = load_prompt("ai_detector.md", prompts_dir=prompts_dir)
    return (
        template.replace("{{title}}", request.title)
        .replace("{{language}}", request.language)
        .replace("{{content_markdown}}", request.content_markdown)
    )


def render_humanizer_prompt(
    request: HumanizerInput,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_humanizer.md``."""
    template = load_prompt("article_humanizer.md", prompts_dir=prompts_dir)
    return (
        template.replace("{{language}}", request.language)
        .replace("{{audience}}", request.audience)
        .replace("{{detector_notes}}", request.detector_notes or "(нет)")
        .replace("{{current_title}}", request.title)
        .replace("{{current_meta_description}}", request.meta_description)
        .replace("{{current_url_slug}}", request.url_slug or "")
        .replace("{{current_markdown}}", request.content_markdown)
    )


def render_summary_prompt(
    request: SummaryInput,
    prompts_dir: Path | str | None = None,
) -> str:
    """Render ``article_summary.md``."""
    template = load_prompt("article_summary.md", prompts_dir=prompts_dir)
    return (
        template.replace("{{title}}", request.title)
        .replace("{{language}}", request.language)
        .replace("{{target_char_count}}", str(request.target_char_count))
        .replace("{{content_markdown}}", request.content_markdown)
    )
