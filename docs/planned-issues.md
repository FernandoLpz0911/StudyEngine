# Structural-debt cleanup — issue drafts

Outcome of the grilling session (2026-07-06). Resolves the recurring
record/session edge-bug class the last three code-review rounds each re-found.
See `CONTEXT.md` (glossary) and `docs/adr/0001-two-runs-combo-vs-record.md`.

Order matters: #1 → #2 depend in sequence; #3–#6 are independent.

---

## Issue 1 — RecordTracker owns the log-wide record run

**Labels:** refactor, correctness

Records currently ride the per-session `streak`, which resets at session start,
so a correct run spanning a session boundary folds short and `longest_run`
records lie (round-3 finding #3).

- Add `RecordTracker` (in `engine/engagement.py`): holds baselines
  (`fastest_ms`, `best_day`, `longest_run`) **and** the current record run.
- `RecordTracker.snapshot()` seeds the current run from the log's trailing
  consecutive-correct count — already computed while `dao.record_baselines`
  scans the is_correct sequence; widen that return, no new query.
- `tracker.detect(correct, elapsed_ms, answered_today_before) -> list[str]`
  increments/folds its own run; replaces the free `detect_records` +
  `prev_run`/`run_length` args.
- Day-rollover re-snapshot (`ensure_fresh_baselines`) becomes `tracker.refresh()`.
- Combo streak stays caller-local and never feeds records.

**Done when:** `test_records.py` covers a boundary-spanning run setting
`longest_run` correctly; no caller passes `prev_run` for records.

---

## Issue 2 — Shared `service.settle_answer` collapses the two answer paths

**Labels:** refactor, correctness
**Depends on:** #1

`api.submit_answer` and `cli._run_item` duplicate the full settle sequence and
have already drifted in ordering (`ensure_fresh_baselines`/`detect_records`
before vs after FSRS save) — round-3 finding #2.

- Add `service.settle_answer(item, raw_answer, elapsed_ms, tracker, streak_in)
  -> AnswerOutcome`.
- Owns: grade, `count_answered_today` + `log_answered`, `tracker.refresh()` +
  `tracker.detect(...)`, FSRS `apply_rating`/`save` + `next_review_days`,
  `quests.settle()`, pending-retry DB add/remove, streak/best math, and the
  combo/reward/combo_break strings.
- Returns an `AnswerOutcome` dataclass; caller does **not** get: in-session
  `retry_queue` append (index differs per caller), `recent`/`last_subject`/
  `xp_session` accumulation, or presentation (JSON vs print).
- One write-order, defined once — ordering can no longer drift.

**Done when:** both callers render from `AnswerOutcome`; no settle step is
written twice.

---

## Issue 3 — Deduplicate the retry-queue popper

**Labels:** refactor

`_pop_retry` is near-identical in `api.py` and `cli/study.py` (suppression skip,
force/index gate, pop) — round-3 finding #4.

- Extract `service.next_retry(retry_queue, index, force) -> Concept | None`.
- api wraps the return in `policy.Selection(concept, "retry")`; cli uses it
  directly. Suppression-skip logic lives once.

---

## Issue 4 — Session lifecycle: pop on close + idempotent close

**Labels:** correctness

`next_item` done-path calls `dao.close_session` but leaves the session in
`_sessions`; `_get_or_rebuild` only checks `ended_at` on the rebuild path, so a
resident session keeps serving/logging after close on a long-running server —
round-3 finding #1.

- Done-path: `dao.close_session(id)` then `_sessions.pop(id, None)`.
- `dao.close_session` gets `WHERE ended_at IS NULL` (idempotent — a re-close
  can't overwrite the original timestamp; also hardens the CLI double-close).

**Done when:** `test_session_resume.py` asserts a resident session 404s after
its done-summary without a restart.

---

## Issue 5 — Quests: shared `_evaluate` core, kill the double query

**Labels:** refactor, efficiency

`settle()` queries `claimed_quests(day)` then calls `todays_quests()` which
queries it again; until all 3 quests are claimed every answer re-scans the day —
round-3 finding #6.

- Extract pure `_evaluate(rows, day, claimed, daily_goal) -> list[dict]` (banks
  + returns).
- `settle()` fetches `claimed` + `today_interactions()` once, early-outs, calls
  the core. `todays_quests()` (endpoint) calls the same core.
- Keep the log-derived progress invariant — do **not** add in-memory counters.

---

## Issue 6 — Settings: single range helper

**Labels:** refactor

`settings._get` (clamp) and `set_value` (validate) duplicate the `(lo, hi)`
range logic — round-3 finding #8.

- Extract `_in_range(value, bounds) -> bool`; both call it.

---

## Explicitly not doing

- **Quest `progress` lambdas** (round-3 finding #7): kept. Laziness is
  load-bearing — `clean_queue`'s `due_count()` runs only when that quest is
  drawn. Eager eval would query every day.
