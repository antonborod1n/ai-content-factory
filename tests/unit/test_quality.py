"""Deterministic detector verdict helpers."""

from app.core.quality import clamp_score, detector_verdict


def test_clamp_score() -> None:
    assert clamp_score(-3) == 0
    assert clamp_score(150) == 100
    assert clamp_score(32) == 32


def test_detector_verdict_pass() -> None:
    assert detector_verdict(32, 78) == "pass"


def test_detector_verdict_review_on_ai_score() -> None:
    assert detector_verdict(70, 78) == "review"
    assert detector_verdict(90, 90) == "review"


def test_detector_verdict_review_on_uniqueness() -> None:
    assert detector_verdict(32, 49) == "review"
