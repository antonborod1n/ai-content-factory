"""Word counting for generated article content."""

import re

# Any Unicode letter or digit, excluding the underscore.
_WORD_CHAR_RE = re.compile(r"[^\W_]", re.UNICODE)


def count_characters(content_markdown: str) -> int:
    """Count characters in Markdown source, including spaces (Dzen length)."""
    return len(content_markdown or "")


def count_words(content_markdown: str) -> int:
    """Count words in Markdown source.

    Counts whitespace-separated tokens that contain at least one letter or
    digit, so Markdown syntax such as ``#``, ``-`` or ``**`` is not counted.
    """
    return sum(
        1 for token in content_markdown.split() if _WORD_CHAR_RE.search(token)
    )
