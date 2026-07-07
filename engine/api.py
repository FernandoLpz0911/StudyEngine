"""HTTP API over the study engine — the backend the web frontend talks to.

Thin layer: every endpoint calls the same policy / generator / scheduler /
analytics code the CLI uses (via engine.service), so behaviour is identical. A
session holds the interleaving state (last subject, streak, DKT predictions) so
GET /session/{id}/next reproduces the global study loop one request at a time.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine import service
from engine.analytics.readiness import (
    concept_mastery,
    overall_progress,
    subject_readiness,
)
from engine.config import COLD_START_MASTERY, GLOBAL_WARMUP
from engine.db import dao
from engine.db.seed import load_all
from engine.engagement import RecordTracker
from engine.mathfmt import latexify
from engine.scheduler import policy
from engine.service import GRADE_LABEL
from engine.stats import profile
from engine.subjects import SUBJECTS

_rng = np.random.default_rng()


@dataclass
class _Session:
    db_id: int
    scope: str  # "global" or a subject key
    dkt_active: bool = False
    p_correct: dict | None = None
    last_subject: str | None = None
    index: int = 0
    streak: int = 0
    best_streak: int = 0
    xp_session: int = 0
    recent: list[bool] = field(default_factory=list)
    items: dict = field(default_factory=dict)
    retry_queue: list[tuple[str, int]] = field(default_factory=list)
    record_tracker: RecordTracker | None = None


_sessions: dict[int, _Session] = {}


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    load_all()
    yield


app = FastAPI(title="StudyEngine API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# All JSON endpoints live under /api; the built frontend (mounted at the end of
# this module) is served from / so one process serves the whole app.
api = APIRouter(prefix="/api")


class StartIn(BaseModel):
    scope: str = "global"  # "global" or a subject key


class AnswerIn(BaseModel):
    session_id: int
    item_id: int
    answer: str = ""
    elapsed_ms: int = 0


class MnemonicIn(BaseModel):
    concept_id: str
    text: str


class SettingIn(BaseModel):
    key: str
    value: str


class ExamDateIn(BaseModel):
    subject: str
    date: str | None = None  # ISO YYYY-MM-DD, or null to clear


class CardIn(BaseModel):
    subject: str
    question: str
    answer: str
    distractors: list[str]
    theory: str | None = None


@api.get("/subjects")
def get_subjects() -> list[dict]:
    return [
        {"key": s.key, "title": s.title, "blurb": s.blurb} for s in SUBJECTS.values()
    ]


@api.post("/session")
def start_session(body: StartIn) -> dict:
    if body.scope != "global" and body.scope not in SUBJECTS:
        raise HTTPException(422, f"unknown scope '{body.scope}'")
    db_id = dao.create_session(body.scope)
    sess = _Session(db_id=db_id, scope=body.scope)
    _init_live_state(sess)
    _sessions[db_id] = sess
    return {"session_id": db_id, "scope": body.scope, "dkt_active": sess.dkt_active}


def _init_live_state(sess: _Session) -> None:
    """State every live session needs, fresh or rebuilt after a restart.

    Missed concepts from earlier sessions are still owed a re-test — front-load
    them so an abandoned tab or a closed session never loses the errorful retry.
    Record baselines are snapshotted once here and updated in Python per answer,
    instead of re-scanning the whole interaction log on every submit.
    """
    sess.retry_queue = [(cid, 0) for cid in dao.pending_retries()]
    sess.record_tracker = RecordTracker.snapshot()
    from engine.tracing import infer
    sess.dkt_active = infer.dkt_is_active()
    if sess.dkt_active:
        sess.p_correct = infer.predict(dao.get_interaction_history_timed())


def _rebuild_session(session_id: int) -> _Session | None:
    """Restore a live session from the database after a server restart.

    Everything except the served-but-unanswered item survives: results, streaks,
    session XP, the serving index, and the persisted retry queue. The learner
    keeps their in-flight session instead of silently starting over.
    """
    row = dao.get_session(session_id)
    if row is None or row["ended_at"]:
        return None  # never resurrect a finished session — the client starts fresh
    sess = _Session(db_id=session_id, scope=row["subject"])
    results = dao.session_results(session_id)
    streak = best = xp = 0
    for r in results:
        streak = streak + 1 if r["is_correct"] else 0
        best = max(best, streak)
        if r["is_correct"]:
            xp += (r["grade"] or 0) * r["exam_weight"]
    sess.recent = [bool(r["is_correct"]) for r in results]
    sess.streak = streak
    sess.best_streak = best
    sess.xp_session = xp
    sess.index = dao.count_shown(session_id)
    sess.last_subject = results[-1]["subject"] if results else None
    _init_live_state(sess)
    _sessions[session_id] = sess
    return sess


def _get_or_rebuild(session_id: int) -> _Session | None:
    return _sessions.get(session_id) or _rebuild_session(session_id)


def _pop_retry(sess: _Session, force: bool) -> policy.Selection | None:
    """Serve a queued missed concept whose spacing gap has elapsed (errorful retry).

    Suppressed concepts are skipped (left queued): the retry path bypasses policy,
    so it must honor bury/suspend itself or a just-hidden concept comes right back.
    """
    if not sess.retry_queue:
        return None
    suppressed = dao.suppressed_concept_ids()
    for i, (cid, ready) in enumerate(sess.retry_queue):
        if cid in suppressed:
            continue
        if force or sess.index >= ready:
            concept = dao.get_concept(cid)
            sess.retry_queue.pop(i)
            if concept is not None:
                return policy.Selection(concept, "retry")
    return None


@api.get("/session/{session_id}/next")
def next_item(session_id: int) -> dict:
    sess = _get_or_rebuild(session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")

    selection = _pop_retry(sess, force=False)
    if selection is not None:
        return _serve(sess, selection)

    if sess.scope == "global":
        if sess.dkt_active and sess.index % 5 == 0:
            from engine.tracing import infer
            sess.p_correct = infer.predict(dao.get_interaction_history_timed())
        stalling = sess.recent[-2:] == [False, False]
        mode = "confidence" if (sess.index < GLOBAL_WARMUP or stalling) else "weak"
        selection = policy.select_global(
            list(SUBJECTS), avoid_subject=sess.last_subject, mode=mode,
            p_correct=sess.p_correct,
        )
    else:
        selection = policy.select_next(sess.scope)

    if selection is None:
        selection = _pop_retry(sess, force=True)  # drain pending re-tests before ending
    if selection is None:
        # The session is over: close it in the DB so the ended_at guard applies
        # to web sessions too and stale tabs can't resurrect it days later.
        dao.close_session(sess.db_id)
        answered = len(sess.recent)
        correct = sum(sess.recent)
        return {
            "done": True,
            "summary": {
                "answered": answered,
                "correct": correct,
                "accuracy": round(correct / answered, 3) if answered else 0.0,
                "best_streak": sess.best_streak,
                "xp_gained": sess.xp_session,
                **profile(),
            },
        }

    return _serve(sess, selection)


def _serve(sess: _Session, selection: policy.Selection) -> dict:
    """Build, log, and return one study item for a chosen concept."""
    from engine.config import LEECH_LAPSES
    item = service.build_item(selection.concept, _rng, selection.reason)
    item_id = service.log_item_shown(sess.db_id, item)
    sess.items[item_id] = item
    sess.index += 1
    is_generator = item.kind != "recall"
    fmt = latexify if is_generator else (lambda s: s)
    lapses = dao.get_lapses(item.concept_id)
    return {
        # Leech: repeatedly forgotten — the UI slows the learner down (theory forced
        # open, lapse count shown) because more raw reps demonstrably aren't working.
        "leech": lapses >= LEECH_LAPSES,
        "lapses": lapses,
        "done": False,
        "item_id": item_id,
        "concept_id": item.concept_id,
        "concept_name": item.concept_name,
        "subject": item.subject,
        "reason": item.reason,
        "mode": "generator" if is_generator else "recall",
        # High-mastery generator concepts drop the options: typed recall, not recognition.
        "input_mode": "typed" if is_generator and not item.choices else "choices",
        "question": fmt(item.question),
        "choices": item.choices,  # raw — compared on grade + echoed back as the answer
        "note": dao.get_mnemonic(item.concept_id),
        # Theory is authored markdown/LaTeX (rendered client-side); never latexify it.
        "theory": item.theory,
        # Cold start: not yet learned → the UI opens the explanation up front.
        "cold": concept_mastery(item.concept_id) < COLD_START_MASTERY,
    }


@api.post("/answer")
def submit_answer(body: AnswerIn) -> dict:
    sess = _get_or_rebuild(body.session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")
    item = sess.items.get(body.item_id)
    if item is None:
        # Served before a restart — the built item is gone, so it can't be graded.
        # The client just asks for the next item on the same (rebuilt) session.
        raise HTTPException(404, "unknown item for this session")

    if sess.record_tracker is None:
        sess.record_tracker = RecordTracker.snapshot()
    outcome = service.settle_answer(
        body.item_id, item, body.answer, body.elapsed_ms,
        sess.record_tracker, sess.streak, sess.best_streak, _rng,
    )

    # Fold the outcome into caller-owned session state the service doesn't touch.
    if not outcome.correct and item.reason != "retry":
        from engine.config import RETRY_GAP
        sess.retry_queue.append((item.concept_id, sess.index + RETRY_GAP))
    sess.recent.append(outcome.correct)
    sess.last_subject = item.subject
    sess.streak = outcome.streak
    sess.best_streak = outcome.best_streak
    sess.xp_session += outcome.xp

    from engine.config import FATIGUE_THRESHOLD, FATIGUE_WINDOW
    window = sess.recent[-FATIGUE_WINDOW:]
    fatigued = (
        len(window) >= FATIGUE_WINDOW
        and sum(window) / len(window) < FATIGUE_THRESHOLD
    )
    fmt = latexify if item.kind != "recall" else (lambda s: s)
    return {
        "is_correct": outcome.correct,
        "correct_answer": item.correct,  # raw — frontend matches it against a choice
        "grade": outcome.grade,
        "label": GRADE_LABEL[outcome.grade],
        "steps": [fmt(s) for s in item.explain],
        "reward": outcome.reward,
        "records": outcome.records,
        "combo_break": outcome.combo_break,
        "streak": outcome.streak,
        "combo": outcome.combo,
        "xp_gained": outcome.xp,
        "next_review_days": outcome.next_review_days,
        "theory": item.theory,  # authored markdown/LaTeX — rendered client-side, not latexified
        "why_wrong": outcome.why_wrong,
        "fatigued": fatigued,
        "ask_mnemonic": outcome.ask_mnemonic,
    }


@api.post("/mnemonic")
def save_mnemonic(body: MnemonicIn) -> dict:
    dao.save_mnemonic(body.concept_id, body.text)
    return {"ok": True}


@api.get("/settings")
def get_settings() -> list[dict]:
    """User-tunable settings with current values, defaults, and descriptions."""
    from engine import settings
    return settings.all_settings()


@api.post("/settings")
def put_setting(body: SettingIn) -> dict:
    from engine import settings
    try:
        settings.set_value(body.key, body.value)
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "settings": settings.all_settings()}


@api.get("/cards")
def list_cards() -> list[dict]:
    """Learner-authored recall cards (IKEA effect: own content sticks harder)."""
    return dao.list_user_cards()


@api.post("/cards")
def create_card(body: CardIn) -> dict:
    if body.subject not in SUBJECTS:
        raise HTTPException(422, f"unknown subject '{body.subject}'")
    question = body.question.strip()
    answer = body.answer.strip()
    distractors = [d.strip() for d in body.distractors if d.strip()]
    if not question or not answer:
        raise HTTPException(422, "question and answer are required")
    if not distractors:
        raise HTTPException(422, "at least one distractor is required")
    if answer in distractors:
        raise HTTPException(422, "a distractor equals the answer")
    concept_id = dao.create_user_card(
        body.subject, question, answer, distractors[:3],
        (body.theory or "").strip() or None,
    )
    return {"ok": True, "concept_id": concept_id}


@api.delete("/cards/{concept_id}")
def delete_card(concept_id: str) -> dict:
    if not dao.delete_user_card(concept_id):
        raise HTTPException(404, "not a user card or not found")
    return {"ok": True}


def _known_concept_or_404(concept_id: str) -> None:
    if dao.get_concept(concept_id) is None:
        raise HTTPException(404, f"unknown concept '{concept_id}'")


@api.post("/concepts/{concept_id}/suspend")
def suspend(concept_id: str) -> dict:
    """'I know this' — out of rotation until resumed from settings."""
    _known_concept_or_404(concept_id)
    dao.suspend_concept(concept_id)
    return {"ok": True}


@api.post("/concepts/{concept_id}/bury")
def bury(concept_id: str) -> dict:
    """'Not today' — hidden until tomorrow, then back automatically."""
    _known_concept_or_404(concept_id)
    dao.bury_concept(concept_id)
    return {"ok": True}


@api.post("/concepts/{concept_id}/resume")
def resume(concept_id: str) -> dict:
    _known_concept_or_404(concept_id)
    dao.resume_concept(concept_id)
    return {"ok": True}


@api.get("/concepts/suspended")
def suspended() -> list[dict]:
    return dao.list_suspended()


@api.post("/exam_date")
def set_exam_date(body: ExamDateIn) -> dict:
    """Set or clear a subject's exam date — drives the countdown and daily pace."""
    if body.subject not in SUBJECTS:
        raise HTTPException(422, f"unknown subject '{body.subject}'")
    try:
        dao.set_exam_date(body.subject, body.date)
    except ValueError as exc:
        raise HTTPException(422, f"bad date '{body.date}' (want YYYY-MM-DD)") from exc
    return {"ok": True}


@api.get("/stats")
def stats() -> dict:
    """Streak, level, XP, daily-goal progress, reviews waiting — the home HUD."""
    return profile()


@api.get("/quests")
def quests() -> list[dict]:
    """Today's rotating quests with live progress (bonus XP banks automatically)."""
    from engine.quests import todays_quests
    return todays_quests()


@api.get("/me")
def me_endpoint() -> dict:
    """Full learner profile: stats, achievements, personal bests, leeches, heatmap."""
    from engine.stats import me
    return me()


@api.get("/progress")
def progress() -> dict:
    from engine.config import DKT_MIN_INTERACTIONS
    from engine.tracing import infer

    result = overall_progress(list(SUBJECTS))
    result["dkt"] = {
        "active": infer.dkt_is_active(),
        "answered": dao.count_answered_interactions(),
        "gate": DKT_MIN_INTERACTIONS,
    }
    from engine.config import FSRS_MIN_REVIEWS
    from engine.scheduler.optimize import stored_parameters
    result["fsrs_fit"] = {
        "fitted": stored_parameters() is not None,
        "reviews": dao.count_answered_interactions(),
        "gate": FSRS_MIN_REVIEWS,
    }
    return result


@api.get("/progress/{subject}")
def subject_progress(subject: str) -> dict:
    if subject not in SUBJECTS:
        raise HTTPException(404, f"unknown subject '{subject}'")
    return subject_readiness(subject)


app.include_router(api)

# Serve the built single-page frontend from / when it exists (production / the
# `python -m engine.cli.app` launcher). Absent in pure-dev use, where Vite serves
# the UI and proxies /api here — then this mount is simply skipped.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
