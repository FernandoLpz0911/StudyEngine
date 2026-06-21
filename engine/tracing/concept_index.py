"""Global concept_id -> integer index spanning every subject.

The DKT model has one input/output slot per concept across the whole app, so a
single learner's interleaved history trains one model over all domains. The index
is derived deterministically from the sorted concept ids in the database (no file
to drift); a trained checkpoint records n_concepts and is invalidated only if the
concept set changes.
"""
from __future__ import annotations


def load() -> dict[str, int]:
    """Return {concept_id: index} for all concepts, ordered by id (stable)."""
    from engine.db.dao import all_concept_ids

    return {cid: i for i, cid in enumerate(all_concept_ids())}
