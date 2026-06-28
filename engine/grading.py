"""Objective grading: check an answer, then derive the FSRS grade from data only.

No self-rating is involved anywhere. Correctness comes from comparing the answer
to a computed key; the four-level FSRS grade is a pure function of correctness and
response time.
"""
from __future__ import annotations

from engine.config import GRADE_FAST_MS, GRADE_SLOW_MS


def grade_answer(user_answer: str, correct_answer: str, tolerance: float = 1e-5) -> bool:
    """True when the user's answer matches: exact string, or numeric within tolerance."""
    if user_answer.strip() == correct_answer.strip():
        return True
    try:
        return abs(float(user_answer) - float(correct_answer)) <= tolerance
    except ValueError:
        return False


def derive_grade(
    is_correct: bool,
    elapsed_ms: int,
    fast_ms: int = GRADE_FAST_MS,
    slow_ms: int = GRADE_SLOW_MS,
) -> int:
    """Map objective signals to an FSRS rating (1 Again, 2 Hard, 3 Good, 4 Easy).

    Wrong → Again. Right and quick → Easy; right and slow → Hard; otherwise Good.
    Response time is measured, never reported by the learner, so grading stays
    purely data-based.
    """
    if not is_correct:
        return 1
    if elapsed_ms > 0 and elapsed_ms <= fast_ms:
        return 4
    if elapsed_ms >= slow_ms:
        return 2
    return 3
