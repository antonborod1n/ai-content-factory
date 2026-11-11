"""Deterministic quality helpers (no AI, no SQL)."""


def clamp_score(value: int) -> int:
    """Keep a detector score in 0..100."""
    return max(0, min(100, int(value)))


def detector_verdict(
    ai_likelihood: int,
    uniqueness: int,
    *,
    ai_review_threshold: int = 70,
    uniqueness_floor: int = 50,
) -> str:
    """``pass`` when scores look safe; ``review`` before CMS otherwise."""
    if ai_likelihood >= ai_review_threshold or uniqueness < uniqueness_floor:
        return "review"
    return "pass"
