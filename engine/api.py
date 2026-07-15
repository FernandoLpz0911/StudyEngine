"""HTTP API over the study engine — the backend the web frontend talks to.

Thin layer: every endpoint calls the same policy / generator / scheduler /
analytics code the CLI uses (via engine.service), so behaviour is identical. A
session holds the interleaving state (last subject, streak, DKT predictions) so
GET /session/{id}/next reproduces the global study loop one request at a time.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.analytics.readiness import (
    concept_mastery,
    overall_progress,
    subject_readiness,
)
from engine.config import COLD_START_MASTERY
from engine.db import dao
from engine.db.seed import load_all
from engine.loop import Done, StudyLoop, Turn
from engine.mathfmt import latexify
from engine.service import GRADE_LABEL
from engine.stats import profile
from engine.subjects import SUBJECTS

# Live sessions keyed by DB id, so a GET next / POST answer pair resolves against
# the same in-memory StudyLoop; evicted on Done or rebuilt after a restart.
_sessions: dict[int, StudyLoop] = {}


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
    loop = StudyLoop.start(body.scope)
    _sessions[loop.db_id] = loop
    return {
        "session_id": loop.db_id, "scope": body.scope, "dkt_active": loop.dkt_active
    }


def _get_or_rebuild(session_id: int) -> StudyLoop | None:
    """The resident StudyLoop, or one rebuilt from the DB after a server restart."""
    loop = _sessions.get(session_id)
    if loop is None:
        loop = StudyLoop.rebuild(session_id)
        if loop is not None:
            _sessions[session_id] = loop
    return loop


@api.get("/session/{session_id}/next")
def next_item(session_id: int) -> dict:
    loop = _get_or_rebuild(session_id)
    if loop is None:
        raise HTTPException(404, "unknown session")

    step = loop.next()
    if isinstance(step, Done):
        # The loop already closed the DB session; evict the resident copy so the
        # ended_at guard applies on the next request (rebuild path) and a
        # long-running server can't keep serving from the in-memory session.
        _sessions.pop(loop.db_id, None)
        return {"done": True, "summary": {**step.summary, **profile()}}
    return _serve_json(step)


def _serve_json(turn: Turn) -> dict:
    """Render one served item as the /next payload — transport only; the StudyLoop
    has already built, logged, and stored it."""
    from engine.config import LEECH_LAPSES
    item = turn.item
    is_generator = item.kind != "recall"
    fmt = latexify if is_generator else (lambda s: s)
    lapses = dao.get_lapses(item.concept_id)
    return {
        # Leech: repeatedly forgotten — the UI slows the learner down (theory forced
        # open, lapse count shown) because more raw reps demonstrably aren't working.
        "leech": lapses >= LEECH_LAPSES,
        "lapses": lapses,
        "done": False,
        "item_id": turn.item_id,
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
    loop = _get_or_rebuild(body.session_id)
    if loop is None:
        raise HTTPException(404, "unknown session")
    item = loop.items.get(body.item_id)
    if item is None:
        # Served before a restart — the built item is gone, so it can't be graded.
        # The client just asks for the next item on the same (rebuilt) session.
        raise HTTPException(404, "unknown item for this session")

    outcome = loop.settle(body.item_id, body.answer, body.elapsed_ms)

    from engine.config import FATIGUE_THRESHOLD, FATIGUE_WINDOW
    window = loop.recent[-FATIGUE_WINDOW:]
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
