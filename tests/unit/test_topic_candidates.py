"""Normalize / dedupe helpers for Topic Discovery."""

from app.core.topic_candidates import (
    dedupe_candidates,
    dedupe_texts,
    is_near_duplicate,
    jaccard_similarity,
    normalize_topic_text,
    tokenize_topic,
)
from app.schemas.discovery import CandidateKind, SearchEngine, TopicCandidate


def test_normalize_collapses_case_and_spaces() -> None:
    assert normalize_topic_text("  Жесткость   Матраса ") == "жесткость матраса"


def test_jaccard_and_near_duplicate() -> None:
    assert jaccard_similarity(["a", "b"], ["a", "b", "c"]) == 2 / 3
    assert is_near_duplicate(
        "как выбрать жесткость матраса",
        ["как выбрать жесткость матраса для сна"],
        threshold=0.6,
    )
    assert not is_near_duplicate("насос", ["матрас"])
    assert tokenize_topic("") == frozenset()


def test_dedupe_texts_drops_synonyms() -> None:
    kept = dedupe_texts(
        [
            "Как выбрать матрас",
            "как выбрать   матрас",
            "Промышленный насос",
        ]
    )
    assert kept == ["Как выбрать матрас", "Промышленный насос"]
    near = dedupe_texts(
        ["жесткость матраса", "жесткость матраса купить"],
        threshold=0.6,
    )
    assert near == ["жесткость матраса"]


def test_dedupe_candidates_keeps_first() -> None:
    candidates = [
        TopicCandidate(
            text="Как выбрать матрас",
            kind=CandidateKind.ORGANIC,
            engine=SearchEngine.GOOGLE,
            query="матрас",
        ),
        TopicCandidate(
            text="как выбрать матрас",
            kind=CandidateKind.RELATED,
            engine=SearchEngine.YANDEX,
            query="матрас",
        ),
        TopicCandidate(
            text="Кокосовый матрас",
            kind=CandidateKind.PAA,
            engine=SearchEngine.GOOGLE,
            query="матрас",
        ),
    ]
    kept = dedupe_candidates(candidates)
    assert [item.text for item in kept] == ["Как выбрать матрас", "Кокосовый матрас"]
