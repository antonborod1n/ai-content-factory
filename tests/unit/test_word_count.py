"""Unit tests for the word counting helper."""

from app.core.word_count import count_words


def test_counts_plain_words() -> None:
    assert count_words("one two three") == 3


def test_ignores_markdown_syntax_tokens() -> None:
    assert count_words("# Heading\n\n- item one\n- item two") == 5


def test_counts_words_with_inline_markup() -> None:
    assert count_words("**bold** and _italic_ text") == 4


def test_handles_extra_whitespace_and_newlines() -> None:
    assert count_words("  first\n\n\tsecond   third  ") == 3


def test_counts_cyrillic_words() -> None:
    assert count_words("# Как выбрать насос") == 3


def test_empty_content_is_zero() -> None:
    assert count_words("") == 0
    assert count_words("\n\n   ") == 0
    assert count_words("### --- ***") == 0
