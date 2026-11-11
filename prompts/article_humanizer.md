Ты «очеловечиваешь» экспертную статью для аудитории ниже: живой ритм, меньше
канцелярита, все факты на месте. Новых цифр и обещаний не выдумывай.

Язык: {{language}}
Аудитория: {{audience}}

## Заметки детектора (если есть)

{{detector_notes}}

## Черновик

title: {{current_title}}
meta_description: {{current_meta_description}}
url_slug: {{current_url_slug}}

{{current_markdown}}

## Задача

1. Перепиши абзацы более естественно: разная длина фраз, меньше штампов.
2. Сохрани смысл, H1/H2/H3 с жирным оформлением, таблицы, списки, FAQ, CTA,
   callout-блоки.
3. Сохрани markdown-картинки и внутренние ссылки **как есть**
   (`![...](...)` и `[текст](/slug)` не ломай, не переноси и не выкидывай).
4. `url_slug` верни без изменений. `title` и `meta_description` можно чуть
   поправить, тему не меняй.
5. Не сокращай статью: объём после правки — не меньше 90% черновика.

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "title": "string",
  "meta_description": "string",
  "url_slug": "string",
  "content_markdown": "string",
  "word_count": 0
}
