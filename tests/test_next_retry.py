"""service.next_retry: the shared retry-queue popper (issue #3)."""
import engine.subjects  # noqa: F401
from engine import service
from engine.db import dao


def _cid(subject: str = "diffeq") -> str:
    return dao.get_concepts(subject)[0].id


class TestNextRetry:
    def test_empty_queue_is_none(self, db):
        queue: list[tuple[str, int]] = []
        assert service.next_retry(queue, index=5, force=False) is None

    def test_gate_holds_until_the_spacing_index_or_force(self, db):
        cid = _cid()
        queue = [(cid, 10)]
        assert service.next_retry(queue, index=3, force=False) is None  # too soon
        assert queue == [(cid, 10)]  # left queued
        picked = service.next_retry(queue, index=3, force=True)  # force overrides
        assert picked is not None and picked.id == cid
        assert queue == []  # popped

    def test_ready_item_pops_at_or_past_its_index(self, db):
        cid = _cid()
        queue = [(cid, 10)]
        picked = service.next_retry(queue, index=10, force=False)
        assert picked is not None and picked.id == cid
        assert queue == []

    def test_suppressed_concept_is_skipped_and_left_queued(self, db):
        cid = _cid()
        dao.bury_concept(cid)
        queue = [(cid, 0)]
        assert service.next_retry(queue, index=99, force=True) is None
        assert queue == [(cid, 0)]  # still owed once it's unhidden
