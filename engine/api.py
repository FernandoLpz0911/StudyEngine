"""HTTP API over the study engine — the backend the web frontend talks to.

Thin layer: every endpoint calls the same policy / generator / scheduler /
analytics code the CLI uses (via engine.service), so behaviour is identical. A
session holds the interleaving state (last subject, streak, DKT predictions) so
GET /session/{id}/next reproduces the global study loop one request at a time.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine import service
from engine.analytics.readiness import overall_progress, subject_readiness
from engine.config import GLOBAL_WARMUP
from engine.db import dao
from engine.db.seed import load_all
from engine.engagement import reward_message
from engine.scheduler import policy, store
from engine.service import GRADE_LABEL
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
    recent: list[bool] = field(default_factory=list)
    items: dict = field(default_factory=dict)


_sessions: dict[int, _Session] = {}


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    load_all()
    yield


app = FastAPI(title="StudyEngine API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


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


@app.get("/subjects")
def get_subjects() -> list[dict]:
    return [
        {"key": s.key, "title": s.title, "blurb": s.blurb} for s in SUBJECTS.values()
    ]


@app.post("/session")
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


@app.get("/session/{session_id}/next")
def next_item(session_id: int) -> dict:
    sess = _sessions.get(session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")

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
        return {"done": True}

    item = service.build_item(selection.concept, _rng, selection.reason)
    item_id = service.log_item_shown(sess.db_id, item)
    sess.items[item_id] = item
    sess.index += 1
    return {
        "done": False,
        "item_id": item_id,
        "concept_id": item.concept_id,
        "concept_name": item.concept_name,
        "subject": item.subject,
        "reason": item.reason,
        "mode": "recall" if item.kind == "recall" else "generator",
        "question": item.question,
        "choices": item.choices,
        "note": dao.get_mnemonic(item.concept_id),
    }


@app.post("/answer")
def submit_answer(body: AnswerIn) -> dict:
    sess = _sessions.get(body.session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")
    item = sess.items.get(body.item_id)
    if item is None:
        raise HTTPException(404, "unknown item for this session")

    correct, grade = service.grade(body.answer, body.elapsed_ms, item)
    dao.log_answered(body.item_id, body.answer or None, correct, grade, body.elapsed_ms)
    store.save(store.apply_rating(store.get_or_create(item.concept_id), grade))

    sess.recent.append(correct)
    sess.last_subject = item.subject
    sess.streak = sess.streak + 1 if correct else 0
    return {
        "is_correct": correct,
        "correct_answer": item.correct,
        "grade": grade,
        "label": GRADE_LABEL[grade],
        "steps": item.explain,
        "reward": reward_message(correct, sess.streak, _rng),
        "ask_mnemonic": (not correct) and dao.get_mnemonic(item.concept_id) is None,
    }


@app.post("/mnemonic")
def save_mnemonic(body: MnemonicIn) -> dict:
    dao.save_mnemonic(body.concept_id, body.text)
    return {"ok": True}


@app.get("/progress")
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


@app.get("/progress/{subject}")
def subject_progress(subject: str) -> dict:
    if subject not in SUBJECTS:
        raise HTTPException(404, f"unknown subject '{subject}'")
    return subject_readiness(subject)
