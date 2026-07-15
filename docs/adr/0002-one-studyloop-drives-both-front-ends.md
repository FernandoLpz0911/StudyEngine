# 2. One StudyLoop drives both front ends

Date: 2026-07-14

## Status

Accepted

## Context

The interleaved study loop — retry-drain first, DKT re-prediction every 5 items,
warmup/stall/cooldown pacing between confidence and weak selection, then a
force-drain of pending re-tests before the session ends — was implemented twice:
once in `api.next_item` (one HTTP request at a time) and once in
`cli.study.run_global` (a straight `for` loop). The api.py docstring admitted it:
"reproduces the global study loop one request at a time." The `% 5` cadence, the
warmup gate, and the `recent[-2:] == [False, False]` stall rule were copy-pasted
magic constants living in two files, already drifting: the CLI had an end-of-
session cooldown and an `i > 0` DKT guard the API lacked; the API folded session
XP the CLI didn't.

`service.settle_answer` was introduced to stop *settlement* drift, but drew its
seam in the wrong place. Its docstring says it "owns the shared write sequence so
the two front ends can never drift," yet it deliberately excludes "caller-owned
state (the retry queue, the recent list, the XP total)" — so the in-session retry
re-append, `recent.append`, streak fold, and `xp_session +=` were duplicated
verbatim in both callers. The one `Settle` concept was physically half-in-service,
half-in-each-front-end. Worse, `settle_answer` also *computed* streak/combo/reward/
XP, none of which appear in the `CONTEXT.md` definition of Settle — session-local
framing had leaked into the log-wide write path.

A third symptom: `api._rebuild_session` replays `session_results` to recompute
streak/best/XP with a second copy of the same fold, so a server restart could
silently change the learner's streak or XP if the two encodings drifted.

The root cause was the same each time: the **turn** — select, serve, settle — and
the session-local state it advances had no owner, so both front ends re-derived it.

## Decision

Introduce a single deep module `engine/loop.py` with a `StudyLoop` class that owns
all session-local state and drives one **Turn** at a time behind two methods (see
`CONTEXT.md` for **StudyLoop** and **Turn**):

- `StudyLoop.start(scope, n)` / `StudyLoop.rebuild(session_id)` — construct fresh
  or replay the log through the *same* session-local fold used incrementally, so
  the rebuild path can no longer diverge from the live path.
- `next() -> Turn | Done` — selects, builds, logs, increments the index, and
  stores the `item_id -> item` map (so the web API's `GET next` / `POST answer`
  round-trip resolves against the loop). Owns warmup/stall/cooldown pacing, the
  DKT `% 5` refresh, retry-drain, and `dao.close_session` on `Done`.
- `settle(item_id, raw, elapsed) -> Outcome` — calls `service.settle_answer` for
  the log-wide Settle, then folds the session-local delta (retry re-append,
  recent, streak, best, session XP, last subject).

Bounded (CLI, fixed `n` with a cooldown) and open-ended (API, ends on nothing-due)
are reconciled by a single optional budget: `n: int | None`. Cooldown fires only
when `n` is known; `n=None` disables it. The pacing rule lives once, inside the
loop.

`service.settle_answer` shrinks to the canonical Settle (`CONTEXT.md`): grade, log,
FSRS, quests, retry debt, record detection, and item-level feedback — no session
state. The two front ends keep only transport and rendering: the API keeps its
in-memory session registry (now holding `StudyLoop` instances) and JSON/latexify;
the CLI keeps stdout and input.

## Consequences

- The interleaving, pacing, DKT cadence, retry-drain, and settlement fold have one
  owner; the two front ends can no longer drift. Kills the duplicated global loop
  (api ⟷ cli), the leaky `settle_answer` seam, the DKT threading copy, and the
  rebuild re-derivation of streak/XP.
- The loop becomes directly testable: `loop = StudyLoop.start("global", 5);
  loop.next(); loop.settle(...)` — no `TestClient`, no stdin. Existing HTTP and
  session-resume tests stay as integration guards; new unit tests target the loop.
- CLI cooldown, rebuild semantics, and retry spacing are preserved exactly; the
  minor prior divergences (DKT `i > 0` guard, session-XP fold) are unified to the
  correct behavior.
- One more module and a wider constructor surface (`start`/`rebuild`). Judged worth
  it: the conflation was one HIGHEST- and one Strong-severity friction, and the
  drift it caused was already live.
