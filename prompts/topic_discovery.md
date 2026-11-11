# Topic Discovery — контент-план из выдачи

Собери уникальные темы статей из кандидатов поисковой выдачи Google и Яндекс.

Ниша: {{niche}}
Сиды: {{seeds}}
Язык: {{language}}
Аудитория: {{audience}}
Максимум тем: {{max_topics}}

Кандидаты (organic titles, People Also Ask, related searches):

{{candidates_json}}

Правила:

- Кластеризуй близкие формулировки в одну тему. Не плоди синонимы.
- Тема должна опираться на кандидатов. Не выдумывай запросы, которых нет в списке.
- Предпочитай информационные и информационно-коммерческие экспертные углы под
  указанную аудиторию.
- `topic` — готовый заголовок статьи на языке {{language}}.
- `primary_keywords` — 1–3 главных запроса; `secondary_keywords` — смежные из выдачи.
- `article_goal` — одна фраза, зачем статья читателю.
- `outline` — 6–10 пунктов H2, черновик (позже его может заменить research).
- `search_intent` — по кандидатам: `informational`, `informational_commercial`
  или `commercial`.
- Верни не больше {{max_topics}} тем.

Ответ — только один валидный JSON-объект без блоков кода и комментариев:

{
  "topics": [
    {
      "topic": "",
      "primary_keywords": [],
      "secondary_keywords": [],
      "article_goal": "",
      "outline": [],
      "search_intent": "informational_commercial"
    }
  ]
}
