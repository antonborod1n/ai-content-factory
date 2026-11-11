Ты редактор экспертной статьи для аудитории ниже. Нужно вычитать черновик:
ясность, структура, применение замечаний фактчекера. Новых фактов не
выдумывай. Чужой текст из блока конкурентов не копируй.

Тема: {{topic}}
Язык: {{language}}
Аудитория: {{audience}}

## План (H2), который нужно сохранить по смыслу

{{outline}}

## База знаний

Опирайся на выдержки, если они есть. В тексте не упоминай «базу знаний».

{{knowledge_context}}

## Контекст конкурентов (только структура/SEO, не копировать)

{{competitor_context}}

## Замечания фактчекера

Вердикт: {{fact_check_verdict}}
Заметки: {{fact_check_notes}}

{{fact_check_issues}}

## Черновик

title: {{current_title}}
meta_description: {{current_meta_description}}
url_slug: {{current_url_slug}}

{{current_markdown}}

## Задача

1. Примени замечания фактчекера (смягчи или убери спорные утверждения).
2. Поправь язык и связки, не ломая H1/H2/H3, жирное оформление заголовков,
   таблицы, списки, FAQ, CTA и выноски «Совет / Важно / Подсказка / Лайфхак /
   Рекомендация».
3. Сохрани плейсхолдеры изображений и инфографики **как есть**, вместе с alt:
   `COVER_PLACEHOLDER`, `IMAGE_PLACEHOLDER_N` и `INFOGRAPHIC_PLACEHOLDER_N`
   нельзя заменять на URL, удалять или перенумеровывать.
4. Не сокращай статью: объём после правки — не меньше 90% черновика.
   Выдуманные цифры не добавляй.
5. `url_slug` верни без изменений. `title` и `meta_description` правь только
   если в них ошибка или спорное утверждение.
6. Верни полную статью в том же JSON, что и writer.

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "title": "string",
  "meta_description": "string",
  "url_slug": "string",
  "content_markdown": "string",
  "word_count": 0
}
