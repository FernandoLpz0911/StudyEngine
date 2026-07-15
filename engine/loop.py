"""The StudyLoop: one owner for the interleaved study loop and its Turn state.

The loop that selects, serves, and settles items lived twice — once in the HTTP
API (one request at a time) and once in the CLI (a straight for-loop). Both
re-derived the same interleaving, warmup/stall/cooldown pacing, DKT cadence,
retry-drain, and settlement fold. `StudyLoop` owns all of it (see ADR-0002 and
`CONTEXT.md` for **StudyLoop** and **Turn**): the CLI drives one Turn per loop
iteration; the web API drives `next()` on `GET .../next` and `settle()` on
`POST /answer`, with the `item_id -> item` map living here so the two halves
resolve across the request round-trip.

Session-local state (index, recent, retry queue, combo streak, best, XP, last
subject, record tracker, DKT predictions) lives here; the log-wide write path
stays in `service.settle_answer`. Front ends keep only transport and rendering.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine import service
from engine.config import GLOBAL_COOLDOWN, GLOBAL_WARMUP, RETRY_GAP
from engine.db import dao
from engine.engagement import (
    RecordTracker,
    combo_break_message,
    combo_label,
    reward_message,
)
from engine.scheduler import policy
from engine.service import AnswerOutcome, StudyItem
from engine.subjects import SUBJECTS


@dataclass
class Turn:
    """One served item, awaiting an answer. `mode` is the selection mode that
    produced it (``None`` for a retry) — front ends use it for framing only."""
    item_id: int
    item: StudyItem
    mode: str | None = None


@dataclass
class Done:
    """The loop is over; the DB session is already closed. Carries the summary."""
    summary: dict


class StudyLoop:
    """Live driver for one study session. Rebuildable from the DB after a restart."""

    def __init__(self, db_id: int, scope: str, n: int | None) -> None:
        self.db_id = db_id
        self.scope = scope  # "global" or a subject key
        self.n = n  # item budget; None = open-ended (the web API), ends on nothing-due
        self.index = 0
        self.recent: list[bool] = []
        self.retry_queue: list[tuple[str, int]] = []
        self.items: dict[int, StudyItem] = {}
        self.streak = 0
        self.best = 0
        self.xp = 0
        self.last_subject: str | None = None
        self.touched: set[str] = set()
        self.tracker: RecordTracker | None = None
        self.dkt_active = False
        self.p_correct: dict | None = None
        self._mode: str | None = None  # selection mode of the last global pick
        self._rng = np.random.default_rng()

    @classmethod
    def start(cls, scope: str, n: int | None = None) -> StudyLoop:
        """Open a fresh session and its live state."""
        loop = cls(dao.create_session(scope), scope, n)
        loop._init_live_state()
        return loop

    @classmethod
    def rebuild(cls, session_id: int) -> StudyLoop | None:
        """Restore a live session from the DB after a server restart.

        Replays the logged results through the *same* session-local fold used
        live (`_fold_result`), so the rebuilt streak/best/XP can never diverge
        from the incremental path. The served-but-unanswered item is the only
        thing lost. Rebuilt sessions are open-ended (only the web API rebuilds).
        """
        row = dao.get_session(session_id)
        if row is None or row["ended_at"]:
            return None  # never resurrect a finished session — the client starts fresh
        loop = cls(session_id, row["subject"], n=None)
        for r in dao.session_results(session_id):
            loop._fold_result(
                bool(r["is_correct"]), r["grade"] or 0, r["exam_weight"], r["subject"]
            )
        loop.index = dao.count_shown(session_id)
        loop._init_live_state()
        return loop

    def _init_live_state(self) -> None:
        """State every live session needs, fresh or rebuilt.

        Missed concepts from earlier sessions are still owed a re-test — front-load
        them so an abandoned tab never loses the errorful retry. A single-subject
        session only front-loads its own subject's debts. Record baselines snapshot
        once here and advance in Python per answer, instead of re-scanning the log.
        """
        if self.scope == "global":
            pending = dao.pending_retries()
        else:
            subject_ids = {c.id for c in dao.get_concepts(self.scope)}
            pending = [cid for cid in dao.pending_retries() if cid in subject_ids]
        self.retry_queue = [(cid, 0) for cid in pending]
        self.tracker = RecordTracker.snapshot()
        from engine.tracing import infer
        self.dkt_active = infer.dkt_is_active()
        if self.dkt_active:
            self.p_correct = infer.predict(dao.get_interaction_history_timed())

    def next(self) -> Turn | Done:
        """Advance the loop by one Turn: select, serve, log. Ends when the budget
        is spent or nothing is available (draining pending re-tests first)."""
        if self.n is not None and self.index >= self.n:
            return self._finish()

        concept = service.next_retry(self.retry_queue, self.index, force=False)
        if concept is not None:
            return self._serve(concept, "retry", mode=None)

        if self.scope == "global":
            selection = self._select_global()
        else:
            selection = policy.select_next(self.scope)

        if selection is None:
            concept = service.next_retry(self.retry_queue, self.index, force=True)
            if concept is None:
                return self._finish()  # drain pending re-tests before ending
            return self._serve(concept, "retry", mode=None)
        return self._serve(selection.concept, selection.reason, mode=self._mode)

    def _select_global(self) -> policy.Selection | None:
        """Weakest-first across subjects, with warmup/cooldown/stall confidence
        builders and a DKT re-prediction every 5 items."""
        if self.dkt_active and self.index > 0 and self.index % 5 == 0:
            from engine.tracing import infer
            self.p_correct = infer.predict(dao.get_interaction_history_timed())
        warm = self.index < GLOBAL_WARMUP
        cool = self.n is not None and self.index >= self.n - GLOBAL_COOLDOWN
        stalling = self.recent[-2:] == [False, False]
        self._mode = "confidence" if (warm or cool or stalling) else "weak"
        return policy.select_global(
            list(SUBJECTS), avoid_subject=self.last_subject,
            mode=self._mode, p_correct=self.p_correct,
        )

    def _serve(self, concept, reason: str, mode: str | None) -> Turn:
        item = service.build_item(concept, self._rng, reason)
        item_id = service.log_item_shown(self.db_id, item)
        self.items[item_id] = item
        self.index += 1
        return Turn(item_id, item, mode)

    def settle(self, item_id: int, raw_answer: str, elapsed_ms: int) -> AnswerOutcome:
        """Grade and settle one answer, folding the session-local delta.

        The log-wide Settle (log, FSRS, quests, retry debt, record detection) lives
        in `service.settle_answer`; here we add the session-local framing — the
        in-session retry re-append, recent list, combo streak, best, and XP.
        """
        item = self.items[item_id]
        res = service.settle_answer(item_id, item, raw_answer, elapsed_ms, self.tracker)

        concept = dao.get_concept(item.concept_id)
        exam_weight = concept.exam_weight if concept else 1
        prev_streak = self.streak
        if not res.correct and item.reason != "retry":
            self.retry_queue.append((item.concept_id, self.index + RETRY_GAP))
        self._fold_result(res.correct, res.grade, exam_weight, item.subject)
        xp = res.grade * exam_weight if res.correct else 0
        combo_break = "" if res.correct else combo_break_message(prev_streak, self.best)
        return AnswerOutcome(
            correct=res.correct,
            grade=res.grade,
            records=res.records,
            reward=reward_message(res.correct, self.streak, self._rng),
            combo=combo_label(self.streak),
            combo_break=combo_break,
            streak=self.streak,
            best_streak=self.best,
            xp=xp,
            next_review_days=res.next_review_days,
            why_wrong=res.why_wrong,
            ask_mnemonic=res.ask_mnemonic,
        )

    def _fold_result(
        self, correct: bool, grade: int, exam_weight: int, subject: str
    ) -> None:
        """The session-local reduction of one result — the single fold shared by
        the live `settle` path and the `rebuild` replay."""
        self.recent.append(correct)
        self.streak = self.streak + 1 if correct else 0
        self.best = max(self.best, self.streak)
        if correct:
            self.xp += grade * exam_weight
        self.last_subject = subject
        self.touched.add(subject)

    def _finish(self) -> Done:
        dao.close_session(self.db_id)
        return Done(self.summary())

    def summary(self) -> dict:
        answered = len(self.recent)
        correct = sum(self.recent)
        return {
            "answered": answered,
            "correct": correct,
            "accuracy": round(correct / answered, 3) if answered else 0.0,
            "best_streak": self.best,
            "xp_gained": self.xp,
            "subjects": len(self.touched),
        }
