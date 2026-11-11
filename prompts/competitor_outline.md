Ты SEO-стратег. По разбору ТОП-статей конкурентов нужно собрать **улучшенный
план** нашей статьи. Текст конкурентов копировать нельзя — только структура,
пробелы в покрытии темы и SEO-обёртка.

Тема: {{topic}}
Язык: {{language}}
Аудитория: {{audience}}
Целевой объём нашей статьи: {{word_count}} слов
Ключевые слова: {{keywords}}

## Профили конкурентов

Ниже JSON: title, url, snippet, headings (H1–H3), section_images
(картинки по каждому H2/H3), word_count, image_count, video_count,
list_count, table_count, has_faq, features. Это не полный текст страниц.
Число картинок в нашей статье бэкенд возьмёт из средних section_images —
в плане не обещай реальные фото и не возвращай counts.

{{competitor_profiles}}

## Задача

1. Покрой темы, которые есть у нескольких конкурентов.
2. Добавь разделы, которых у них нет, если они полезны читателю.
3. Убери дубли заголовков. 6–10 пунктов плана (H2).
4. Если у конкурентов есть FAQ / таблицы / списки — заложи это в план
   (пункт FAQ, если уместно). Не обещай реальные картинки или видео.
5. Дай более сильные, чем у выдачи, `title_hint`, `meta_description_hint`
   и латинский `url_slug_hint` (строчные буквы, цифры, дефисы).
6. `article_goal` — одна фраза, зачем статья лучше конкурентов.
7. `notes` — кратко: чего не хватает в выдаче (без URL-простыни).

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "outline": ["string", "string"],
  "title_hint": "string",
  "meta_description_hint": "string",
  "url_slug_hint": "string",
  "article_goal": "string",
  "notes": "string"
}
