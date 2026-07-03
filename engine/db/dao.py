"""Data-access layer — all SQLite reads/writes go through here."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

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
            "i.subject FROM interaction i "
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
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE session SET ended_at = ? WHERE id = ?", (now, session_id))


def log_shown(
    session_id: int,
    concept_id: str,
    subject: str,
    kind: str,
    seed: int = 0,
    params_json: str = "{}",
    correct_answer: str | None = None,
) -> int:
    """Record that a problem/card was served. Returns the interaction id."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO interaction
                (session_id, concept_id, subject, kind, seed, params_json,
                 correct_answer, shown_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, concept_id, subject, kind, seed, params_json, correct_answer, now),
        )
        return cur.lastrowid


def log_answered(
    item_id: int,
    user_answer: str | None,
    is_correct: bool | None,
    grade: int,
    elapsed_ms: int = 0,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE interaction
            SET user_answer = ?, is_correct = ?, grade = ?,
                elapsed_ms = ?, answered_at = ?
            WHERE id = ?
            """,
            (
                user_answer,
                int(is_correct) if is_correct is not None else None,
                grade,
                elapsed_ms,
                now,
                item_id,
            ),
        )


def get_concept_accuracy(concept_id: str, window: int = 10) -> float | None:
    """Recent fraction-correct for a concept over its last `window` graded items."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT is_correct FROM interaction
            WHERE concept_id = ? AND is_correct IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (concept_id, window),
        ).fetchall()
    if not rows:
        return None
    return sum(r["is_correct"] for r in rows) / len(rows)


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
    """'Not today' — hidden until the next local day, then back automatically."""
    now = datetime.now(UTC).isoformat()
    until = (_local_today() + timedelta(days=1)).isoformat()
    with get_connection() as conn:
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


def count_new_concepts_today(today: date | None = None) -> int:
    """Concepts first shown on the current local day (drives the new-per-day cap)."""
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM ("
            "  SELECT concept_id, MIN(shown_at) AS first_shown FROM interaction"
            "  GROUP BY concept_id"
            ") WHERE date(first_shown, ?) = ?",
            (_tz_modifier(), today),
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
    """Distinct UTC dates on which any item was answered, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date(answered_at, ?) AS d FROM interaction "
            "WHERE answered_at IS NOT NULL ORDER BY d DESC",
            (_tz_modifier(),),
        ).fetchall()
    out: list[date] = []
    for row in rows:
        try:
            out.append(date.fromisoformat(row["d"]))
        except (ValueError, TypeError):
            continue
    return out


def _tz_modifier() -> str:
    """SQLite datetime modifier shifting UTC to the configured local day boundary."""
    from engine.config import STREAK_TZ_OFFSET
    return f"{STREAK_TZ_OFFSET:+g} hours"


def _local_today() -> date:
    from engine.config import STREAK_TZ_OFFSET
    return (datetime.now(UTC) + timedelta(hours=STREAK_TZ_OFFSET)).date()


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
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at IS NOT NULL AND date(answered_at, ?) = ?",
            (_tz_modifier(), today),
        ).fetchone()
    return row["n"] if row else 0


def today_interactions(today: date | None = None) -> list[dict]:
    """Today's graded answers as (subject, is_correct, elapsed_ms) — quest fuel."""
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT subject, is_correct, COALESCE(elapsed_ms, 0) AS elapsed_ms "
            "FROM interaction "
            "WHERE is_correct IS NOT NULL AND date(answered_at, ?) = ?",
            (_tz_modifier(), today),
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
    """Prior bests to beat for live 'new record' pops — excluding what's in flight.

    Unlike personal_bests (a display aggregate), each baseline excludes the thing
    currently being extended, so a record fires once at the crossing instead of on
    every subsequent answer: best_day ignores today, longest_run ignores the
    still-running trailing streak. fastest_ms is naturally self-limiting.
    """
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        fastest = conn.execute(
            "SELECT MIN(elapsed_ms) AS ms FROM interaction "
            "WHERE is_correct = 1 AND elapsed_ms > 0"
        ).fetchone()["ms"]
        best_day = conn.execute(
            "SELECT MAX(n) AS m FROM (SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at IS NOT NULL AND date(answered_at, ?) != ? "
            "GROUP BY date(answered_at, ?))",
            (_tz_modifier(), today, _tz_modifier()),
        ).fetchone()["m"]
        seq = conn.execute(
            "SELECT is_correct FROM interaction WHERE is_correct IS NOT NULL ORDER BY id"
        ).fetchall()
    # Longest completed run, excluding the trailing run still in progress (it is
    # the run the learner may be extending right now).
    runs: list[int] = []
    run = 0
    for r in seq:
        if r["is_correct"]:
            run += 1
        else:
            if run:
                runs.append(run)
            run = 0
    longest = max(runs) if runs else 0
    return {
        "fastest_ms": fastest,
        "best_day": best_day or 0,
        "longest_run": longest,
    }


def personal_bests() -> dict:
    """Fastest correct answer, best single day, and longest-ever correct run."""
    with get_connection() as conn:
        fastest = conn.execute(
            "SELECT MIN(elapsed_ms) AS ms FROM interaction "
            "WHERE is_correct = 1 AND elapsed_ms > 0"
        ).fetchone()["ms"]
        best_day = conn.execute(
            "SELECT MAX(n) AS m FROM (SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at IS NOT NULL GROUP BY date(answered_at, ?))",
            (_tz_modifier(),),
        ).fetchone()["m"]
        seq = conn.execute(
            "SELECT is_correct FROM interaction WHERE is_correct IS NOT NULL ORDER BY id"
        ).fetchall()
    run = best = 0
    for r in seq:
        run = run + 1 if r["is_correct"] else 0
        best = max(best, run)
    return {
        "fastest_ms": fastest,
        "best_day": best_day or 0,
        "longest_run": best,
    }


def due_count() -> int:
    """Concepts whose FSRS review is due now (the 'reviews waiting' open loop).

    Suppressed concepts don't count — a suspended card must not nag forever.
    """
    now = datetime.now(UTC).isoformat()
    today = _local_today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM card_state cs "
            "WHERE cs.reps > 0 AND cs.due IS NOT NULL AND cs.due <= ? "
            "AND NOT EXISTS (SELECT 1 FROM concept_suppression s "
            "  WHERE s.concept_id = cs.concept_id AND (s.until IS NULL OR s.until > ?))",
            (now, today),
        ).fetchone()
    return row["n"] if row else 0


def graded_reviews() -> list[tuple[str, int, str, int]]:
    """Every graded interaction as (concept_id, grade, answered_at, elapsed_ms),
    oldest first — the raw material for fitting personal FSRS parameters."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, grade, answered_at, COALESCE(elapsed_ms, 0) AS ms
            FROM interaction
            WHERE grade IS NOT NULL AND answered_at IS NOT NULL
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
