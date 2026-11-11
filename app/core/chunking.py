"""Split extracted document text into overlapping chunks."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"[ \t]+")
_PARAGRAPH_RE = re.compile(r"\n{2,}")


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries.

    ``chunk_size`` and ``chunk_overlap`` are character counts of the normalized
    source. Overlap must be smaller than chunk size. Empty input yields no
    chunks.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized = _normalize(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    paragraphs = [part for part in _PARAGRAPH_RE.split(normalized) if part]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            pieces.append(paragraph)
        else:
            pieces.extend(_split_long_paragraph(paragraph, chunk_size))

    return _pack_with_overlap(pieces, chunk_size, chunk_overlap)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    words = paragraph.split(" ")
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        extra = len(word) if not current else len(word) + 1
        if current and current_len + extra > chunk_size:
            parts.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra
    if current:
        parts.append(" ".join(current))
    return parts


def _pack_with_overlap(
    pieces: list[str], chunk_size: int, chunk_overlap: int
) -> list[str]:
    chunks: list[str] = []
    buffer = ""
    for piece in pieces:
        candidate = piece if not buffer else f"{buffer}\n\n{piece}"
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            buffer = _overlap_suffix(buffer, chunk_overlap)
            remainder = piece if not buffer else f"{buffer}\n\n{piece}"
            if len(remainder) <= chunk_size:
                buffer = remainder
            else:
                # Piece still does not fit with overlap; emit it on its own.
                if buffer:
                    chunks.append(buffer)
                buffer = piece
        else:
            chunks.append(piece)
            buffer = _overlap_suffix(piece, chunk_overlap)
    if buffer and (not chunks or chunks[-1] != buffer):
        chunks.append(buffer)
    return [item for item in chunks if item.strip()]


def _overlap_suffix(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return text
    suffix = text[-overlap:]
    space = suffix.find(" ")
    if 0 <= space < len(suffix) - 1:
        return suffix[space + 1 :]
    return suffix
