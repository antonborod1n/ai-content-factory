"""URL and content filters for Stage 3 competitor articles."""

from app.core.competitor_filter import (
    is_competitor_article_url,
    is_usable_competitor_article,
)
from app.core.page_structure import parse_html

_LONG = (
    "Выбор жесткости матраса зависит от веса, привычной позы сна и состояния "
    "спины. Слишком мягкая модель даёт провал поясницы, слишком жёсткая "
    "создаёт давление на плечи и бёдра. Ниже разбираем, кому какой вариант "
    "подходит, какие ошибки чаще совершают при первой покупке и как отличить "
    "маркетинговый ярлык от реальной поддержки позвоночника ночью."
)


def test_rejects_video_and_social_hosts() -> None:
    assert is_competitor_article_url("https://www.youtube.com/watch?v=abc") is False
    assert is_competitor_article_url("https://youtu.be/abc") is False
    assert is_competitor_article_url("https://rutube.ru/video/abc") is False
    assert is_competitor_article_url("https://vk.com/video-1_2") is False
    assert is_competitor_article_url("https://www.tiktok.com/@x/video/1") is False


def test_rejects_marketplaces_and_shop_paths() -> None:
    assert (
        is_competitor_article_url("https://www.wildberries.ru/catalog/123/detail.aspx")
        is False
    )
    assert is_competitor_article_url("https://ozon.ru/product/matras-1") is False
    assert is_competitor_article_url("https://hoff.ru/catalog/matrasy/") is False
    assert is_competitor_article_url("https://askona.ru/product/orion") is False


def test_keeps_editorial_urls_including_brand_blogs() -> None:
    assert is_competitor_article_url("https://example.com/firm-mattress") is True
    assert (
        is_competitor_article_url(
            "https://www.askona.ru/blog/article/kak-vybrat-zhestkost-matrasa/"
        )
        is True
    )
    assert (
        is_competitor_article_url(
            "https://hoff.ru/blog/zhestkost-matrasa-kak-podobrat/"
        )
        is True
    )


def test_rejects_short_or_headingless_pages() -> None:
    short = parse_html("<h1>Тема</h1><p>Мало текста.</p>")
    assert is_usable_competitor_article(short, min_chars=300) is False

    no_heading = parse_html(f"<p>{_LONG}</p>")
    assert is_usable_competitor_article(no_heading, min_chars=300) is False


def test_keeps_long_article_html() -> None:
    structure = parse_html(f"<h1>Жесткость матраса</h1><p>{_LONG}</p>")
    assert structure.char_count >= 300
    assert is_usable_competitor_article(structure, min_chars=300) is True


def test_rejects_product_schema_without_article() -> None:
    html = f"""
    <html><head>
      <meta property="og:type" content="product">
    </head><body>
      <h1>Матрас Orion</h1>
      <p>{_LONG}</p>
    </body></html>
    """
    structure = parse_html(html)
    assert is_usable_competitor_article(structure, html=html, min_chars=300) is False


def test_keeps_article_schema_even_with_product_widget() -> None:
    html = f"""
    <html><head>
      <meta property="og:type" content="article">
      <script type="application/ld+json">{{"@type":"Product"}}</script>
    </head><body>
      <h1>Как выбрать жесткость</h1>
      <p>{_LONG}</p>
    </body></html>
    """
    structure = parse_html(html)
    assert is_usable_competitor_article(structure, html=html, min_chars=300) is True
