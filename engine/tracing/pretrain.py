"""Pretrain the global DKT on synthetic data so it works from day one.

A single learner cannot produce the hundreds of interactions DKT needs before it
beats FSRS — exactly the early window that matters. Pretraining fits the model to
a plausible synthetic learning curve in a throwaway database, then writes the
weights to the live checkpoint flagged ``pretrained``; the activation gate lets a
pretrained checkpoint bypass the interaction-count requirement. Real training
later overwrites it with a data-fitted model.

    python -m engine.cli.train --pretrain
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import torch

import engine.tracing.train as train_mod
from engine.db.seed import load_all
from engine.tracing.synthetic import seed_synthetic


def pretrain(
    n_sessions: int = 40,
    steps_per_session: int = 30,
    n_epochs: int = 30,
    hidden: int = 64,
    seed: int = 0,
) -> dict:
    """Train on synthetic data and save it as the live pretrained checkpoint."""
    saved_paths = (
        train_mod.CHECKPOINT_DIR,
        train_mod._BEST_CHECKPOINT,
        train_mod._TRAIN_LOG,
    )
    live_checkpoint = train_mod._BEST_CHECKPOINT
    previous_db = os.environ.get("DB_PATH")

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DB_PATH"] = str(Path(tmp) / "pretrain.db")
        ckpt_dir = Path(tmp) / "checkpoints"
        ckpt_dir.mkdir()
        try:
            load_all()
            n = seed_synthetic(n_sessions, steps_per_session, rng_seed=seed)
            train_mod.CHECKPOINT_DIR = ckpt_dir
            train_mod._BEST_CHECKPOINT = ckpt_dir / "dkt.pt"
            train_mod._TRAIN_LOG = ckpt_dir / "log.jsonl"
            result = train_mod.train(n_epochs=n_epochs, hidden=hidden)
            blob = (
                torch.load(train_mod._BEST_CHECKPOINT, map_location="cpu",
                           weights_only=True)
                if train_mod._BEST_CHECKPOINT.exists()
                else None
            )
        finally:
            train_mod.CHECKPOINT_DIR, train_mod._BEST_CHECKPOINT, train_mod._TRAIN_LOG = (
                saved_paths
            )
            if previous_db is None:
                os.environ.pop("DB_PATH", None)
            else:
                os.environ["DB_PATH"] = previous_db

    if blob is None:
        return {"error": result.get("error", "no checkpoint produced")}

    blob["pretrained"] = True
    live_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(blob, live_checkpoint)
    return {
        "val_auc": blob.get("val_auc"),
        "n_interactions": n,
        "checkpoint_path": str(live_checkpoint),
        "pretrained": True,
    }
