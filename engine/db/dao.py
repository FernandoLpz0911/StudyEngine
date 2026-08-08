"""Data-access layer — all SQLite reads/writes go through here."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from engine.db.connection import get_connection


@dataclass
class Concept:
    """One node in a subject's concept graph."""

    id: str
    subject: str
    name: str
    category: str | None
    mode: str  # "generator" | "recall"
    domain: str | None = None
    generator: dict | None = None
    card_question: str | None = None
    card_answer: str | None = None
    card_distractors: list[str] = field(default_factory=list)
    card_explanations: dict[str, str] = field(default_factory=dict)
    theory_md: str | None = None
    exam_weight: int = 1
    prerequisites: list[str] = field(default_factory=list)


def _row_to_concept(row, prereqs: list[str]) -> Concept:
    return Concept(
        id=row["id"],
        subject=row["subject"],
        name=row["name"],
        category=row["category"],
        mode=row["mode"],
        domain=row["domain"] if "domain" in row.keys() else None,
        generator=json.loads(row["generator_json"]) if row["generator_json"] else None,
        card_question=row["card_question"],
        card_answer=row["card_answer"],
        card_distractors=json.loads(row["card_distractors"]) if row["card_distractors"] else [],
        card_explanations=(
            json.loads(row["card_explanations"])
            if "card_explanations" in row.keys() and row["card_explanations"]
            else {}
        ),
        theory_md=row["theory_md"],
        exam_weight=row["exam_weight"],
        prerequisites=prereqs,
    )


def drills_today(subject: str, today: date | None = None) -> dict[str, int]:
    """How many drills each concept has already taken on the current local day.

    A correct drill deliberately leaves card state alone, so mastery does not move
    and "the weakest concept" would otherwise be the same concept all day — the
    day's top-up would become one concept massed twenty times. Rotating on this
    count spreads drills over the weakest concepts instead (ADR-0008).
    """
    start, end = local_day_bounds(today or _local_today())
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, COUNT(*) AS n FROM interaction
            WHERE subject = ? AND reason = 'drill'
              AND shown_at >= ? AND shown_at < ?
            GROUP BY concept_id
            """,
            (subject, start, end),
        ).fetchall()
    return {r["concept_id"]: r["n"] for r in rows}


def recent_accuracy(subject: str, window: int) -> float | None:
    """Fraction correct over the subject's last `window` settled answers.

    Whether the learner is running ahead of the plan, measured across the subject
    rather than per concept: the question is how the studying is going overall,
    not whether one card happens to be easy.

    Solo attempts only, for the same reason as `get_concept_accuracy`: this number
    both opens the frontier past its deadline and closes it under the accuracy
    floor, and scaffolded answers would push it in the wrong direction on both.
    Guessing-corrected for the same reason too — an uncorrected 40% over a
    multiple-choice history is really about 20%.
    """
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT is_correct, choices_n FROM interaction
            WHERE subject = ? AND is_correct IS NOT NULL AND {MEASURED}
            ORDER BY id DESC LIMIT ?
            """,
            (subject, window),
        ).fetchall()
    if len(rows) < window:  # too little evidence to call anyone ahead
        return None
    return deguess(rows)


def count_unseen_concepts(subject: str) -> int:
    """Concepts in a subject never yet served — the coverage backlog.

    One aggregate rather than a card-state read per concept: the intro quota is
    recomputed on every item served, so it must not cost a query per concept.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM concept c
            LEFT JOIN card_state cs ON cs.concept_id = c.id
            WHERE c.subject = ? AND COALESCE(cs.reps, 0) = 0
            """,
            (subject,),
        ).fetchone()
    return row["n"] if row else 0


def get_concepts(subject: str) -> list[Concept]:
    """All concepts for a subject, each with its prerequisite list."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM concept WHERE subject = ? ORDER BY id", (subject,)
        ).fetchall()
        prereq_rows = conn.execute("SELECT * FROM concept_prereq").fetchall()

    prereqs: dict[str, list[str]] = {}
    for row in prereq_rows:
        prereqs.setdefault(row["concept_id"], []).append(row["prereq_id"])

    return [_row_to_concept(row, prereqs.get(row["id"], [])) for row in rows]


def get_concept(concept_id: str) -> Concept | None:
    """A single concept with its prerequisites, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM concept WHERE id = ?", (concept_id,)).fetchone()
        if row is None:
            return None
        prereq_rows = conn.execute(
            "SELECT prereq_id FROM concept_prereq WHERE concept_id = ?", (concept_id,)
        ).fetchall()
    return _row_to_concept(row, [r["prereq_id"] for r in prereq_rows])


def list_subjects() -> list[str]:
    """Distinct subjects present in the database."""
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT subject FROM concept ORDER BY subject").fetchall()
    return [r["subject"] for r in rows]


def create_session(subject: str) -> int:
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO session (subject, started_at) VALUES (?, ?)", (subject, now)
        )
        return cur.lastrowid


def get_session(session_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, subject, started_at, ended_at FROM session WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def session_results(session_id: int) -> list[dict]:
    """Graded answers of one session in order — enough to rebuild its live state."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT i.is_correct, i.grade, COALESCE(c.exam_weight, 1) AS exam_weight, "
            "i.subject, i.aided FROM interaction i "
            "LEFT JOIN concept c ON c.id = i.concept_id "
            "WHERE i.session_id = ? AND i.is_correct IS NOT NULL ORDER BY i.id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def count_shown(session_id: int) -> int:
    """Items served in a session (answered or not) — restores the serving index."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row["n"] if row else 0


def close_session(session_id: int) -> None:
    # Idempotent: only the first close stamps ended_at, so re-closing (a CLI
    # double-close, or the web done-path after the DB row is already ended)
    # can't overwrite the original end time.
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE session SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (now, session_id),
        )


def log_shown(
    session_id: int,
    concept_id: str,
    subject: str,
    kind: str,
    seed: int = 0,
    params_json: str = "{}",
    correct_answer: str | None = None,
    reason: str | None = None,
    stage: str = "solo",
    choices_n: int = 0,
) -> int:
    """Record that a problem/card was served. Returns the interaction id.

    `reason` is why the item was chosen (new / review / retry / drill). It is
    persisted because one of those values changes what the answer means: a drill
    is an off-schedule attempt, so it must be kept out of the FSRS weight fit
    (ADR-0008).

    `stage` is how much help the item came with (ADR-0013). It is persisted for
    the same reason: a scaffolded answer is not evidence of unaided skill, so
    every accuracy read filters on it.

    `choices_n` is how many options were offered, 0 for free response (ADR-0014).
    Persisted because it sets how much of a correct answer could have been luck,
    which is what the guessing correction needs to undo.
    """
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO interaction
                (session_id, concept_id, subject, kind, seed, params_json,
                 correct_answer, shown_at, reason, stage, choices_n)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, concept_id, subject, kind, seed, params_json,
             correct_answer, now, reason or None, stage, choices_n),
        )
        return cur.lastrowid


def log_answered(
    item_id: int,
    user_answer: str | None,
    is_correct: bool | None,
    grade: int,
    elapsed_ms: int = 0,
    dont_know: bool = False,
    aided: bool = False,
) -> None:
    """Record the answer.

    `dont_know` is stored in its own column rather than inferred from a null
    answer: a blank submission and a deliberate "I don't know" look identical in
    `user_answer`, and only one of them is evidence.

    `aided` means the explanation was opened before answering. Without it a bare
    item solved with the theory on screen is logged as unaided evidence, which is
    the same lie as counting a worked example — just one the learner tells rather
    than the system.
    """
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE interaction
            SET user_answer = ?, is_correct = ?, grade = ?,
                elapsed_ms = ?, answered_at = ?, dont_know = ?, aided = ?
            WHERE id = ?
            """,
            (
                user_answer,
                int(is_correct) if is_correct is not None else None,
                grade,
                elapsed_ms,
                now,
                int(dont_know),
                int(aided),
                item_id,
            ),
        )


#: What makes an attempt count toward readiness: served bare *and* answered without
#: opening the explanation (ADR-0014). Written once and reused, because the failure
#: mode here is a read that filters one condition and forgets the other — which is
#: precisely how scaffolded retention survived the first pass at this.
MEASURED = "stage = 'solo' AND aided = 0"

#: The rung an attempt actually happened at. A bare item answered with the
#: explanation open was not a bare attempt, so it is read as a guided one — which
#: is what keeps it out of readiness while still crediting it toward ascent. The
#: served stage stays in the log untouched; only the *reading* moves.
EFFECTIVE_STAGE = "CASE WHEN aided = 1 THEN 'paired' ELSE stage END"


def deguess(rows: list) -> float | None:
    """Unaided skill behind a set of graded answers, with luck backed out.

    An answer chosen from `choices_n` options is right with probability 1/n while
    knowing nothing, so an observed *rate* over such answers overstates skill by
    the guessing floor. `(observed - ḡ) / (1 - ḡ)` inverts that, where ḡ is the
    mean guess probability across the very answers being measured.

    Self-retiring by construction: free response carries ḡ = 0, so the correction
    shrinks to nothing as real answers replace the multiple-choice history — no
    flag day, and no second number to keep in step (ADR-0014).

    A population correction applied to a small sample is an estimate, but it
    replaces a *known-biased* estimate rather than a neutral one: leaving it out
    asserts the guessing floor is zero, which is the one value it certainly is not.
    """
    if not rows:
        return None
    from engine.config import DEGUESS_HISTORY

    observed = sum(r["is_correct"] for r in rows) / len(rows)
    if not DEGUESS_HISTORY:
        return observed
    guess = sum(1.0 / n if (n := (r["choices_n"] or 0)) > 1 else 0.0 for r in rows)
    g_bar = guess / len(rows)
    if g_bar >= 1.0:
        return observed
    return max(0.0, min(1.0, (observed - g_bar) / (1.0 - g_bar)))


def get_concept_accuracy(concept_id: str, window: int = 10) -> float | None:
    """Recent unaided skill for a concept, over its last `window` solo items.

    Solo attempts only (ADR-0013). A study trial is the worked solution being read
    back, and a paired attempt came after seeing that solution worked through on a
    sibling problem; counting either would report the learner's ability to copy.
    This number feeds mastery, drill targeting, and the projected exam score, so
    inflating it here would inflate every readiness signal at once.

    Corrected for guessing (ADR-0014), because the historical log is entirely
    four-option multiple choice and an uncorrected rate over it credits a quarter
    of the wrong answers as knowledge.
    """
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT is_correct, choices_n FROM interaction
            WHERE concept_id = ? AND is_correct IS NOT NULL AND {MEASURED}
            ORDER BY id DESC LIMIT ?
            """,
            (concept_id, window),
        ).fetchall()
    return deguess(rows)


def stage_accuracy(concept_id: str, stage: str, window: int) -> float | None:
    """Skill at one rung of the ladder — what promotion off that rung is judged on.

    Promotion cannot wait on solo accuracy, because a concept held at `paired`
    never produces a solo attempt, so the bar would be measured from evidence the
    stage itself prevents. Measuring at the *current* rung makes promotion and
    demotion the same comparison (ADR-0014).
    """
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT is_correct, choices_n FROM interaction
            WHERE concept_id = ? AND is_correct IS NOT NULL
              AND {EFFECTIVE_STAGE} = ?
            ORDER BY id DESC LIMIT ?
            """,
            (concept_id, stage, window),
        ).fetchall()
    return deguess(rows)


def recent_attempts(concept_id: str, window: int) -> list[tuple[str, bool, bool]]:
    """The concept's last `window` attempts as (stage, correct, dont_know), newest
    first. The evidence `teaching.stage_for` derives a concept's stage from,
    returned as plain tuples so the teaching rules stay free of any database type.

    The stage reported is the *effective* one, so an aided answer to a bare item
    cannot be mistaken for unaided evidence by the rules that promote and demote.
    """
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {EFFECTIVE_STAGE} AS stage, is_correct, dont_know
            FROM interaction
            WHERE concept_id = ? AND is_correct IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (concept_id, window),
        ).fetchall()
    return [
        (r["stage"] or "solo", bool(r["is_correct"]), bool(r["dont_know"]))
        for r in rows
    ]


def solo_reps(concept_id: str) -> int:
    """How many unaided attempts a concept has had.

    The rep-confidence term in mastery asks "how much evidence is there", and a
    guided rep is evidence of exposure, not of skill. Counting it would let a
    concept read as well-evidenced while nothing unaided had been shown — which is
    how mastery's third factor stayed scaffolded after its first two were fixed.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction "
            f"WHERE concept_id = ? AND is_correct IS NOT NULL AND {MEASURED}",
            (concept_id,),
        ).fetchone()
    return row["n"] if row else 0


def last_solo_review(concept_id: str) -> datetime | None:
    """When the concept was last answered unaided, or None if it never was.

    Readiness decays from *this*, not from the last review of any kind. FSRS is
    right to reset its clock on a guided review — the card was seen — but nothing
    about unaided recall was demonstrated, so crediting it would let a run of
    worked examples walk the projected score up on its own.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(answered_at) AS t FROM interaction "
            f"WHERE concept_id = ? AND is_correct IS NOT NULL AND {MEASURED}",
            (concept_id,),
        ).fetchone()
    if row is None or row["t"] is None:
        return None
    return datetime.fromisoformat(row["t"])


def stage_times(subject: str) -> dict[str, dict[str, list[float]]]:
    """Per-concept elapsed seconds, split into scaffolded and unaided attempts.

    Feeds the slog report only (ADR-0014) — never the schedule. Clamped by the
    same ceiling the grader uses, so one abandoned tab cannot define a median.
    """
    from engine.config import MAX_ANSWER_MS

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT concept_id, stage, elapsed_ms FROM interaction "
            "WHERE subject = ? AND is_correct IS NOT NULL AND elapsed_ms IS NOT NULL",
            (subject,),
        ).fetchall()
    out: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        bucket = "solve" if (row["stage"] or "solo") == "solo" else "understand"
        entry = out.setdefault(row["concept_id"], {"solve": [], "understand": []})
        entry[bucket].append(min(row["elapsed_ms"], MAX_ANSWER_MS) / 1000.0)
    return out


def subject_stats(subject: str) -> dict:
    """Answered count and accuracy for a subject (for the study summary)."""
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE subject = ? AND is_correct IS NOT NULL",
            (subject,),
        ).fetchone()["n"]
        correct = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE subject = ? AND is_correct = 1",
            (subject,),
        ).fetchone()["n"]
    return {
        "answered": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
    }


def save_mnemonic(concept_id: str, text: str) -> None:
    """Store the learner's own hint for a concept (IKEA effect: they invest)."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO mnemonic (concept_id, text, created_at) "
            "VALUES (?, ?, ?)",
            (concept_id, text, now),
        )


def get_mnemonic(concept_id: str) -> str | None:
    """The learner's saved hint for a concept, resurfaced on later encounters."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT text FROM mnemonic WHERE concept_id = ?", (concept_id,)
        ).fetchone()
    return row["text"] if row else None


def get_setting(key: str) -> str | None:
    """Raw stored value for a user setting, or None when unset (config default applies)."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO setting (key, value) VALUES (?, ?)", (key, value)
        )


USER_CARD_PREFIX = "user."


def create_user_card(
    subject: str,
    question: str,
    answer: str,
    distractors: list[str],
    theory_md: str | None = None,
) -> str:
    """Insert a learner-authored recall card; returns its concept id.

    User cards live in the same concept table (id prefixed "user.") so the
    scheduler, grading, and analytics treat them like seeded content. Seed
    reloads use INSERT OR REPLACE by id and never touch this prefix.
    """
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    concept_id = f"{USER_CARD_PREFIX}{subject}.{now_ms}"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO concept
                (id, subject, name, category, mode,
                 card_question, card_answer, card_distractors, theory_md, exam_weight)
            VALUES (?, ?, ?, 'My cards', 'recall', ?, ?, ?, ?, 1)
            """,
            (
                concept_id,
                subject,
                question[:60] + ("…" if len(question) > 60 else ""),
                question,
                answer,
                json.dumps(distractors),
                theory_md,
            ),
        )
    return concept_id


def list_user_cards() -> list[dict]:
    """Learner-authored cards, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, subject, card_question AS question, card_answer AS answer, "
            "card_distractors AS distractors FROM concept "
            "WHERE id LIKE ? ORDER BY id DESC",
            (f"{USER_CARD_PREFIX}%",),
        ).fetchall()
    return [
        {**dict(r), "distractors": json.loads(r["distractors"] or "[]")} for r in rows
    ]


def delete_user_card(concept_id: str) -> bool:
    """Remove a learner-authored card and all its traces; False if not a user card."""
    if not concept_id.startswith(USER_CARD_PREFIX):
        return False
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM concept WHERE id = ?", (concept_id,)
        ).fetchone()
        if not exists:
            return False
        # Owner deletes their own card: its study history goes with it (FK order).
        for table in ("interaction", "card_state", "mnemonic", "pending_retry"):
            conn.execute(f"DELETE FROM {table} WHERE concept_id = ?", (concept_id,))
        conn.execute("DELETE FROM concept_prereq WHERE concept_id = ?", (concept_id,))
        conn.execute("DELETE FROM concept WHERE id = ?", (concept_id,))
    return True


def suspend_concept(concept_id: str) -> None:
    """'I know this / stop showing it' — out of rotation until resumed.

    A suspended concept owes nothing, so any pending re-test goes with it.
    """
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO concept_suppression (concept_id, until, created_at) "
            "VALUES (?, NULL, ?)",
            (concept_id, now),
        )
        conn.execute("DELETE FROM pending_retry WHERE concept_id = ?", (concept_id,))


def bury_concept(concept_id: str) -> None:
    """'Not today' — hidden until the next local day, then back automatically.

    A no-op on a suspended concept: burying must not silently demote an
    indefinite 'I know this' into a one-day hide.
    """
    now = datetime.now(UTC).isoformat()
    until = (_local_today() + timedelta(days=1)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT until FROM concept_suppression WHERE concept_id = ?",
            (concept_id,),
        ).fetchone()
        if row and row["until"] is None:
            return
        conn.execute(
            "INSERT OR REPLACE INTO concept_suppression (concept_id, until, created_at) "
            "VALUES (?, ?, ?)",
            (concept_id, until, now),
        )


def resume_concept(concept_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM concept_suppression WHERE concept_id = ?", (concept_id,)
        )


def suspended_concept_ids() -> set[str]:
    """Only the indefinitely suspended ('I know this') concepts — not buried ones.

    Suspension implies mastery, so these count as introduced prerequisites; a
    one-day bury implies nothing and must not unlock dependents.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT concept_id FROM concept_suppression WHERE until IS NULL"
        ).fetchall()
    return {r["concept_id"] for r in rows}


def suppressed_concept_ids(today: date | None = None) -> set[str]:
    """Concepts currently out of rotation (suspended, or buried and not yet due back)."""
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT concept_id FROM concept_suppression WHERE until IS NULL OR until > ?",
            (today,),
        ).fetchall()
    return {r["concept_id"] for r in rows}


def list_suspended() -> list[dict]:
    """Indefinitely suspended concepts, for the resume list in settings."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT cs.concept_id AS id, c.name AS name, c.subject AS subject "
            "FROM concept_suppression cs JOIN concept c ON c.id = cs.concept_id "
            "WHERE cs.until IS NULL ORDER BY c.subject, c.name"
        ).fetchall()
    return [dict(r) for r in rows]


def set_exam_date(subject: str, iso_date: str | None) -> None:
    """Set (or clear with None) the exam date for a subject, ISO YYYY-MM-DD."""
    key = f"exam_date.{subject}"
    with get_connection() as conn:
        if iso_date is None:
            conn.execute("DELETE FROM setting WHERE key = ?", (key,))
        else:
            date.fromisoformat(iso_date)  # validate before storing
            conn.execute(
                "INSERT OR REPLACE INTO setting (key, value) VALUES (?, ?)",
                (key, iso_date),
            )


def get_exam_date(subject: str) -> date | None:
    raw = get_setting(f"exam_date.{subject}")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def add_pending_retry(concept_id: str) -> None:
    """Queue a missed concept for re-testing that survives the end of the session."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO pending_retry (concept_id, created_at) VALUES (?, ?)",
            (concept_id, now),
        )


def remove_pending_retry(concept_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM pending_retry WHERE concept_id = ?", (concept_id,))


def pending_retries() -> list[str]:
    """Missed concepts still owed a re-test, oldest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT concept_id FROM pending_retry ORDER BY created_at"
        ).fetchall()
    return [r["concept_id"] for r in rows]


def record_reflection(
    interaction_id: int, concept_id: str, step_index: int | None
) -> None:
    """Store which worked-solution step the learner says they first went wrong at.

    `step_index` is None for an explicit "not sure", which is deliberately stored
    rather than discarded: not being able to locate the break is itself the most
    useful thing the concept can report about how well it is understood.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reflection "
            "(interaction_id, concept_id, step_index, created_at) VALUES (?, ?, ?, ?)",
            (interaction_id, concept_id, step_index, datetime.now(UTC).isoformat()),
        )


def step_breakdown(concept_id: str) -> dict[str, int]:
    """How often each solution step was named as the break, plus "not sure".

    The one signal the log never carried: *where* a concept fails, as opposed to
    that it failed. A concept whose misses cluster on one step needs that step
    taught; one whose misses scatter needs the whole concept re-taught.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT step_index, COUNT(*) AS n FROM reflection "
            "WHERE concept_id = ? GROUP BY step_index",
            (concept_id,),
        ).fetchall()
    return {
        ("unsure" if r["step_index"] is None else str(r["step_index"])): r["n"]
        for r in rows
    }


def count_new_concepts_today(
    today: date | None = None, subject: str | None = None
) -> int:
    """Concepts first shown on the current local day (drives the new-per-day cap).

    The unscoped count is the cap's own denominator — the flood it guards against
    is global. Scoping to a subject answers a different question: how much of that
    subject's coverage deadline today has already paid (see `analytics.pace`).
    """
    start, end = local_day_bounds(today or _local_today())
    where = "" if subject is None else "WHERE subject = ?"
    params: list[object] = [] if subject is None else [subject]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM ("
            "  SELECT concept_id, MIN(shown_at) AS first_shown FROM interaction"
            f"  {where}"
            "  GROUP BY concept_id"
            ") WHERE first_shown >= ? AND first_shown < ?",
            (*params, start, end),
        ).fetchone()
    return row["n"] if row else 0


def all_concept_ids() -> list[str]:
    """Every concept id across all subjects, sorted (the global DKT index order)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM concept ORDER BY id").fetchall()
    return [r["id"] for r in rows]


def count_answered_interactions() -> int:
    """Total graded interactions across all subjects (for the DKT activation gate)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE is_correct IS NOT NULL"
        ).fetchone()
    return row["n"] if row else 0


def total_xp() -> int:
    """Lifetime XP: every correct retrieval scores its FSRS grade × exam weight.

    Ties progression to *spaced retrieval value*, not time-on-app — a fast, hard,
    high-weight concept recalled correctly is worth more than an easy repeat, and a
    wrong answer scores nothing. Keeps the addictive number aligned with learning.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(i.grade * COALESCE(c.exam_weight, 1)), 0) AS xp
            FROM interaction i JOIN concept c ON c.id = i.concept_id
            WHERE i.is_correct = 1
            """
        ).fetchone()
    return (int(row["xp"]) if row else 0) + quest_bonus_xp()


def _answered_days() -> list[date]:
    """Distinct local dates on which any item was answered, most recent first.

    Grouped in Python rather than SQL: this spans the whole history, so each
    timestamp needs the UTC offset that was in force *for it*, which a single
    SQLite modifier cannot express across a DST change.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT answered_at FROM interaction WHERE answered_at IS NOT NULL"
        ).fetchall()
    days: set[date] = set()
    for row in rows:
        try:
            days.add(local_day(row["answered_at"]))
        except (ValueError, TypeError):
            continue
    return sorted(days, reverse=True)


def _answers_per_local_day(exclude: date | None = None) -> dict[date, int]:
    """How many answers fell on each local day. Grouped in Python, see _answered_days."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT answered_at FROM interaction WHERE answered_at IS NOT NULL"
        ).fetchall()
    counts: dict[date, int] = {}
    for row in rows:
        try:
            day = local_day(row["answered_at"])
        except (ValueError, TypeError):
            continue
        if day == exclude:
            continue
        counts[day] = counts.get(day, 0) + 1
    return counts


@lru_cache(maxsize=8)
def _zone(name: str) -> ZoneInfo:
    """The configured study timezone, falling back to UTC if the name is unknown."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def study_zone() -> ZoneInfo:
    from engine.config import STUDY_TIMEZONE
    return _zone(STUDY_TIMEZONE)


def local_day(when: datetime | str) -> date:
    """The learner's study day for a stored UTC timestamp.

    Timestamps are written as UTC; which *day* they belong to is a question about
    the learner's wall clock, and the answer shifts with DST. Converting through a
    real zone means an answer at 23:30 in Chicago counts for that day whether the
    UTC offset happens to be 5 or 6 hours.

    The day then runs from `DAY_ROLLOVER_HOUR`, so a 1am answer is bucketed into
    the day before — the streak this backs must not break because a session ran
    past midnight, and the best-day record must not split one sitting in two.
    Takes a stored UTC instant; `study_today` is the same rule applied to a
    wall-clock time already in the learner's zone.
    """
    from engine.config import DAY_ROLLOVER_HOUR
    if isinstance(when, str):
        when = datetime.fromisoformat(when)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    local = when.astimezone(study_zone())
    return (local - timedelta(hours=DAY_ROLLOVER_HOUR)).date()


def local_day_bounds(day: date) -> tuple[str, str]:
    """The UTC half-open interval [start, end) covering one local day.

    Used instead of SQLite's `date(ts, '+N hours')`: SQLite has no timezone
    database, so a modifier can only ever express one fixed offset and is an hour
    wrong for half the year. Comparing stored UTC timestamps against precomputed
    UTC bounds is exact, and uses the index on `answered_at`.
    """
    from engine.config import DAY_ROLLOVER_HOUR
    zone = study_zone()
    rollover = time(hour=DAY_ROLLOVER_HOUR)
    start = datetime.combine(day, rollover, tzinfo=zone)
    # Built from the next calendar date rather than start + 24h: across a DST
    # boundary a fixed 24 hours lands an hour either side of the rollover, which
    # would leave a gap or an overlap between consecutive days.
    end = datetime.combine(day + timedelta(days=1), rollover, tzinfo=zone)
    return start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()


def local_now() -> datetime:
    """Wall-clock time in the learner's timezone."""
    return datetime.now(UTC).astimezone(study_zone())


def study_today(now: datetime | None = None) -> date:
    """The study day the learner is currently in.

    The day turns over at `DAY_ROLLOVER_HOUR`, not midnight, so everything that
    means "today" — streak, daily goal, quests, new-per-day cap, records, the
    gate's quota — belongs to the day the learner is still awake in. Answering at
    1am finishes the previous day rather than silently starting a fresh one, which
    at midnight would break a streak mid-session, pay the gate for a day not yet
    lived, and split one sitting across two days of statistics.
    """
    from engine.config import DAY_ROLLOVER_HOUR
    return ((now or local_now()) - timedelta(hours=DAY_ROLLOVER_HOUR)).date()


def _local_today() -> date:
    return study_today()


def daily_streak(today: date | None = None) -> int:
    """Consecutive study days ending today, with earned freezes bridging slips.

    Loss aversion: a visible streak the learner won't want to break is the single
    strongest pull back into the app, and it enforces the daily cadence FSRS needs.
    One freeze is earned per STREAK_FREEZE_EARN_DAYS studied days; each silently
    bridges a single missed day so one slip never resets the chain.
    """
    from engine.config import STREAK_FREEZE_EARN_DAYS
    today = today or _local_today()
    days = set(_answered_days())
    if not days:
        return 0
    bridges = len(days) // STREAK_FREEZE_EARN_DAYS
    cursor = today
    if cursor not in days:  # current day still in progress — don't penalise it
        cursor -= timedelta(days=1)
    streak = 0
    while True:
        if cursor in days:
            streak += 1
        elif bridges > 0:
            bridges -= 1  # a freeze covers this gap; chain survives
        else:
            break
        cursor -= timedelta(days=1)
    return streak


def freeze_status() -> dict:
    """Earned / consumed streak freezes — surfaced so the safety net is visible."""
    from engine.config import STREAK_FREEZE_EARN_DAYS
    earned = len(_answered_days()) // STREAK_FREEZE_EARN_DAYS
    return {"earned": earned, "earn_days": STREAK_FREEZE_EARN_DAYS}


def study_days(limit: int = 372) -> list[str]:
    """Recent distinct local study dates (ISO) for the contribution heatmap."""
    return [d.isoformat() for d in _answered_days()[:limit]]


def count_answered_today(today: date | None = None) -> int:
    """Items answered so far on the current local day (drives the daily-goal ring)."""
    start, end = local_day_bounds(today or _local_today())
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at >= ? AND answered_at < ?",
            (start, end),
        ).fetchone()
    return row["n"] if row else 0


def count_correct_today(subject: str | None = None, today: date | None = None) -> int:
    """Correct answers on the current local day — the study gate's quota counter.

    Deliberately *not* count_answered_today: the gate is paid in work done, not
    attempts made, so twenty wrong answers cannot open it (ADR-0005).

    Unfiltered by stage, unlike every accuracy read (ADR-0013): a completed study
    trial is the work the ladder asks for on a concept that is not yet answerable,
    and it is the *only* thing on offer for one in remediation. Excluding it would
    make the quota unpayable on precisely the days the loop most needs to keep
    running. It cannot be farmed — the ladder decides when a study trial is
    served, and a failed one pays nothing even with the solution on screen.
    """
    start, end = local_day_bounds(today or _local_today())
    sql = (
        "SELECT COUNT(*) AS n FROM interaction "
        "WHERE is_correct = 1 AND answered_at >= ? AND answered_at < ?"
    )
    params: list[object] = [start, end]
    if subject is not None:
        sql += " AND subject = ?"
        params.append(subject)
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return row["n"] if row else 0


def record_bail(today: date | None = None) -> None:
    """Spend one emergency bail, opening the gate for the rest of the local day."""
    day = (today or _local_today()).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO gate_bail (bailed_at, day) VALUES (?, ?)",
            (datetime.now(UTC).isoformat(), day),
        )


def bailed_today(today: date | None = None) -> bool:
    day = (today or _local_today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM gate_bail WHERE day = ?", (day,)
        ).fetchone()
    return bool(row and row["n"])


def record_raise(today: date | None = None) -> None:
    """Note that the gate came up today — it only ever raises once per local day."""
    day = (today or _local_today()).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO gate_raise (raised_at, day) VALUES (?, ?)",
            (datetime.now(UTC).isoformat(), day),
        )


def raised_today(today: date | None = None) -> bool:
    day = (today or _local_today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM gate_raise WHERE day = ?", (day,)
        ).fetchone()
    return bool(row and row["n"])


def reset_bails() -> int:
    """Wipe the bail history, restoring the full ration. Returns rows removed."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM gate_bail")
    return cur.rowcount


def count_bails_since(days: int, now: datetime | None = None) -> int:
    """Bails spent in the trailing `days` window — the ration the gate enforces."""
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM gate_bail WHERE bailed_at >= ?", (cutoff,)
        ).fetchone()
    return row["n"] if row else 0


def today_interactions(today: date | None = None) -> list[dict]:
    """Today's graded answers as (subject, is_correct, elapsed_ms) — quest fuel."""
    start, end = local_day_bounds(today or _local_today())
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT subject, is_correct, COALESCE(elapsed_ms, 0) AS elapsed_ms "
            "FROM interaction "
            "WHERE is_correct IS NOT NULL AND answered_at >= ? AND answered_at < ?",
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def claim_quest(day: str, quest_id: str, bonus_xp: int) -> bool:
    """Record a completed quest once; True only on the first claim."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO quest_log (day, quest_id, bonus_xp) VALUES (?, ?, ?)",
            (day, quest_id, bonus_xp),
        )
    return cur.rowcount > 0


def claimed_quests(day: str) -> set[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT quest_id FROM quest_log WHERE day = ?", (day,)
        ).fetchall()
    return {r["quest_id"] for r in rows}


def quest_bonus_xp() -> int:
    """Lifetime XP earned from completed daily quests."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(bonus_xp), 0) AS xp FROM quest_log"
        ).fetchone()
    return int(row["xp"]) if row else 0


def leeches() -> list[dict]:
    """Concepts repeatedly forgotten (lapses ≥ LEECH_LAPSES) — the costly few."""
    from engine.config import LEECH_LAPSES
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT cs.concept_id AS id, c.name AS name, c.subject AS subject, "
            "cs.lapses AS lapses FROM card_state cs JOIN concept c ON c.id = cs.concept_id "
            "WHERE cs.lapses >= ? ORDER BY cs.lapses DESC",
            (LEECH_LAPSES,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_lapses(concept_id: str) -> int:
    """How many times this concept has been forgotten after being learned."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT lapses FROM card_state WHERE concept_id = ?", (concept_id,)
        ).fetchone()
    return row["lapses"] if row else 0


def record_baselines(today: date | None = None) -> dict:
    """Prior bests to beat for live 'new record' pops, snapshotted per session.

    Unlike personal_bests (a display aggregate), best_day excludes today so the
    daily record fires once at the crossing. longest_run includes every logged
    run — nothing is in flight at snapshot time — and detect_records advances it
    in memory as runs end. Stamped with the local day so a session that crosses
    midnight can detect staleness (RecordTracker.refresh).
    """
    day = today or _local_today()
    best_day = max(_answers_per_local_day(exclude=day).values(), default=0)
    today = day.isoformat()
    with get_connection() as conn:
        fastest = conn.execute(
            "SELECT MIN(elapsed_ms) AS ms FROM interaction "
            "WHERE is_correct = 1 AND elapsed_ms > 0"
        ).fetchone()["ms"]
        seq = conn.execute(
            "SELECT is_correct FROM interaction WHERE is_correct IS NOT NULL ORDER BY id"
        ).fetchall()
    run = longest = 0
    for r in seq:
        run = run + 1 if r["is_correct"] else 0
        longest = max(longest, run)
    return {
        "day": today,
        "fastest_ms": fastest,
        "best_day": best_day or 0,
        "longest_run": longest,
        # Trailing consecutive-correct count at the end of the log: the run a new
        # session inherits, so a record run can span a session boundary.
        "current_run": run,
    }


def personal_bests() -> dict:
    """Fastest correct answer, best single day, and longest-ever correct run."""
    with get_connection() as conn:
        fastest = conn.execute(
            "SELECT MIN(elapsed_ms) AS ms FROM interaction "
            "WHERE is_correct = 1 AND elapsed_ms > 0"
        ).fetchone()["ms"]
        seq = conn.execute(
            "SELECT is_correct FROM interaction WHERE is_correct IS NOT NULL ORDER BY id"
        ).fetchall()
    run = best = 0
    for r in seq:
        run = run + 1 if r["is_correct"] else 0
        best = max(best, run)
    return {
        "fastest_ms": fastest,
        "best_day": max(_answers_per_local_day().values(), default=0),
        "longest_run": best,
    }


def due_count() -> int:
    """Concepts whose FSRS review is due now (the 'reviews waiting' open loop).

    Suppressed concepts don't count — a suspended card must not nag forever. The
    due rule itself lives in `availability.is_due`, shared with policy selection
    and dashboard readiness so the three can't drift.
    """
    from engine.scheduler.availability import is_due
    now = datetime.now(UTC)
    suppressed = suppressed_concept_ids()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT concept_id, reps, due FROM card_state "
            "WHERE reps > 0 AND due IS NOT NULL"
        ).fetchall()
    return sum(
        1 for r in rows
        if is_due(
            r["reps"], datetime.fromisoformat(r["due"]), now,
            r["concept_id"] in suppressed,
        )
    )


def graded_reviews() -> list[tuple[str, int, str, int]]:
    """Every graded interaction as (concept_id, grade, answered_at, elapsed_ms),
    oldest first — the raw material for fitting personal FSRS parameters.

    Drills are excluded. The optimizer infers stability from how long a card
    survived between *scheduled* reviews, so an off-schedule attempt on a card
    that was not due is not evidence it can read — feeding those in would teach
    the fit that intervals are far shorter than they are (ADR-0008).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, grade, answered_at, COALESCE(elapsed_ms, 0) AS ms
            FROM interaction
            WHERE grade IS NOT NULL AND answered_at IS NOT NULL
              AND (reason IS NULL OR reason != 'drill')
            ORDER BY answered_at
            """
        ).fetchall()
    return [(r["concept_id"], r["grade"], r["answered_at"], r["ms"]) for r in rows]


def get_interaction_history_timed(
    limit: int = 1000,
) -> list[tuple[str, bool, float]]:
    """Recent (concept_id, is_correct, time_days) across all subjects, oldest first.

    time_days is shown_at as days-since-epoch (falls back to sequence position),
    feeding the DKT model's recall-lag features. The interleaved global history is
    exactly the cross-domain sequence the model trains and predicts on.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, is_correct, shown_at FROM interaction
            WHERE is_correct IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    history: list[tuple[str, bool, float]] = []
    for position, row in enumerate(reversed(rows)):
        try:
            t = datetime.fromisoformat(row["shown_at"]).timestamp() / 86400.0
        except (ValueError, TypeError):
            t = float(position)
        history.append((row["concept_id"], bool(row["is_correct"]), t))
    return history
