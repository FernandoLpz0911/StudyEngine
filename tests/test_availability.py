"""availability: the two shared concept-selection predicates (issue #3)."""
from datetime import UTC, datetime, timedelta

from engine.scheduler.availability import introduced, is_due

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


class TestIntroduced:
    def test_seen_once_is_introduced(self):
        assert introduced(1, suspended=False) is True

    def test_never_seen_is_not(self):
        assert introduced(0, suspended=False) is False

    def test_suspended_never_seen_still_counts(self):
        # "I know this" must not lock everything behind it forever.
        assert introduced(0, suspended=True) is True


class TestIsDue:
    def test_reached_and_visible_is_due(self):
        assert is_due(2, NOW - timedelta(hours=1), NOW, suppressed=False) is True

    def test_future_due_is_not(self):
        assert is_due(2, NOW + timedelta(hours=1), NOW, suppressed=False) is False

    def test_never_reviewed_is_not(self):
        assert is_due(0, NOW - timedelta(days=1), NOW, suppressed=False) is False

    def test_suppressed_is_never_due(self):
        # A buried/suspended card must not nag even when its time has come.
        assert is_due(2, NOW - timedelta(hours=1), NOW, suppressed=True) is False

    def test_no_due_time_is_not(self):
        assert is_due(2, None, NOW, suppressed=False) is False

    def test_naive_due_is_read_as_utc(self):
        naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
        assert is_due(2, naive, NOW, suppressed=False) is True
