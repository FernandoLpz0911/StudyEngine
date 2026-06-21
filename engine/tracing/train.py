"""DKT training loop: masked BCE loss, gradient clipping, AUC evaluation, checkpoint."""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score

from engine.tracing.concept_index import load as load_index
from engine.tracing.dataset import DKTBatch, build_batches, load_sequences, train_val_split
from engine.tracing.features import N_DKT_FEATURES
from engine.tracing.model import DKT

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

_BEST_CHECKPOINT = CHECKPOINT_DIR / "dkt_best.pt"
_TRAIN_LOG = CHECKPOINT_DIR / "train_log.jsonl"


def _bce_loss(
    preds: torch.Tensor,   # (B, T, M)
    batch: DKTBatch,
) -> torch.Tensor:
    """Masked BCE: only valid steps contribute, gathered at next concept."""
    # Gather predicted P(correct) at next-step concept index
    # t_indices: (B, T) long
    concept_idx = batch.t_indices.unsqueeze(-1)     # (B, T, 1) — for gather
    p_correct = preds.gather(2, concept_idx).squeeze(-1)  # (B, T)

    loss = nn.functional.binary_cross_entropy(
        p_correct[batch.mask], batch.targets[batch.mask]
    )
    return loss


def _eval_auc(
    model: DKT,
    batches: list[DKTBatch],
    device: torch.device,
) -> float:
    """Compute AUC over a set of batches."""
    model.eval()
    all_preds: list[float] = []
    all_targets: list[float] = []

    with torch.no_grad():
        for batch in batches:
            x = batch.inputs.to(device)
            preds = model(x)
            concept_idx = batch.t_indices.unsqueeze(-1).to(device)
            p_correct = preds.gather(2, concept_idx).squeeze(-1).cpu()
            mask = batch.mask

            all_preds.extend(p_correct[mask].tolist())
            all_targets.extend(batch.targets[mask].tolist())

    if len(set(all_targets)) < 2:
        return float("nan")
    return float(roc_auc_score(all_targets, all_preds))


def train(
    n_epochs: int = 50,
    hidden: int = 128,
    layers: int = 1,
    dropout: float = 0.2,
    lr: float = 1e-3,
    grad_clip: float = 5.0,
    batch_size: int = 32,
    val_frac: float = 0.2,
    seed: int = 42,
    device_str: str = "auto",
) -> dict:
    """Train DKT. Returns {val_auc, n_interactions, epochs_run, checkpoint_path}."""
    torch.manual_seed(seed)

    if device_str == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str)

    concept_index = load_index()
    M = len(concept_index)

    sequences = load_sequences(concept_index)
    n_interactions = sum(len(s) for s in sequences)

    if len(sequences) < 2:
        return {
            "val_auc": float("nan"),
            "n_interactions": n_interactions,
            "epochs_run": 0,
            "checkpoint_path": None,
            "error": "Not enough sequences to train (need ≥ 2 sessions with ≥ 2 steps each).",
        }

    train_seqs, val_seqs = train_val_split(sequences, val_frac=val_frac, seed=seed)

    train_batches = build_batches(train_seqs, M, batch_size, shuffle=True)
    val_batches = build_batches(val_seqs, M, batch_size, shuffle=False)

    model = DKT(
        M, hidden=hidden, layers=layers, dropout=dropout, n_features=N_DKT_FEATURES
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best_auc = -1.0
    best_epoch = 0
    log_rows: list[dict] = []

    for epoch in range(1, n_epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_steps = 0

        for batch in train_batches:
            x = batch.inputs.to(device)
            preds = model(x)
            loss = _bce_loss(preds, DKTBatch(
                preds,
                batch.targets.to(device),
                batch.t_indices.to(device),
                batch.mask.to(device),
            ))
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            epoch_loss += loss.item() * batch.mask.sum().item()
            n_steps += batch.mask.sum().item()

        avg_loss = epoch_loss / max(n_steps, 1)
        val_auc = _eval_auc(model, val_batches, device)

        row = {"epoch": epoch, "train_loss": avg_loss, "val_auc": val_auc}
        log_rows.append(row)

        if not (val_auc != val_auc) and val_auc > best_auc:  # nan-safe
            best_auc = val_auc
            best_epoch = epoch
            torch.save(
                {
                    "epoch": epoch,
                    "val_auc": val_auc,
                    "n_concepts": M,
                    "hidden": hidden,
                    "layers": layers,
                    "dropout": dropout,
                    "n_features": N_DKT_FEATURES,
                    "model_state": model.state_dict(),
                },
                _BEST_CHECKPOINT,
            )

    # Persist training log (append)
    with _TRAIN_LOG.open("a") as f:
        for row in log_rows:
            f.write(json.dumps(row) + "\n")

    return {
        "val_auc": best_auc,
        "best_epoch": best_epoch,
        "n_interactions": n_interactions,
        "epochs_run": n_epochs,
        "checkpoint_path": str(_BEST_CHECKPOINT) if best_auc > -1 else None,
    }
