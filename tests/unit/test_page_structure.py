"""HTML structure parser (deterministic, no network)."""

from app.core.page_structure import parse_html


def test_parse_html_extracts_headings_and_counts() -> None:
    html = """
    <html><head><title>Гид по матрасам</title>
    <script>var x = 1;</script>
    </head><body>
      <h1>Главное</h1>
      <h2>Для кого жесткий матрас</h2>
      <p>Текст про вес покупателя и позу сна на спине.</p>
      <h2>FAQ</h2>
      <ul><li>Один</li></ul>
      <table><tr><td>A</td></tr></table>
      <img src="/a.jpg">
      <iframe src="https://www.youtube.com/embed/zz"></iframe>
    </body></html>
    """
    structure = parse_html(html)
    assert structure.title == "Гид по матрасам"
    assert "Для кого жесткий матрас" in structure.headings
    assert structure.image_count == 1
    assert structure.video_count == 1
    assert structure.list_count == 1
    assert structure.table_count == 1
    assert structure.has_faq is True
    assert "faq" in structure.features
    assert structure.infographic_count == 0
    assert structure.word_count >= 5
    assert structure.char_count >= 40
    assert "var x" not in " ".join(structure.headings)
    faq = next(item for item in structure.sections if item.heading == "FAQ")
    assert faq.image_count == 1


def test_parse_html_counts_images_per_heading() -> None:
    html = """
    <body>
      <h2>Жесткий матрас</h2>
      <img src="/firm.jpg">
      <img src="/firm-2.jpg">
      <h2>Мягкий матрас</h2>
      <p>Текст</p>
      <h2>FAQ</h2>
      <img src="/faq.jpg">
    </body>
    """
    structure = parse_html(html)
    by_heading = {item.heading: item.image_count for item in structure.sections}
    assert by_heading["Жесткий матрас"] == 2
    assert by_heading["Мягкий матрас"] == 0
    assert by_heading["FAQ"] == 1


def test_parse_html_counts_infographics_from_alt() -> None:
    html = """
    <body>
      <h2>Сравнение</h2>
      <img src="/photo.jpg" alt="матрас в интерьере">
      <img src="/chart.png" alt="схема жесткости">
    </body>
    """
    structure = parse_html(html)
    assert structure.image_count == 2
    assert structure.infographic_count == 1
    assert "infographics:1" in structure.features


def test_parse_html_skips_data_images() -> None:
    structure = parse_html('<img src="data:image/gif;base64,AAAA"><img src="">')
    assert structure.image_count == 0
