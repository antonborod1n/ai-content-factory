"""Map competitor-topics content-plan JSON to article briefs.

Parsing and field mapping only — no HTTP, OpenAI, or database access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.topics_file import TopicsMergeResult, dump_topic_brief, merge_topics
from app.schemas.articles import ArticleGenerateRequest

DEFAULT_LANGUAGE = "ru"
DEFAULT_TONE = "экспертный, понятный, разговорный"
DEFAULT_SEARCH_INTENT = "informational_commercial"


class CompetitorPlanTopic(BaseModel):
    """One row from a competitor-topics content-plan JSON."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = Field(min_length=1)
    category: str = ""
    priority: str = ""
    competitors: list[str] = Field(default_factory=list)
    is_gap: bool = Field(default=False, alias="isGap")
    unique_angle: str = Field(default="", alias="uniqueAngle")
    intent: str = ""
    commercial_link: str = Field(default="", alias="commercialLink")
    format: str = ""
    month: int | None = None

    @field_validator("title", "category", "priority", "intent", "format")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("unique_angle", "commercial_link")
    @classmethod
    def _strip_optional(cls, value: str) -> str:
        return value.strip()

    @field_validator("competitors")
    @classmethod
    def _clean_competitors(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip() and item.strip().lower() != "gap"]


class CompetitorPlan(BaseModel):
    """Root of content-plan-[domain].json. Extra keys (summary, patterns) ignored."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    domain: str = ""
    niche: str = ""
    audience: str = ""
    geo: str = ""
    site_type: str = Field(default="", alias="siteType")
    blog_format: str = Field(default="", alias="blogFormat")
    topics: list[CompetitorPlanTopic] = Field(default_factory=list)

    @field_validator("domain", "niche", "audience", "geo")
    @classmethod
    def _strip_context(cls, value: str) -> str:
        return value.strip()


def is_content_plan_payload(raw: object) -> bool:
    """True when JSON looks like content-plan-[domain].json (not a raw dump)."""
    if not isinstance(raw, dict):
        return False
    topics = raw.get("topics")
    if not isinstance(topics, list) or not topics:
        return False
    first = topics[0]
    return isinstance(first, dict) and bool(str(first.get("title") or "").strip())


def normalize_search_intent(intent: str) -> str:
    """Turn ``informational / howto`` into ``informational_howto``."""
    parts = [part.strip().lower() for part in intent.replace("/", " ").split() if part.strip()]
    if not parts:
        return DEFAULT_SEARCH_INTENT
    return "_".join(parts)


def load_competitor_plan(path: Path | str) -> CompetitorPlan:
    """Parse a competitor-topics JSON file."""
    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Competitor plan JSON must be an object")
    plan = CompetitorPlan.model_validate(raw)
    if not plan.topics:
        raise ValueError("Competitor plan has no topics")
    return plan


def plan_topic_to_brief(
    topic: CompetitorPlanTopic,
    plan: CompetitorPlan,
    *,
    language: str = DEFAULT_LANGUAGE,
    use_knowledge_base: bool = True,
        use_competitor_research: bool = True,
        use_multi_agent: bool = False,
        use_text: bool = True,
        use_images: bool = False,
        use_internal_links: bool = True,
        use_dzen: bool = False,
        use_detectors: bool = False,
        use_humanizer: bool = False,
        use_summary: bool = False,
    ) -> dict[str, Any]:
    """Map one plan row to an ``ArticleGenerateRequest`` dump for topics.json.

    Research-derived fields (outline, word_count, placeholders) stay absent so
    Stage 3 research can fill them later.
    """
    primary = [topic.title]
    audience = plan.audience or "general"
    request = ArticleGenerateRequest(
        topic=topic.title,
        language=language,
        audience=audience,
        keywords=primary,
        primary_keywords=primary,
        search_intent=normalize_search_intent(topic.intent),
        article_goal=topic.unique_angle,
        cta=topic.commercial_link,
        tone=DEFAULT_TONE,
        use_knowledge_base=use_knowledge_base,
        use_competitor_research=use_competitor_research,
        use_multi_agent=use_multi_agent,
        use_text=use_text,
        use_images=use_images,
        use_internal_links=use_internal_links,
        use_dzen=use_dzen,
        use_detectors=use_detectors,
        use_humanizer=use_humanizer,
        use_summary=use_summary,
    )
    # dump_topic_brief strips research-derived fields unless they are in source.
    source: dict[str, Any] = {"topic": topic.title}
    if topic.unique_angle:
        source["article_goal"] = topic.unique_angle
    if topic.commercial_link:
        source["cta"] = topic.commercial_link
    return dump_topic_brief(request, source=source)


def plan_to_briefs(
    plan: CompetitorPlan,
    *,
    language: str = DEFAULT_LANGUAGE,
    use_knowledge_base: bool = True,
    use_competitor_research: bool = True,
    use_multi_agent: bool = False,
    use_text: bool = True,
    use_images: bool = False,
    use_internal_links: bool = True,
    use_dzen: bool = False,
    use_detectors: bool = False,
    use_humanizer: bool = False,
    use_summary: bool = False,
) -> list[dict[str, Any]]:
    """Map every plan row to a generate brief."""
    return [
        plan_topic_to_brief(
            topic,
            plan,
            language=language,
            use_knowledge_base=use_knowledge_base,
            use_competitor_research=use_competitor_research,
            use_multi_agent=use_multi_agent,
            use_text=use_text,
            use_images=use_images,
            use_internal_links=use_internal_links,
            use_dzen=use_dzen,
            use_detectors=use_detectors,
            use_humanizer=use_humanizer,
            use_summary=use_summary,
        )
        for topic in plan.topics
    ]


def plan_context(plan: CompetitorPlan) -> dict[str, Any]:
    """Compact site context stored on the content plan row (not in briefs)."""
    return {
        "domain": plan.domain,
        "geo": plan.geo,
        "site_type": plan.site_type,
        "blog_format": plan.blog_format,
    }


def plan_to_topic_rows(
    plan: CompetitorPlan,
    *,
    language: str = DEFAULT_LANGUAGE,
    use_knowledge_base: bool = True,
    use_competitor_research: bool = True,
    use_multi_agent: bool = False,
    use_text: bool = True,
    use_images: bool = False,
    use_internal_links: bool = True,
    use_dzen: bool = False,
    use_detectors: bool = False,
    use_humanizer: bool = False,
    use_summary: bool = False,
) -> list[dict[str, Any]]:
    """Rows for ``content_plan_topics`` (brief + competitor metadata)."""
    flags = {
        "language": language,
        "use_knowledge_base": use_knowledge_base,
        "use_competitor_research": use_competitor_research,
        "use_multi_agent": use_multi_agent,
        "use_text": use_text,
        "use_images": use_images,
        "use_internal_links": use_internal_links,
        "use_dzen": use_dzen,
        "use_detectors": use_detectors,
        "use_humanizer": use_humanizer,
        "use_summary": use_summary,
    }
    rows: list[dict[str, Any]] = []
    for index, topic in enumerate(plan.topics):
        rows.append(
            {
                "sort_order": index,
                "brief": plan_topic_to_brief(topic, plan, **flags),
                "source_engines": ["competitor_inventory"],
                "source_queries": list(topic.competitors),
                "source_competitors": list(topic.competitors),
                "is_gap": topic.is_gap,
                "priority": topic.priority,
                "category": topic.category,
            }
        )
    return rows


def import_competitor_plan(
    plan_path: Path | str,
    topics_path: Path | str,
    *,
    language: str = DEFAULT_LANGUAGE,
    use_knowledge_base: bool = True,
    use_competitor_research: bool = True,
) -> TopicsMergeResult:
    """Append unique briefs from a competitor plan into a topics JSON file."""
    plan = load_competitor_plan(plan_path)
    briefs = plan_to_briefs(
        plan,
        language=language,
        use_knowledge_base=use_knowledge_base,
        use_competitor_research=use_competitor_research,
    )
    return merge_topics(topics_path, briefs)
