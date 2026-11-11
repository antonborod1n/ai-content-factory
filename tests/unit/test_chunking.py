"""Unit tests for document text chunking."""

import pytest

from app.core.chunking import chunk_text


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("   \n") == []


def test_short_text_is_a_single_chunk() -> None:
    text = "Короткий абзац про промышленный насос."
    assert chunk_text(text, chunk_size=800, chunk_overlap=120) == [text]


def test_long_text_is_split_and_overlaps() -> None:
    paragraphs = [f"Параграф номер {index} " + ("слово " * 20) for index in range(8)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, chunk_size=180, chunk_overlap=40)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    # Overlap: some tokens from an earlier chunk reappear in the next one.
    assert any(
        token in chunks[1]
        for token in chunks[0].split()[-5:]
    )


def test_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, chunk_overlap=10)
