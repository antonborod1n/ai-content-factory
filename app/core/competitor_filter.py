"""Which SERP hits count as competitor *articles*. Deterministic, no AI/SQL."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.http_url import is_public_http_url
from app.core.page_structure import PageStructure

DEFAULT_MIN_ARTICLE_CHARS = 300

# Video / short-form hosts — not written articles.
_VIDEO_HOSTS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "rutube.ru",
    "tiktok.com",
    "dailymotion.com",
    "twitch.tv",
)

# Social feeds, not editorial pages we can outline.
_SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "vk.com",
    "ok.ru",
    "twitter.com",
    "x.com",
    "pinterest.com",
    "reddit.com",
    "t.me",
    "telegram.me",
    "telegram.org",
)

# Marketplaces and classifieds — product cards, not articles.
_MARKETPLACE_HOSTS = (
    "wildberries.ru",
    "ozon.ru",
    "ozon.com",
    "avito.ru",
    "youla.ru",
    "amazon.com",
    "amazon.co.uk",
    "aliexpress.com",
    "aliexpress.ru",
    "alibaba.com",
    "ebay.com",
    "market.yandex.ru",
    "megamarket.ru",
    "sbermegamarket.ru",
    "lamoda.ru",
    "dns-shop.ru",
    "citilink.ru",
    "mvideo.ru",
    "eldorado.ru",
)

_BLOCKED_HOSTS = _VIDEO_HOSTS + _SOCIAL_HOSTS + _MARKETPLACE_HOSTS

# Shop / catalog URL segments. Brand blogs (/blog, /article) stay eligible.
_SHOP_PATH_SEGMENTS = frozenset(
    {
        "catalog",
        "catalogue",
        "category",
        "categories",
        "product",
        "products",
        "tovar",
        "goods",
        "cart",
        "basket",
        "checkout",
        "shop",
        "store",
        "collection",
        "collections",
        "sku",
        "kupit",
        "buy",
    }
)

_PRODUCT_PAGE_MARKERS = (
    'property="og:type" content="product"',
    "property='og:type' content='product'",
    "schema.org/product",
    "schema.org/itemlist",
    '"@type":"product"',
    '"@type": "product"',
    "'@type': 'product'",
    '"@type":"itemlist"',
    '"@type": "itemlist"',
)

_ARTICLE_PAGE_MARKERS = (
    'property="og:type" content="article"',
    "property='og:type' content='article'",
    "schema.org/article",
    "schema.org/blogposting",
    "schema.org/newsarticle",
    '"@type":"article"',
    '"@type": "article"',
    '"@type":"blogposting"',
    '"@type": "blogposting"',
    '"@type":"newsarticle"',
    '"@type": "newsarticle"',
)


def is_competitor_article_url(url: str) -> bool:
    """True when the URL can be a public written article, not a shop/video hit."""
    if not is_public_http_url(url):
        return False
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if _host_is_blocked(host):
        return False
    segments = [part.casefold() for part in parsed.path.split("/") if part]
    if any(part in _SHOP_PATH_SEGMENTS for part in segments):
        return False
    return True


def is_usable_competitor_article(
    structure: PageStructure,
    *,
    html: str = "",
    min_chars: int = DEFAULT_MIN_ARTICLE_CHARS,
) -> bool:
    """True when fetched HTML looks like a real article of enough length."""
    if min_chars < 0:
        min_chars = 0
    if structure.char_count < min_chars:
        return False
    if not structure.headings:
        return False
    if html and _looks_like_product_page(html):
        return False
    return True


def _host_is_blocked(host: str) -> bool:
    normalized = host.removeprefix("www.")
    return any(
        normalized == suffix or normalized.endswith("." + suffix)
        for suffix in _BLOCKED_HOSTS
    )


def _looks_like_product_page(html: str) -> bool:
    lowered = html.casefold()
    if any(marker in lowered for marker in _ARTICLE_PAGE_MARKERS):
        return False
    return any(marker in lowered for marker in _PRODUCT_PAGE_MARKERS)
