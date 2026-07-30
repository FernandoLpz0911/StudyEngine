# 7. Coverage is paced by its own deadline, not by what reviews leave over

Date: 2026-07-29

## Status

Accepted

## Context

Selection served overdue reviews strictly before the frontier: `if overdue:
return` was reached before the frontier was ever consulted. With
`EARLY_REINFORCEMENT_REPS` capping the first intervals at a day, every seen
concept is due again the next morning, so the review queue is never empty and the
frontier was never reached at all.

The effect was invisible because nothing failed. Exam P sat at 16 of 44 concepts
seen with `new_per_day = 8` entirely unspent, and 0 new concepts introduced on a
day with 31 answers. The learner would have sat the exam having never once seen
Normal, Poisson, Binomial, or the Central Limit Theorem, while the dashboard
reported steadily improving mastery of the sixteen concepts they *had* met.

Coverage and mastery fail differently. Mastery degrades gracefully — a concept at
0.6 on exam day is worth something. Coverage does not: a concept never introduced
is worth nothing, and it cannot be repaired late, because a first exposure in the
final week can only be crammed. Coverage is therefore the part of readiness with a
genuine deadline, and it was the part with no schedule.

## Decision

Introductions get a deadline of their own and a daily quota derived from it.

- The coverage deadline is `exam_date - CONSOLIDATION_DAYS` (default 40), derived
  rather than configured. A separate date would be one more thing to keep in sync
  and would silently contradict the exam date as soon as a sitting moved.
- Today's share is `ceil(unseen / days_to_deadline)`, bounded by `new_per_day`.
  Owed introductions are served *before* reviews; once the share is paid, the
  ordinary reviews-first order resumes.
- The deadline is a ceiling as well as a floor. A subject with an exam date does
  not race ahead into the `new_per_day` cap on a quiet day — see Consequences.
- The frontier is ranked by transitive downstream reach, then exam weight.

Subjects with no exam date are unchanged: no owed introductions, and the frontier
still opens freely whenever nothing is due.

## Consequences

- The quota is self-correcting without tracking a debt. The divisor shrinks each
  day, so a skipped day raises tomorrow's share on its own, and the whole
  mechanism returns zero and disappears once coverage is complete.
- Pacing in both directions is the surprising half. Once the day's supply of
  reviews runs dry — which now happens routinely, see ADR-0008 — the old frontier
  rule would introduce up to `new_per_day` concepts, finishing coverage in about
  four days instead of fourteen. That is the review flood `new_per_day` exists to
  prevent, and it would leave a wall of first exposures all maturing together. A
  subject with an exam date is therefore held to the deadline's pace.
- Ranking on reach rather than weight alone is what makes the deep layers
  reachable in time. On Exam P every weight-3 concept (Normal, Poisson,
  Exponential, CLT) is prerequisite-locked behind weight-1 and weight-2 ones, so
  ranking on weight alone strands the gateways and pushes CLT to the final day of
  the coverage window. Reach puts *Higher moments* (8 dependents) and
  *Transformations of a random variable* (7) first instead.
- `_intro_owed` is consulted on every item served, so it is deliberately cheap:
  three queries and no mastery computation. `subject_pace` is the richer read,
  used only for display.
