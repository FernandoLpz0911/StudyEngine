"""Synthetic interaction data for DKT cold-start pretraining.

Simulates a learner who starts weak and improves over time, across every concept
in the database. Used only by pretraining (into a throwaway DB) — never the real
study log.
"""
from __future__ import annotations

import random

from engine.db import dao


def seed_synthetic(
    n_sessions: int = 40,
    steps_per_session: int = 30,
    base_accuracy: float = 0.4,
    improvement_rate: float = 0.015,
    rng_seed: int = 42,
) -> int:
    """Insert synthetic answered interactions across all concepts. Returns the count."""
    rng = random.Random(rng_seed)
    ids = dao.all_concept_ids()
    skill = {cid: base_accuracy for cid in ids}

    total = 0
    for _ in range(n_sessions):
        session_id = dao.create_session("synthetic")
        for _ in range(steps_per_session):
            cid = rng.choice(ids)
            correct = rng.random() < min(0.95, skill[cid])
            item = dao.log_shown(session_id, cid, cid.split(".")[0], "synthetic",
                                 correct_answer="0")
            dao.log_answered(item, "0", correct, 4 if correct else 1, 1000)
            skill[cid] = min(0.95, skill[cid] + improvement_rate)
            total += 1
    return total
