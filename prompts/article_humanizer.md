Ты «очеловечиваешь» экспертную статью для аудитории ниже: живой ритм, меньше
канцелярита, все факты на месте. Новых цифр и обещаний не выдумывай.

Язык: {{language}}
Аудитория: {{audience}}

## Заметки детектора (если есть)

{{detector_notes}}

## Замечания фактчекера (если есть)

{{fact_check_notes}}

## Черновик

title: {{current_title}}
meta_description: {{current_meta_description}}
url_slug: {{current_url_slug}}

{{current_markdown}}

## Задача

1. Если выше есть замечания фактчекера — смягчи или убери спорные утверждения.
   Новых фактов и цифр не добавляй.
2. Перепиши абзацы более естественно: разная длина фраз, меньше штампов.
3. Сохрани смысл, H1/H2/H3 с жирным оформлением, таблицы, списки, FAQ, CTA,
   callout-блоки.
4. Сохрани markdown-картинки и внутренние ссылки **как есть**
   (`![...](...)` и `[текст](/slug)` не ломай, не переноси и не выкидывай).
5. `url_slug` верни без изменений. `title` и `meta_description` можно чуть
   поправить, тему не меняй.
6. Не сокращай статью: объём после правки — не меньше 90% черновика.

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "title": "string",
  "meta_description": "string",
  "url_slug": "string",
  "content_markdown": "string",
  "word_count": 0
}
