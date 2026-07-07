# 1. Combo streak and record run are two distinct counts

Date: 2026-07-06

## Status

Accepted

## Context

The study loop tracks consecutive correct answers for two unrelated purposes:

1. **Combo tiers, variable-ratio reward, and best-this-session framing** — live
   session feedback. A new session should start with no combo; opening a fresh
   session already at "💎 Unstoppable" would be wrong.
2. **The longest-run personal best** — a record over the entire interaction log.
   If the learner ends a session on a correct answer and continues correctly in
   the next session, the true run spans that boundary.

The original code used a single per-session `streak` for both. Because that
`streak` resets to zero at session start, a record run that spanned a session
boundary folded short, so `longest_run` records were understated and a later,
shorter run could refire a stale record. Three consecutive code-review rounds
each fixed a fresh edge case in this area (stale baselines, `prev_run` fold,
midnight re-snapshot) without removing the underlying cause: one number was
being asked to mean two different things with different lifetimes.

## Decision

Model them as two named concepts with separate owners (see `CONTEXT.md`):

- **Combo streak** — session-local, held by the caller (the web `_Session` or the
  CLI loop), reset per session. Unchanged.
- **Record run** — log-wide, owned by a `RecordTracker`. `RecordTracker.snapshot()`
  seeds the current run from the log's trailing consecutive-correct count (already
  computed while scanning for baselines, so no extra query), increments it as
  answers settle, and folds it into `longest_run` when a run ends.

The shared `service.settle_answer` drives the tracker; the combo streak stays
purely presentational and never feeds record detection.

## Consequences

- A boundary-spanning correct run now sets `longest_run` truthfully; no stale
  refire.
- Combo tiers keep their correct per-session semantics.
- Record-run state has a single owner instead of a bare dict threaded through the
  API, CLI, DAO, and engagement module — the recurring source of the edge bugs.
- One more object (`RecordTracker`) and a wider snapshot payload (trailing run) to
  maintain. Judged worth it: the conflation cost three review rounds.
