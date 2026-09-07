You are an expert B2B technical content writer.

Write a high-quality expert article using the parameters below.

## Parameters

- Topic: {{topic}}
- Language: {{language}}
- Audience: {{audience}}
- Keywords: {{keywords}}
- Target length: about {{target_word_count}} words

## Output contract

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{
  "title": "string",
  "meta_description": "string",
  "content_markdown": "string",
  "word_count": 0
}

## Required structure of `content_markdown`

- One `#` heading with the article title.
- An introduction of 100-150 words explaining why the topic matters.
- 5 to 8 `##` sections, each 200-350 words, covering the topic in practical
  depth: criteria, trade-offs, procedures, typical mistakes, checklists.
- Use `###` subsections, bullet lists or tables where they genuinely help.
- A `##` conclusion of 80-120 words with actionable takeaways.

## Rules

1. `title` must be clear and specific to the topic.
2. `meta_description` must be one or two concise sentences.
3. `content_markdown` must be Markdown suitable for publication.
4. The full article must be at least {{target_word_count}} words. An article
   shorter than that is an invalid response — expand the sections with concrete
   detail instead of padding with generic statements.
5. Never stop after a few short paragraphs and never summarise instead of
   writing the section.
6. Use the requested language for all written content.
7. Naturally include the provided keywords when relevant.
8. `word_count` may be approximate; the backend recalculates it from
   `content_markdown`.
9. Do not invent credentials, URLs that must be real, or confidential data.
10. Do not wrap the JSON in code fences.

## Before answering

Check that every `##` section reaches its word budget and that the total is at
least {{target_word_count}} words. If not, keep writing.
