"""Personalized FSRS parameters fitted to the learner's own review log.

The default FSRS weights are population averages; after enough graded reviews the
optimizer (py-fsrs, gradient descent over the retrievability loss) re-fits all 21
weights to this learner, so intervals match how *they* actually forget. Fitted
parameters are stored in the `setting` table and picked up by the scheduler on the
next review — nothing else changes, grading stays objective.
"""
from __future__ import annotations

import json
from datetime import datetime

from fsrs import Rating, ReviewLog

from engine.config import FSRS_MIN_REVIEWS
from engine.db import dao

PARAMS_KEY = "fsrs_params_json"


def stored_parameters() -> tuple[float, ...] | None:
    """Previously fitted weights, or None to use the py-fsrs defaults."""
    raw = dao.get_setting(PARAMS_KEY)
    if not raw:
        return None
    try:
        params = tuple(float(x) for x in json.loads(raw))
    except (ValueError, TypeError):
        return None
    return params or None


def review_logs() -> list[ReviewLog]:
    """The graded interaction history as py-fsrs ReviewLogs, oldest first.

    py-fsrs wants integer card ids; concept ids are strings, so each gets a
    stable index. The optimizer only uses the id to group a card's sequence.
    """
    card_ids = {cid: i for i, cid in enumerate(dao.all_concept_ids())}
    logs: list[ReviewLog] = []
    for concept_id, grade, answered_at, elapsed_ms in dao.graded_reviews():
        if concept_id not in card_ids:
            continue
        logs.append(
            ReviewLog(
                card_id=card_ids[concept_id],
                rating=Rating(grade),
                review_datetime=datetime.fromisoformat(answered_at),
                review_duration=elapsed_ms or None,
            )
        )
    return logs


def fit(verbose: bool = False) -> dict:
    """Fit personal FSRS weights when the log is big enough; persist and report.

    Returns {"fitted": bool, "reviews": int, "gate": int, "parameters": [...] | None}.
    """
    logs = review_logs()
    result = {
        "fitted": False,
        "reviews": len(logs),
        "gate": FSRS_MIN_REVIEWS,
        "parameters": None,
    }
    if len(logs) < FSRS_MIN_REVIEWS:
        return result
    from fsrs.optimizer import Optimizer
    params = Optimizer(logs).compute_optimal_parameters(verbose=verbose)
    dao.set_setting(PARAMS_KEY, json.dumps(params))
    result["fitted"] = True
    result["parameters"] = params
    return result
