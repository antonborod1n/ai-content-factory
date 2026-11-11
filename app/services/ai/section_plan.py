"""Split a brief into per-section writing tasks.

Small models stop after roughly a thousand words no matter how the prompt is
worded, so a long article is written one outline section per request.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ai import ArticleWriteInput

# Below this a "section" is not worth its own request.
MIN_SECTION_WORD_COUNT = 150
# One heading is just an article; sectioning starts to pay off from two.
MIN_SECTIONS = 2


@dataclass(frozen=True)
class SectionPlan:
    """Everything one section request needs to know."""

    index: int
    total: int
    title: str
    word_count: int
    image_placeholders: int
    infographic_placeholders: int
    first_image_number: int
    first_infographic_number: int

    @property
    def is_last(self) -> bool:
        return self.index == self.total


def distribute(total: int, buckets: int) -> list[int]:
    """Spread ``total`` items over ``buckets`` as evenly as possible."""
    if buckets <= 0 or total <= 0:
        return [0] * max(buckets, 0)
    base, remainder = divmod(total, buckets)
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def build_section_plans(
    request: ArticleWriteInput, *, target_word_count: int
) -> list[SectionPlan]:
    """Plan one request per outline heading, or nothing when there is no outline."""
    titles = [title.strip() for title in request.outline if title.strip()]
    if len(titles) < MIN_SECTIONS:
        return []

    total = len(titles)
    per_section = max(target_word_count // total, MIN_SECTION_WORD_COUNT)
    images = _section_image_counts(request, total)
    infographics = distribute(request.infographic_placeholders, total)

    plans: list[SectionPlan] = []
    image_number = 1
    infographic_number = 1
    for index, title in enumerate(titles):
        plans.append(
            SectionPlan(
                index=index + 1,
                total=total,
                title=title,
                word_count=per_section,
                image_placeholders=images[index],
                infographic_placeholders=infographics[index],
                first_image_number=image_number,
                first_infographic_number=infographic_number,
            )
        )
        image_number += images[index]
        infographic_number += infographics[index]
    return plans


def _section_image_counts(request: ArticleWriteInput, total: int) -> list[int]:
    planned = [max(0, int(item)) for item in request.section_image_placeholders]
    if len(planned) == total:
        return planned
    return distribute(request.image_placeholders, total)
