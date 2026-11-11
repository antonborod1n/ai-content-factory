Ты SEO-стратег. Нужно усилить план статьи и SEO-обёртку (title / description /
slug / ключи / intent). Текст конкурентов копировать нельзя.

Тема: {{topic}}
Язык: {{language}}
Аудитория: {{audience}}
Целевой объём: {{word_count}} слов
Search intent сейчас: {{search_intent}}
Цель статьи сейчас: {{article_goal}}
Ключевые слова (все): {{keywords}}
Основные ключи: {{primary_keywords}}
Дополнительные ключи: {{secondary_keywords}}

## Текущий outline

{{outline}}

## Контекст конкурентов (структура и SEO-подсказки, не полный текст)

{{competitor_context}}

## Задача

1. Дай 6–10 пунктов `outline` (H2). Сохрани полезные разделы, убери дубли,
   добавь пробелы покрытия, если они очевидны из контекста конкурентов.
2. Уточни `primary_keywords` (1–5) и `secondary_keywords` (0–8).
3. Уточни `search_intent` одной короткой меткой (например
   informational_commercial).
4. Дай сильные `title_hint`, `meta_description_hint` и латинский
   `url_slug_hint` (строчные буквы, цифры, дефисы).
5. `article_goal` — одна фраза, зачем статья лучше выдачи.
6. `notes` — кратко, без URL-простыни.
7. Не обещай реальные картинки, видео, перелинковку или CMS.

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "outline": ["string", "string"],
  "primary_keywords": ["string"],
  "secondary_keywords": ["string"],
  "search_intent": "string",
  "title_hint": "string",
  "meta_description_hint": "string",
  "url_slug_hint": "string",
  "article_goal": "string",
  "notes": "string"
}
