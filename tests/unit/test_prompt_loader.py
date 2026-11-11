"""Unit tests for prompt loading."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import AIConfigurationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.schemas.dzen import DzenWriteInput
from app.schemas.pipeline import (
    EditorInput,
    FactCheckInput,
    FactCheckIssue,
    FactCheckOutput,
    SeoPlanInput,
)
from app.schemas.competitor_topics import ContentGapHit, ContentGapInput
from app.schemas.discovery import (
    CandidateKind,
    SearchEngine,
    TopicCandidate,
    TopicPlanInput,
)
from app.schemas.quality import DetectorInput, HumanizerInput, SummaryInput
from app.services.ai.prompt_loader import (
    get_prompts_dir,
    image_scene_alt,
    load_prompt,
    load_system_prompt,
    render_article_expand_prompt,
    render_article_writer_prompt,
    render_detector_prompt,
    render_dzen_prompt,
    render_editor_prompt,
    render_fact_check_prompt,
    render_humanizer_prompt,
    render_image_generate_prompt,
    render_seo_brief_prompt,
    render_summary_prompt,
    render_competitor_gap_prompt,
    render_topic_discovery_prompt,
    words_per_section,
)


def test_load_article_writer_prompt() -> None:
    content = load_prompt("article_writer.md")
    assert "{{brief_json}}" in content
    assert "{{word_count}}" in content
    assert "{{knowledge_context}}" in content
    assert "{{competitor_context}}" in content
    assert "content_markdown" in content
    assert "COVER_PLACEHOLDER" in content


def test_render_article_writer_prompt_substitutes_brief() -> None:
    request = ArticleWriteInput(
        topic="Как выбрать промышленный насос",
        language="ru",
        audience="Инженеры и закупщики",
        word_count=3000,
        primary_keywords=["промышленный насос", "как выбрать насос"],
        secondary_keywords=["напор насоса"],
        article_goal="Практическое руководство",
        tone="экспертный, разговорный",
        outline=["Введение", "FAQ", "Заключение"],
        cta="Обратитесь за подбором",
    )
    rendered = render_article_writer_prompt(request, default_word_count=1800)

    assert "Как выбрать промышленный насос" in rendered
    assert "3000" in rendered
    assert "Инженеры и закупщики" in rendered
    assert "промышленный насос" in rendered
    assert "напор насоса" in rendered
    assert "Практическое руководство" in rendered
    assert "Обратитесь за подбором" in rendered
    assert '"outline"' in rendered
    assert "базы знаний нет" in rendered
    assert "анализа конкурентов нет" in rendered
    assert "{{" not in rendered


def test_render_injects_knowledge_context() -> None:
    rendered = render_article_writer_prompt(
        ArticleWriteInput(
            topic="Насос",
            knowledge_context="### Источник 1: Спека\nДавление 10 бар.",
        ),
        default_word_count=1800,
    )
    assert "Давление 10 бар" in rendered
    assert "базы знаний нет" not in rendered
    assert "{{knowledge_context}}" not in rendered


def test_render_uses_default_word_count_from_settings() -> None:
    rendered = render_article_writer_prompt(
        ArticleWriteInput(topic="Тема"),
    )
    expected = str(get_settings().article_target_word_count)
    assert expected in rendered
    assert "{{word_count}}" not in rendered


def test_writer_prompt_states_a_per_section_word_budget() -> None:
    request = ArticleWriteInput(
        topic="Тема",
        word_count=3000,
        outline=["Раздел 1", "Раздел 2", "Раздел 3"],
    )
    rendered = render_article_writer_prompt(request, default_word_count=1800)

    assert words_per_section(request, 3000) == 1000
    assert "1000" in rendered
    assert "{{" not in rendered


def test_words_per_section_falls_back_without_outline() -> None:
    request = ArticleWriteInput(topic="Тема")
    assert words_per_section(request, 3000) == 500


def test_render_article_expand_prompt_includes_the_current_draft() -> None:
    request = ArticleWriteInput(topic="Тема", word_count=3000)
    current = AIArticleOutput(
        title="Заголовок",
        meta_description="Описание",
        url_slug="zagolovok",
        content_markdown="# Заголовок\n\nКороткий черновик.",
        word_count=4,
    )
    rendered = render_article_expand_prompt(
        request,
        current=current,
        current_word_count=4,
        default_word_count=1800,
    )

    assert "Короткий черновик." in rendered
    assert "Заголовок" in rendered
    assert "zagolovok" in rendered
    assert "3000" in rendered
    assert "{{" not in rendered


def test_system_prompt_is_loaded_from_file() -> None:
    system_prompt = load_system_prompt()
    assert "JSON" in system_prompt
    assert system_prompt == system_prompt.strip()


def test_load_prompt_missing_file_is_safe_error(tmp_path: Path) -> None:
    with pytest.raises(AIConfigurationError, match="Prompt file"):
        load_prompt("missing.md", prompts_dir=tmp_path)


def test_prompts_dir_setting_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "article_writer.md").write_text(
        "custom {{topic}} {{brief_json}}", encoding="utf-8"
    )
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        assert get_prompts_dir() == tmp_path
        assert "custom" in load_prompt("article_writer.md")
    finally:
        get_settings.cache_clear()


def test_prompts_dir_never_resolves_into_site_packages() -> None:
    assert "site-packages" not in str(get_prompts_dir())


def test_render_seo_brief_prompt_substitutes_fields() -> None:
    rendered = render_seo_brief_prompt(
        SeoPlanInput(
            topic="Матрас",
            word_count=3000,
            outline=["Вес", "Поза"],
            primary_keywords=["жесткость"],
            competitor_context="H2 конкурентов",
        )
    )
    assert "Матрас" in rendered
    assert "жесткость" in rendered
    assert "H2 конкурентов" in rendered
    assert "{{" not in rendered


def test_render_fact_check_and_editor_prompts() -> None:
    draft = AIArticleOutput(
        title="Заголовок",
        meta_description="Описание",
        url_slug="zagolovok",
        content_markdown="# Тело\n\nГарантия 100 лет.",
        word_count=5,
    )
    fact_rendered = render_fact_check_prompt(
        FactCheckInput(
            topic="Матрас",
            title=draft.title,
            meta_description=draft.meta_description,
            content_markdown=draft.content_markdown,
            knowledge_context="Плотность 35",
        )
    )
    assert "Гарантия 100 лет" in fact_rendered
    assert "Плотность 35" in fact_rendered
    assert "{{" not in fact_rendered

    editor_rendered = render_editor_prompt(
        EditorInput(
            topic="Матрас",
            outline=["Вес", "FAQ"],
            draft=draft,
            fact_check=FactCheckOutput(
                verdict="needs_revision",
                issues=[
                    FactCheckIssue(
                        severity="warning",
                        claim="Гарантия 100 лет",
                        problem="Нет источника",
                        suggestion="Смягчить",
                    )
                ],
                notes="Проверить цифры",
            ),
        )
    )
    assert "needs_revision" in editor_rendered
    assert "Гарантия 100 лет" in editor_rendered
    assert "Смягчить" in editor_rendered
    assert "{{" not in editor_rendered


def test_render_image_generate_prompt() -> None:
    rendered = render_image_generate_prompt(
        topic="Матрас", alt="Слои кокоса", kind="infographic"
    )
    assert "Матрас" in rendered
    assert "Слои кокоса" in rendered
    assert "infographic" in rendered
    assert "простая схема" in rendered.lower()
    assert "Inter" in rendered
    assert "{{" not in rendered


def test_render_image_generate_prompt_asks_for_photo() -> None:
    rendered = render_image_generate_prompt(
        topic="Матрас",
        alt="Застеленная кровать с белым матрасом в светлой спальне",
        kind="image",
    )
    assert "фотореализм" in rendered.lower()
    assert "В кадре не должно быть людей" in rendered
    assert "16:9" in rendered
    assert "по центру кадра" in rendered
    assert "не обрезается" in rendered
    assert "Застеленная кровать с белым матрасом в светлой спальне" in rendered
    assert "Раздел, который иллюстрирует этот кадр" in rendered


def test_render_image_generate_prompt_uses_section_block() -> None:
    rendered = render_image_generate_prompt(
        topic="Матрас",
        alt="Описание изображения",
        kind="image",
        heading="Жёсткий матрас",
        excerpt="Жёсткий блок держит поясницу ровно.",
    )
    assert "Жёсткий матрас" in rendered
    assert "поясницу" in rendered
    assert "только этот раздел" in rendered.lower() or "этот раздел" in rendered


def test_image_scene_alt_replaces_generic_photo_alt() -> None:
    scene = image_scene_alt("Описание изображения", topic="Матрас", kind="image")
    assert "Реалистичное фото" in scene
    assert "Матрас" in scene
    assert "без людей" in scene
    assert image_scene_alt(
        "Застеленная кровать", topic="Матрас", kind="image"
    ) == "Застеленная кровать"
    scene = image_scene_alt(
        "фото",
        topic="Матрас",
        kind="image",
        heading="Мягкий матрас",
        excerpt="Плечо проваливается в мягкий блок.",
    )
    assert "Мягкий матрас" in scene
    assert "Плечо" in scene
    hero = image_scene_alt(
        "фото",
        topic="Матрас",
        kind="hero",
        title="Жесткий или мягкий матрас: какой лучше выбрать?",
    )
    assert "Жесткий или мягкий матрас: какой лучше выбрать?" in hero
    assert "Главный кадр" in hero


def test_render_dzen_prompt() -> None:
    rendered = render_dzen_prompt(
        DzenWriteInput(
            source_title="Как выбрать матрас",
            source_markdown="# Длинный текст статьи",
            target_char_count=4000,
        )
    )
    assert "Как выбрать матрас" in rendered
    assert "Длинный текст статьи" in rendered
    assert "4000" in rendered
    assert "DZEN_COVER_PLACEHOLDER" in rendered
    assert "{{" not in rendered


def test_render_detector_prompt() -> None:
    rendered = render_detector_prompt(
        DetectorInput(
            title="Как выбрать матрас",
            content_markdown="# Черновик статьи",
            language="ru",
        )
    )
    assert "Как выбрать матрас" in rendered
    assert "Черновик статьи" in rendered
    assert "{{" not in rendered


def test_render_humanizer_prompt() -> None:
    rendered = render_humanizer_prompt(
        HumanizerInput(
            title="Как выбрать матрас",
            meta_description="Гид",
            url_slug="kak-vybrat-matras",
            content_markdown="![Кадр](images/image-1.png)\n\nТекст.",
            language="ru",
            audience="покупатели",
            detector_notes="ровный ритм",
        )
    )
    assert "покупатели" in rendered
    assert "ровный ритм" in rendered
    assert "kak-vybrat-matras" in rendered
    assert "images/image-1.png" in rendered
    assert "{{" not in rendered


def test_render_summary_prompt() -> None:
    rendered = render_summary_prompt(
        SummaryInput(
            title="Как выбрать матрас",
            content_markdown="# Длинный текст",
            language="ru",
            target_char_count=500,
        )
    )
    assert "Как выбрать матрас" in rendered
    assert "Длинный текст" in rendered
    assert "500" in rendered
    assert "{{" not in rendered


def test_render_topic_discovery_prompt() -> None:
    rendered = render_topic_discovery_prompt(
        TopicPlanInput(
            niche="матрасы",
            seeds=["жесткость матраса"],
            language="ru",
            audience="покупатели",
            max_topics=5,
            candidates=[
                TopicCandidate(
                    text="Как выбрать жесткость матраса",
                    kind=CandidateKind.ORGANIC,
                    engine=SearchEngine.GOOGLE,
                    query="жесткость матраса",
                )
            ],
        )
    )
    assert "матрасы" in rendered
    assert "жесткость матраса" in rendered
    assert "покупатели" in rendered
    assert "Как выбрать жесткость матраса" in rendered
    assert "{{" not in rendered


def test_render_competitor_gap_prompt() -> None:
    rendered = render_competitor_gap_prompt(
        ContentGapInput(
            domain="goodnight.by",
            niche="товары для сна",
            audience="Покупатели матрасов",
            geo="Беларусь",
            site_type="интернет-магазин",
            language="ru",
            max_topics=80,
            hits=[
                ContentGapHit(
                    text="kak vybrat matras",
                    competitor="promatras",
                    kind="url",
                    url="https://promatras.by/kak-vybrat-matras",
                    source_file="promatras.xlsx",
                )
            ],
        )
    )
    assert "goodnight.by" in rendered
    assert "kak vybrat matras" in rendered
    assert "promatras" in rendered
    assert "{{" not in rendered

