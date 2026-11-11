"""In-memory PageFetcher for tests."""

from __future__ import annotations

_BODY = (
    "Выбор жесткости матраса зависит от веса, привычной позы сна и состояния "
    "спины. Слишком мягкая модель даёт провал поясницы, слишком жёсткая "
    "создаёт давление на плечи и бёдра. Ниже разбираем, кому какой вариант "
    "подходит, какие ошибки чаще совершают при первой покупке и как не "
    "перепутать маркетинговые ярлыки с реальной поддержкой позвоночника."
)

_DEFAULT_PAGES: dict[str, str] = {
    "https://example.com/firm-mattress": f"""
        <html><head><title>Жесткий матрас: плюсы и минусы</title></head>
        <body>
          <h1>Жесткий матрас</h1>
          <h2>Для кого подходит жесткий матрас</h2>
          <p>{_BODY}</p>
          <p>Покупателям от девяноста двух килограмм чаще нужен жесткий блок.</p>
          <img src="https://example.com/firm.jpg" alt="жесткий матрас">
          <h2>Ошибки при выборе жесткости</h2>
          <ul><li>Брать самый жесткий «на вырост»</li></ul>
          <h2>FAQ</h2>
          <table><tr><td>Вес</td><td>Жесткость</td></tr></table>
          <img src="https://example.com/faq.jpg" alt="схема">
        </body></html>
        """,
    "https://example.com/soft-mattress": f"""
        <html><head><title>Мягкий матрас для сна на боку</title></head>
        <body>
          <h1>Мягкий матрас</h1>
          <h2>Сон на боку и плечо</h2>
          <p>{_BODY}</p>
          <p>Мягкая модель помогает плечу проваливаться.</p>
          <img src="https://example.com/soft.jpg" alt="мягкий матрас">
          <h2>Когда мягкий матрас не подходит</h2>
          <ol><li>Сон на животе</li></ol>
          <iframe src="https://www.youtube.com/embed/abc"></iframe>
        </body></html>
        """,
    "https://example.com/firmness-guide": f"""
        <html><head><title>Как выбрать жесткость матраса</title></head>
        <body>
          <h1>Как выбрать жесткость</h1>
          <h2>Вес и поза сна</h2>
          <p>{_BODY}</p>
          <p>Сведите вес и привычную позу в одну таблицу подбора.</p>
          <img src="https://example.com/weight.jpg" alt="вес">
          <h2>Средняя жесткость как компромисс</h2>
          <h2>Заключение</h2>
        </body></html>
        """,
}


class MockPageFetcher:
    """Returns canned HTML for known URLs. Unknown URLs yield None."""

    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.pages = dict(_DEFAULT_PAGES if pages is None else pages)
        self.calls: list[str] = []

    async def fetch(self, url: str) -> str | None:
        self.calls.append(url)
        html = self.pages.get(url)
        return html
