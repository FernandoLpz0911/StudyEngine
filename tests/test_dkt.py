"""Global DKT: dims, train→checkpoint→predict, and prediction-driven selection."""
import random
from datetime import UTC, datetime, timedelta

import engine.subjects  # noqa: F401  (registers concepts)
from engine.db import dao
from engine.scheduler import policy, store
from engine.tracing import infer as infer_mod
from engine.tracing import train as train_mod
from engine.tracing.concept_index import load as load_index
from engine.tracing.dataset import encode_history
from engine.tracing.features import N_DKT_FEATURES
from engine.tracing.model import DKT


def _simulate(sessions: int = 6, steps: int = 20, seed: int = 0) -> None:
    rng = random.Random(seed)
    ids = dao.all_concept_ids()[:12]
    for _ in range(sessions):
        sid = dao.create_session("global")
        for _ in range(steps):
            cid = rng.choice(ids)
            correct = rng.random() < 0.6
            item = dao.log_shown(sid, cid, cid.split(".")[0], "k", correct_answer="1.0")
            dao.log_answered(item, "1.0", correct, 4 if correct else 1, 2000)


def _overdue(concept_id: str) -> None:
    past = datetime.now(UTC) - timedelta(days=2)
    cs = store.get_or_create(concept_id)
    cs.reps, cs.stability, cs.state = 2, 8.0, "review"
    cs.last_review = cs.due = past
    store.save(cs)


class TestModelDims:
    def test_forward_shape_matches_global_concepts(self, db):
        m = len(load_index())
        model = DKT(m, hidden=8, n_features=N_DKT_FEATURES)
        x = encode_history([(0, 1, 0.0), (1, 0, 1.0)], m).unsqueeze(0)
        assert model(x).shape == (1, 2, m)


class TestTrainInfer:
    def test_train_writes_checkpoint_and_predicts(self, db, tmp_path, monkeypatch):
        ckpt = tmp_path / "dkt.pt"
        monkeypatch.setattr(train_mod, "CHECKPOINT_DIR", tmp_path)
        monkeypatch.setattr(train_mod, "_BEST_CHECKPOINT", ckpt)
        monkeypatch.setattr(train_mod, "_TRAIN_LOG", tmp_path / "log.jsonl")
        monkeypatch.setattr(infer_mod, "_BEST_CHECKPOINT", ckpt)

        _simulate()
        result = train_mod.train(n_epochs=2, hidden=8)
        assert result["n_interactions"] == 120
        assert ckpt.exists()

        preds = infer_mod.predict(dao.get_interaction_history_timed())
        assert preds is not None
        assert len(preds) == len(load_index())
        assert all(0.0 <= v <= 1.0 for v in preds.values())

    def test_too_few_sequences_errors(self, db):
        result = train_mod.train(n_epochs=2)
        assert result["epochs_run"] == 0
        assert "error" in result


class TestPredictionDrivenSelection:
    def test_p_correct_overrides_mastery_ranking(self, db):
        _overdue("diffeq.separable")
        _overdue("econ.incentives")
        p = {"diffeq.separable": 0.1, "econ.incentives": 0.9}
        weak = policy.select_global(["diffeq", "econ"], mode="weak", p_correct=p)
        assert weak.concept.id == "diffeq.separable"
        conf = policy.select_global(["diffeq", "econ"], mode="confidence", p_correct=p)
        assert conf.concept.id == "econ.incentives"
