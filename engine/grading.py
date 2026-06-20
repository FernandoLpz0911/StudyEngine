"""Answer grading for generator-mode problems (exact string or numeric tolerance)."""
from __future__ import annotations


def grade_answer(user_answer: str, correct_answer: str, tolerance: float = 1e-3) -> bool:
    """True when the user's answer matches: exact string, or numeric within tolerance."""
    if user_answer.strip() == correct_answer.strip():
        return True
    try:
        return abs(float(user_answer) - float(correct_answer)) <= tolerance
    except ValueError:
        return False
