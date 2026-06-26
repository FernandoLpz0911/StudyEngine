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
from engine.analytics.readiness import overall_progress, subject_readiness
from engine.config import GLOBAL_WARMUP
from engine.db import dao
from engine.db.seed import load_all
from engine.engagement import combo_label, reward_message
from engine.mathfmt import latexify
from engine.scheduler import policy, store
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
    from engine.tracing import infer
    sess.dkt_active = infer.dkt_is_active()
    if sess.dkt_active:
        sess.p_correct = infer.predict(dao.get_interaction_history_timed())
    _sessions[db_id] = sess
    return {"session_id": db_id, "scope": body.scope, "dkt_active": sess.dkt_active}


def _days_until(due) -> int | None:
    """Whole days until a card's next review (the 'back in N days' open loop)."""
    if due is None:
        return None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    d = due if due.tzinfo else due.replace(tzinfo=UTC)
    return max(0, (d - now).days)


def _pop_retry(sess: _Session, force: bool) -> policy.Selection | None:
    """Serve a queued missed concept whose spacing gap has elapsed (errorful retry)."""
    for i, (cid, ready) in enumerate(sess.retry_queue):
        if force or sess.index >= ready:
            concept = dao.get_concept(cid)
            sess.retry_queue.pop(i)
            if concept is not None:
                return policy.Selection(concept, "retry")
    return None


@api.get("/session/{session_id}/next")
def next_item(session_id: int) -> dict:
    sess = _sessions.get(session_id)
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
    item = service.build_item(selection.concept, _rng, selection.reason)
    item_id = service.log_item_shown(sess.db_id, item)
    sess.items[item_id] = item
    sess.index += 1
    is_generator = item.kind != "recall"
    fmt = latexify if is_generator else (lambda s: s)
    return {
        "done": False,
        "item_id": item_id,
        "concept_id": item.concept_id,
        "concept_name": item.concept_name,
        "subject": item.subject,
        "reason": item.reason,
        "mode": "generator" if is_generator else "recall",
        "question": fmt(item.question),
        "choices": item.choices,  # raw — compared on grade + echoed back as the answer
        "note": dao.get_mnemonic(item.concept_id),
        # Theory is authored markdown/LaTeX (rendered client-side); never latexify it.
        "theory": item.theory,
    }


@api.post("/answer")
def submit_answer(body: AnswerIn) -> dict:
    sess = _sessions.get(body.session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")
    item = sess.items.get(body.item_id)
    if item is None:
        raise HTTPException(404, "unknown item for this session")

    correct, grade = service.grade(body.answer, body.elapsed_ms, item)
    dao.log_answered(body.item_id, body.answer or None, correct, grade, body.elapsed_ms)
    new_state = store.apply_rating(store.get_or_create(item.concept_id), grade)
    store.save(new_state)
    next_review_days = _days_until(new_state.due)

    if not correct and item.reason != "retry":
        from engine.config import RETRY_GAP
        sess.retry_queue.append((item.concept_id, sess.index + RETRY_GAP))

    sess.recent.append(correct)
    sess.last_subject = item.subject
    sess.streak = sess.streak + 1 if correct else 0
    sess.best_streak = max(sess.best_streak, sess.streak)
    xp_gained = 0
    if correct:
        concept = dao.get_concept(item.concept_id)
        xp_gained = grade * (concept.exam_weight if concept else 1)
        sess.xp_session += xp_gained

    from engine.config import FATIGUE_THRESHOLD, FATIGUE_WINDOW
    window = sess.recent[-FATIGUE_WINDOW:]
    fatigued = (
        len(window) >= FATIGUE_WINDOW
        and sum(window) / len(window) < FATIGUE_THRESHOLD
    )
    why_wrong = "" if correct else service.explanation_for(body.answer, item)
    fmt = latexify if item.kind != "recall" else (lambda s: s)
    return {
        "is_correct": correct,
        "correct_answer": item.correct,  # raw — frontend matches it against a choice
        "grade": grade,
        "label": GRADE_LABEL[grade],
        "steps": [fmt(s) for s in item.explain],
        "reward": reward_message(correct, sess.streak, _rng),
        "streak": sess.streak,
        "combo": combo_label(sess.streak),
        "xp_gained": xp_gained,
        "next_review_days": next_review_days,
        "theory": item.theory,  # authored markdown/LaTeX — rendered client-side, not latexified
        "why_wrong": why_wrong,
        "fatigued": fatigued,
        "ask_mnemonic": (not correct) and dao.get_mnemonic(item.concept_id) is None,
    }


@api.post("/mnemonic")
def save_mnemonic(body: MnemonicIn) -> dict:
    dao.save_mnemonic(body.concept_id, body.text)
    return {"ok": True}


@api.get("/stats")
def stats() -> dict:
    """Streak, level, XP, daily-goal progress, reviews waiting — the home HUD."""
    return profile()


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
