Я хочу, чтобы вы выступили в роли опытного контент-райтера и SEO-специалиста,
свободно владеющего языком статьи (поле language: {{language}}; для `ru` —
русский). Напишите уникальную (100%) SEO-оптимизированную статью объемом
{{word_count}} слов, написанную «живым» человеческим языком (с использованием
заголовков H1, H2, H3 и H4), которая раскрывает тему, указанную в запросе.
Излагайте материал своими словами, не копируя текст из других источников. При
создании контента учитывайте показатели «перплексии» (сложности и разнообразия
лексики) и «берстиности» (вариативности структуры предложений), обеспечивая их
высокий уровень без потери конкретики и контекста. Используйте развернутые,
увлекательные абзацы. Пишите в разговорном стиле, характерном для живого
человека (неформальный тон, личные местоимения, простой язык, активный залог,
краткие формулировки, риторические вопросы, аналогии и метафоры). Важно
выделить жирным шрифтом заголовок и все подзаголовки статьи, а также
использовать соответствующие теги H. Не нумеруйте заголовки. В статье
рекомендуется использовать таблицы, маркированные списки и различные способы
выделения текста. Укажите места для вставки изображений или инфографики.

Целевая аудитория: {{audience}}
Тон: {{tone}}
Цель статьи: {{article_goal}}
Search intent: {{search_intent}}
CTA: {{cta}}

Теперь напишите статью, следуя этому плану:

{{brief_json}}

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "title": "string",
  "meta_description": "string",
  "url_slug": "string",
  "content_markdown": "string",
  "word_count": 0
}

## SEO fields (`title`, `meta_description`, `url_slug`)

1. `title`:
   - one clear line, specific to the topic (not clickbait spam);
   - include a primary keyword naturally when it fits;
   - roughly 50–70 characters (soft limit; do not pad with junk).
2. `meta_description`:
   - 1–2 sentences, benefit-oriented, in the article language;
   - roughly 140–160 characters (soft limit);
   - no keyword stuffing; invite the reader to open the article.
3. `url_slug`:
   - lowercase Latin letters, digits and hyphens only;
   - transliterate from the topic (e.g. «Жесткий или мягкий матрас» →
     `zhestkiy-ili-myagkiy-matras`);
   - no spaces, no underscores, no leading/trailing hyphens;
   - short and readable (about 3–8 words).

## Markdown rules for `content_markdown`

1. Use Markdown headings: `#` (H1), `##` (H2), `###` (H3), `####` (H4).
2. Make every heading bold as well, e.g. `# **Заголовок**`, `## **Раздел**`.
3. Do not number headings.
4. Follow the `outline` from the plan for section order when outline is not empty.
5. If `include_tables` is true — include Markdown tables where useful.
6. If `include_lists` is true — include bullet/numbered lists.
7. If `include_faq` is true — add an FAQ section with about `faq_count` Q&A pairs.
8. Insert exactly `image_placeholders` image placeholders like:
   `![Описание изображения](IMAGE_PLACEHOLDER_1)`
9. Insert exactly `infographic_placeholders` infographic placeholders like:
   `![Инфографика](INFOGRAPHIC_PLACEHOLDER_1)`
10. Naturally use `primary_keywords` and `secondary_keywords`.
11. End with a conclusion that includes the CTA when `cta` is not empty.
12. Write the full article in the requested language.
13. Length is a hard requirement: `content_markdown` must contain at least
    {{word_count}} words. Budget roughly {{words_per_section}} words per outline
    section. Never stop after a short draft and never compress a section into a
    couple of sentences — if you run short, add concrete examples, comparisons,
    numbers, checklists and step-by-step advice.
14. `word_count` in the JSON may be approximate; the backend recalculates it.
15. Do not invent credentials, real URLs that must resolve, or confidential data.
16. Do not wrap the JSON in code fences.
17. Where it fits the text (not in every section), add short callout blocks using
    one of these labels: **Совет**, **Важно**, **Подсказка**, **Лайфхак**,
    **Рекомендация**. Do not dump all five into one article — usually 2–4
    callouts total is enough. Place them next to practical advice, not in the
    introduction spam. Format each as a Markdown blockquote, for example:

    > **Важно:** не выбирайте матрас только по цене — смотрите на поддержку
    > позвоночника в вашей позе сна.

18. Avoid robotic filler («В этой статье мы рассмотрим…» repeated). Vary
    sentence length. Prefer concrete examples over empty claims.
