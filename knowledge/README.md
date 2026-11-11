# Тестовые материалы базы знаний

Файлы в этой папке — **учебные**, не реальный каталог. Их можно загрузить в Stage 2
и проверить, что статья опирается на факты из документов.

Тема совпадает с [`topics/topics.json`](../topics/topics.json): выбор жёсткости матраса.

| Файл | Формат | О чём |
| --- | --- | --- |
| `goodnight-by-project-brief.md` | Markdown | Контекст клиента: сайт, гео, конкуренты, что не писать. **Не** таблица тем |
| `mattress-firmness-guide.md` | Markdown | Шкала жёсткости, вес, поза сна, линейка Orion |
| `mattress-faq.txt` | Текст | Короткие ответы покупателям |
| `warranty-and-care.md` | Markdown | Гарантия, уход, типичные ошибки |

Как загрузить (API должен быть на `localhost:8000`):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/upload -F "file=@knowledge/goodnight-by-project-brief.md" -F "title=Контекст проекта goodnight.by"
curl.exe -X POST http://localhost:8000/api/v1/documents/upload -F "file=@knowledge/mattress-firmness-guide.md" -F "title=Гайд по жёсткости"
curl.exe -X POST http://localhost:8000/api/v1/documents/upload -F "file=@knowledge/mattress-faq.txt" -F "title=FAQ по матрасам"
curl.exe -X POST http://localhost:8000/api/v1/documents/upload -F "file=@knowledge/warranty-and-care.md" -F "title=Гарантия и уход"
```

Темы статей из контент-плана конкурентов — не сюда, а в `topics/` через
`POST /api/v1/competitor-topics/sources` или `scripts/import_competitor_plan.py`
(GUIDE §5.2b).

Проверка поиска:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/search -H "Content-Type: application/json" -d "{\"query\":\"goodnight.by гео Беларусь Promatras\"}"
curl.exe -X POST http://localhost:8000/api/v1/documents/search -H "Content-Type: application/json" -d "{\"query\":\"жёсткость матраса Orion вес покупателя\"}"
```

Маркеры, по которым видно, что RAG сработал (их нет в обычном brief):

- домен **goodnight.by**, цены в **BYN**, запрет «лечения» (Бехтерев / препараты)
- шкала **ACF-H1…ACF-H5**
- серия **Orion Comfort / Orion Support**
- гарантия чехла **36 месяцев**, блока **18 месяцев**
- порог веса **92 кг** для перехода на жёсткий
