"""Deterministic HTML structure extraction. No AI, no SQL, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from app.core.word_count import count_words

_HEADING_TAGS = frozenset({"h1", "h2", "h3"})
_SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "template"})
_VIDEO_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "rutube.ru",
    "vk.com/video",
)
_FAQ_MARKERS = ("faq", "часто задаваем", "вопрос-ответ", "вопросы и ответы")
_INFOGRAPHIC_MARKERS = (
    "infographic",
    "инфографик",
    "схема",
    "chart",
    "diagram",
    "диаграмм",
)


@dataclass(frozen=True)
class PageSection:
    """One H1–H3 block and how many photos sit under it."""

    heading: str
    image_count: int = 0


@dataclass(frozen=True)
class PageStructure:
    """Visible outline of a competitor article."""

    title: str
    headings: list[str]
    word_count: int
    char_count: int
    image_count: int
    infographic_count: int
    video_count: int
    list_count: int
    table_count: int
    has_faq: bool
    features: list[str] = field(default_factory=list)
    sections: list[PageSection] = field(default_factory=list)


def parse_html(html: str, *, fallback_title: str = "") -> PageStructure:
    """Extract headings, counts and simple features from an HTML document."""
    parser = _StructureParser()
    parser.feed(html or "")
    parser.close()

    title = parser.title.strip() or fallback_title.strip()
    headings = [item.strip() for item in parser.headings if item.strip()]
    body = " ".join(parser.text_parts)
    word_count = count_words(body)
    char_count = len(body)
    has_faq = _looks_like_faq(headings, body)
    features = _feature_list(
        image_count=parser.image_count,
        infographic_count=parser.infographic_count,
        video_count=parser.video_count,
        list_count=parser.list_count,
        table_count=parser.table_count,
        has_faq=has_faq,
    )
    parser.flush_section()
    return PageStructure(
        title=title,
        headings=headings,
        word_count=word_count,
        char_count=char_count,
        image_count=parser.image_count,
        infographic_count=parser.infographic_count,
        video_count=parser.video_count,
        list_count=parser.list_count,
        table_count=parser.table_count,
        has_faq=has_faq,
        features=features,
        sections=[
            PageSection(heading=heading, image_count=count)
            for heading, count in parser.sections
        ],
    )


def _looks_like_faq(headings: list[str], body: str) -> bool:
    haystack = " ".join(headings + [body]).casefold()
    return any(marker in haystack for marker in _FAQ_MARKERS)


def _looks_like_infographic(src: str, alt: str) -> bool:
    haystack = f"{src} {alt}".casefold()
    return any(marker in haystack for marker in _INFOGRAPHIC_MARKERS)


def _feature_list(
    *,
    image_count: int,
    infographic_count: int,
    video_count: int,
    list_count: int,
    table_count: int,
    has_faq: bool,
) -> list[str]:
    features: list[str] = []
    if image_count:
        features.append(f"images:{image_count}")
    if infographic_count:
        features.append(f"infographics:{infographic_count}")
    if video_count:
        features.append(f"video:{video_count}")
    if list_count:
        features.append("lists")
    if table_count:
        features.append("tables")
    if has_faq:
        features.append("faq")
    return features


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.headings: list[str] = []
        self.text_parts: list[str] = []
        self.image_count = 0
        self.infographic_count = 0
        self.video_count = 0
        self.list_count = 0
        self.table_count = 0
        self.sections: list[tuple[str, int]] = []
        self._skip_depth = 0
        self._capture_title = False
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._section_heading = ""
        self._section_images = 0
        self._section_open = False

    def flush_section(self) -> None:
        """Close the current heading block (images before the next H2)."""
        if self._section_open or self._section_images:
            self.sections.append((self._section_heading, self._section_images))
            self._section_open = False
            self._section_images = 0
            self._section_heading = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        attr_map = {key.lower(): (value or "") for key, value in attrs}

        if name in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if name == "title":
            self._capture_title = True
        elif name in _HEADING_TAGS:
            self._heading_tag = name
            self._heading_parts = []
        elif name == "img":
            src = attr_map.get("src", "").strip()
            if src and not src.startswith("data:"):
                self.image_count += 1
                self._section_images += 1
                if _looks_like_infographic(src, attr_map.get("alt", "")):
                    self.infographic_count += 1
        elif name == "video":
            self.video_count += 1
        elif name == "iframe":
            src = attr_map.get("src", "").casefold()
            if any(marker in src for marker in _VIDEO_HOST_MARKERS):
                self.video_count += 1
        elif name in {"ul", "ol"}:
            self.list_count += 1
        elif name == "table":
            self.table_count += 1

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if name == "title":
            self._capture_title = False
        elif name in _HEADING_TAGS and self._heading_tag == name:
            heading = " ".join(self._heading_parts).strip()
            if heading:
                self.headings.append(heading)
                if self._section_open or self._section_images:
                    self.sections.append((self._section_heading, self._section_images))
                self._section_heading = heading
                self._section_images = 0
                self._section_open = True
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._capture_title:
            self.title = f"{self.title} {text}".strip()
        if self._heading_tag is not None:
            self._heading_parts.append(text)
        self.text_parts.append(text)
