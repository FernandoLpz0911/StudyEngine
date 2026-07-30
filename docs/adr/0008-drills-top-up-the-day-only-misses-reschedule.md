# 8. Drills top up the day; only a missed drill reschedules

Date: 2026-07-29

## Status

Accepted

## Context

The supply of items that can pay the gate quota is the day's due reviews plus the
retry queue. Answering correctly *removes* an item from that supply; only a wrong
answer regenerates one, via the retry debt.

So a good day is the dangerous one. With 14 concepts due and a quota of 20
correct, answering all 14 right first time leaves `select_next` returning `None`
at 14/20, with nothing left to answer and the desktop still locked. Perfect
performance strands the learner behind their own gate, and the only exits are the
rationed bail (ADR-0004) or the TTY. The existing day only worked because 11 of 31
answers were wrong.

`new_per_day` was the accidental slack absorbing this, which is a bad job for it:
it runs out precisely once coverage is complete, which is when the shortfall gets
worse, and spending it here fights the coverage pacing of ADR-0007.

## Decision

When due reviews and owed introductions are exhausted and the quota is still
unpaid, serve **drills**: extra reps of the lowest-mastery concepts on fresh
seeds. Drills are logged with `reason = "drill"` and pay the quota like any other
correct answer.

Drills update FSRS **asymmetrically**:

- A **correct** drill leaves card state entirely alone — no rating, no interval
  change, no rep.
- A **missed** drill applies `Again`: stability crashes, the review is pulled
  forward, `lapses` increments. It does **not** advance `reps`.

Drills are excluded from `graded_reviews()`, the input to the personal FSRS
weight fit. They rotate on a least-drilled-today-first key, weakest concept
breaking the tie.

Only the gated subject drills, and only while its quota is unpaid. An ungated
session that runs out of material has simply finished.

## Consequences

- The quota is payable by construction. Simulated against the real log, a day now
  costs 20 answers at 100% accuracy, 22 at 85%, 24 at 73%, 26 at 60% — and never
  strands.
- Drills aim at the lowest measured mastery, which is also the highest-value
  practice available: on Exam P that is Covariance and Correlation at 0.50
  accuracy, the concepts actually holding readiness down.
- The asymmetry biases stored stability *downward*, so slightly more reviews are
  scheduled than FSRS considers optimal. Accepted deliberately: before a dated
  exam, over-reviewing costs time already committed, while under-reviewing costs
  a concept on the day. Symmetric updates were the alternative, and were rejected
  because `apply_rating` advances `reps` unconditionally, and `reps` is the
  confidence term in the mastery score — drills would inflate the very number the
  exam target is defined against.
- Not advancing `reps` on a miss avoids the perverse converse: failing a drill
  must not raise rep-confidence.
- Rotation is load-bearing, not polish. A correct drill leaves mastery unmoved, so
  "the weakest concept" is a fixed point: without rotation the first
  implementation served one concept fifteen times in a row, which is massed
  practice — the opposite of what the rest of the system is for.
- Excluding drills from the weight fit matters independently of the asymmetry.
  The optimizer infers stability from survival between *scheduled* reviews, and a
  drill is by definition off-schedule, on a card that was not due.
- Near-term re-testing of a miss does not depend on any of this: the retry queue
  (`RETRY_GAP`, and `pending_retry` across sessions) already handles it. The FSRS
  lapse is what makes the correction outlive the day.
