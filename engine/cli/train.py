"""Train the global DKT model on your whole interaction history.

    python -m engine.cli.train [--epochs 50] [--hidden 64]

One model over all subjects: it learns from your interleaved cross-domain log and,
once it clears the activation gate, drives weak-concept selection in global
sessions. Until then FSRS handles scheduling — so training early is harmless.
"""
from __future__ import annotations

import argparse
import math

import engine.subjects  # noqa: F401  (ensures all concepts exist for the index)
from engine.db.seed import load_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the global DKT model.")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--hidden", type=int, default=64)
    args = parser.parse_args()

    load_all()
    from engine.tracing import infer
    from engine.tracing.train import train

    result = train(n_epochs=args.epochs, hidden=args.hidden)
    if result.get("error"):
        print(f"Not enough data yet: {result['error']}")
    else:
        auc = result.get("val_auc")
        auc_str = "n/a" if auc is None or math.isnan(auc) else f"{auc:.3f}"
        print(
            f"Trained on {result['n_interactions']} interactions, "
            f"{result['epochs_run']} epochs. Best val-AUC = {auc_str}."
        )
    print(f"DKT active: {infer.dkt_is_active()}")


if __name__ == "__main__":
    main()
