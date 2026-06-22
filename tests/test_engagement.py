"""Variable rewards + mnemonic (IKEA effect) storage."""
from engine.db import dao
from engine.engagement import PRAISE, reward_message


class _FakeRng:
    """Minimal rng stub: fixed random() value, deterministic choice()."""

    def __init__(self, value: float):
        self._value = value

    def random(self) -> float:
        return self._value

    def choice(self, seq):
        return seq[0]


class TestRewardMessage:
    def test_wrong_answer_is_silent(self):
        assert reward_message(False, 3, _FakeRng(0.0)) == ""

    def test_streak_milestone(self):
        assert "5" in reward_message(True, 5, _FakeRng(0.99))

    def test_occasional_praise_when_lucky(self):
        assert reward_message(True, 1, _FakeRng(0.1)) == PRAISE[0]

    def test_usually_silent(self):
        assert reward_message(True, 1, _FakeRng(0.9)) == ""


class TestMnemonic:
    def test_absent_returns_none(self, db):
        assert dao.get_mnemonic("diffeq.separable") is None

    def test_save_and_resurface(self, db):
        dao.save_mnemonic("diffeq.separable", "separate, integrate, exp")
        assert dao.get_mnemonic("diffeq.separable") == "separate, integrate, exp"

    def test_overwrite(self, db):
        dao.save_mnemonic("diffeq.separable", "first")
        dao.save_mnemonic("diffeq.separable", "second")
        assert dao.get_mnemonic("diffeq.separable") == "second"
