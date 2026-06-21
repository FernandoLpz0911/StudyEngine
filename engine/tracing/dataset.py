"""P5.1 — SQLite interactions → padded DKT sequences.

Each session becomes one sequence of (concept_index, is_correct) steps.
Encoding: step t → 2M one-hot, where index = concept_idx if correct else
concept_idx + M.  Target at step t = is_correct of step t+1, gathered at
concept_index of step t+1.  Padded steps are masked out of the loss.
"""
from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

import torch
from torch.nn.utils.rnn import pad_sequence

from engine.db.connection import get_connection
from engine.tracing.concept_index import load as load_index
from engine.tracing.features import N_DKT_FEATURES, encode_features

Step = tuple[int, int, float]  # (concept_idx, is_correct, time_days)


class DKTBatch(NamedTuple):
    inputs: torch.Tensor    # (B, T, 2M + n_features) — one-hot history + time features
    targets: torch.Tensor   # (B, T)      — 0/1 next-step outcome
    t_indices: torch.Tensor # (B, T)      — concept index of next step (for gather)
    mask: torch.Tensor      # (B, T) bool — True where step is valid


def _epoch_days(iso: str | None, fallback: float) -> float:
    """ISO timestamp → days since epoch; fallback (sequence position) if unparseable."""
    if not iso:
        return fallback
    try:
        return datetime.fromisoformat(iso).timestamp() / 86400.0
    except (ValueError, TypeError):
        return fallback


def load_sequences(
    concept_index: dict[str, int] | None = None,
) -> list[list[Step]]:
    """Return per-session (concept_idx, is_correct, time_days) for answered items."""
    if concept_index is None:
        concept_index = load_index()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT session_id, concept_id, is_correct, shown_at
            FROM interaction
            WHERE is_correct IS NOT NULL
            ORDER BY session_id, id
            """
        ).fetchall()

    sessions: dict[int, list[Step]] = {}
    for row in rows:
        idx = concept_index.get(row["concept_id"])
        if idx is None:
            continue
        seq = sessions.setdefault(row["session_id"], [])
        t = _epoch_days(row["shown_at"], fallback=float(len(seq)))
        seq.append((idx, int(row["is_correct"]), t))

    # Only sessions with at least 2 steps (need input + one target)
    return [seq for seq in sessions.values() if len(seq) >= 2]


def encode_sequence(
    seq: list[Step],
    n_concepts: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Encode one session sequence into tensors (before padding).

    Returns:
        x      — (T-1, 2M + n_features) float one-hot input + time features
        target — (T-1,)    float 0/1 next-step outcome
        t_idx  — (T-1,)    long  next-step concept index (for loss gather)
    """
    M = n_concepts
    T = len(seq)
    x = torch.zeros(T - 1, 2 * M + N_DKT_FEATURES)
    target = torch.zeros(T - 1)
    t_idx = torch.zeros(T - 1, dtype=torch.long)

    features = encode_features([(concept_idx, t) for concept_idx, _, t in seq])

    for i in range(T - 1):
        concept_idx, correct, _ = seq[i]
        hot = concept_idx if correct else concept_idx + M
        x[i, hot] = 1.0
        for f, value in enumerate(features[i]):
            x[i, 2 * M + f] = value
        next_idx, next_correct, _ = seq[i + 1]
        target[i] = float(next_correct)
        t_idx[i] = next_idx

    return x, target, t_idx


def encode_history(history: list[Step], n_concepts: int) -> torch.Tensor:
    """Encode a timed (concept_idx, is_correct, time_days) history into model input.

    Returns a (T, 2M + n_features) tensor for live inference — one row per past
    step, no targets. Time features use the same scheme as training.
    """
    M = n_concepts
    x = torch.zeros(len(history), 2 * M + N_DKT_FEATURES)
    features = encode_features([(concept_idx, t) for concept_idx, _, t in history])
    for i, (concept_idx, correct, _) in enumerate(history):
        hot = concept_idx if correct else concept_idx + M
        x[i, hot] = 1.0
        for f, value in enumerate(features[i]):
            x[i, 2 * M + f] = value
    return x


def build_batches(
    sequences: list[list[tuple[int, int]]],
    n_concepts: int,
    batch_size: int = 32,
    shuffle: bool = True,
) -> list[DKTBatch]:
    """Encode sequences and group into padded batches."""
    encoded = [encode_sequence(s, n_concepts) for s in sequences]

    if shuffle:
        import random
        random.shuffle(encoded)

    batches: list[DKTBatch] = []
    for i in range(0, len(encoded), batch_size):
        chunk = encoded[i : i + batch_size]
        xs, targets, t_idxs = zip(*chunk, strict=True)

        # Lengths for masking
        lengths = torch.tensor([x.size(0) for x in xs])

        # Pad to (B, T, 2M)
        x_pad = pad_sequence(xs, batch_first=True)
        t_pad = pad_sequence(targets, batch_first=True, padding_value=0.0)
        ti_pad = pad_sequence(t_idxs, batch_first=True, padding_value=0)

        # Boolean mask: True where step is valid
        T_max = x_pad.size(1)
        mask = torch.arange(T_max).unsqueeze(0) < lengths.unsqueeze(1)

        batches.append(DKTBatch(x_pad, t_pad, ti_pad, mask))

    return batches


def train_val_split(
    sequences: list[list[tuple[int, int]]],
    val_frac: float = 0.2,
    seed: int = 42,
) -> tuple[list, list]:
    """Split by session (not by interaction) to prevent leakage."""
    import random
    rng = random.Random(seed)
    seqs = list(sequences)
    rng.shuffle(seqs)
    n_val = max(1, int(len(seqs) * val_frac))
    return seqs[n_val:], seqs[:n_val]
