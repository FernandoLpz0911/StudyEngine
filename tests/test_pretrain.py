"""DKT synthetic pretraining + the pretrained-bypasses-gate behaviour."""
import pytest

pytest.importorskip("torch")  # DKT is an optional extra (requirements-dkt.txt)

import torch

import engine.subjects  # noqa: F401  (registers concepts)
import engine.tracing.train as train_mod
from engine.db import dao
from engine.tracing import infer as infer_mod
from engine.tracing.concept_index import load as load_index
from engine.tracing.features import N_DKT_FEATURES
from engine.tracing.model import DKT


def _write_checkpoint(path, *, pretrained: bool, val_auc: float) -> None:
    m = len(load_index())
    torch.save(
        {
            "epoch": -1, "val_auc": val_auc, "n_concepts": m,
            "hidden": 8, "layers": 1, "dropout": 0.2,
            "n_features": N_DKT_FEATURES, "pretrained": pretrained,
            "model_state": DKT(m, hidden=8, n_features=N_DKT_FEATURES).state_dict(),
        },
        path,
    )


class TestSynthetic:
    def test_seed_synthetic_inserts(self, db):
        from engine.tracing.synthetic import seed_synthetic

        n = seed_synthetic(n_sessions=5, steps_per_session=10)
        assert n == 50
        assert dao.count_answered_interactions() == 50


class TestActivationGate:
    def test_pretrained_bypasses_interaction_gate(self, db, tmp_path, monkeypatch):
        ckpt = tmp_path / "dkt.pt"
        _write_checkpoint(ckpt, pretrained=True, val_auc=0.99)
        monkeypatch.setattr(infer_mod, "_BEST_CHECKPOINT", ckpt)
        monkeypatch.setattr("engine.config.DKT_MIN_AUC", 0.5)
        assert dao.count_answered_interactions() == 0
        assert infer_mod.dkt_is_active() is True

    def test_non_pretrained_respects_gate(self, db, tmp_path, monkeypatch):
        ckpt = tmp_path / "dkt.pt"
        _write_checkpoint(ckpt, pretrained=False, val_auc=0.99)
        monkeypatch.setattr(infer_mod, "_BEST_CHECKPOINT", ckpt)
        monkeypatch.setattr("engine.config.DKT_MIN_AUC", 0.5)
        assert infer_mod.dkt_is_active() is False  # 0 interactions, not pretrained


class TestPretrainRun:
    def test_pretrain_writes_pretrained_checkpoint(self, db, tmp_path, monkeypatch):
        from engine.tracing import pretrain as pretrain_mod

        ckpt = tmp_path / "live.pt"
        monkeypatch.setattr(train_mod, "CHECKPOINT_DIR", tmp_path)
        monkeypatch.setattr(train_mod, "_BEST_CHECKPOINT", ckpt)
        monkeypatch.setattr(train_mod, "_TRAIN_LOG", tmp_path / "log.jsonl")

        result = pretrain_mod.pretrain(
            n_sessions=8, steps_per_session=15, n_epochs=2, hidden=8
        )
        assert ckpt.exists()
        assert result.get("pretrained") is True
        blob = torch.load(ckpt, map_location="cpu", weights_only=True)
        assert blob["pretrained"] is True
        assert blob["n_concepts"] == len(load_index())
