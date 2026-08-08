# ADR-0013 — A test-only loop teaches nothing, so items are staged

**Status:** accepted (2026-08-07), amended same day by
[ADR-0014](./0014-readiness-is-unaided-or-it-is-fiction.md)

> **Amendments.** The ladder stands; three of the rules below did not survive
> first contact with the data.
>
> - Decision 2's claim that "only `solo` attempts are measured" was **not true as
>   implemented** — `retention` and rep-confidence were never filtered, and guided
>   answers moved the projected score by +1.4 marks. Fixed in ADR-0014.
> - Decision 4's promotion rule (a fixed `PAIRED_PROMOTE_STREAK`) ignored the
>   concept's own bar and released gateways far too cheaply. Replaced by the same
>   accuracy-against-bar comparison used for demotion.
> - Decision 1's premise that options make a scaffolded item gradable is retired:
>   generator problems are now always free response, and the ladder — not a list
>   of choices — is the support.

## Context

The study loop was: select a concept, serve a bare problem, grade it, optionally
show the worked solution, move on. There was no step in it that *taught*. The
only response to a miss was another attempt at the same concept.

The live log said what that produces. On Exam P, over 199 answers:

| concept | reps | FSRS stability |
|---|---|---|
| `mv.covariance` | 18 | **0.0** |
| `uv.variance` | 18 | 0.5 |
| `gp.counting_prob` | 14 | 0.1 |
| `mv.conditional_expectation` | 14 | 0.2 |
| — | | |
| `gp.independence` | 5 | 110.1 |
| `mv.marginal` | 7 | 51.9 |

Eighteen attempts leaving stability at 0.0 is eighteen answers that taught
nothing. Every one was a coin flip, every miss crashed the interval back under a
day, and the concept returned the next morning to be flipped again. Concepts that
were actually understood got there in five reps. The bottom group is not being
learned slowly — it is not being learned at all.

Accuracy confirmed it: 69% lifetime, 56% over the last 50, **40% over the last
20**. Falling, while the coverage deadline kept introducing three new concepts a
day. And because the gate's quota is denominated in *correct* answers, 40%
accuracy silently doubled the day's cost — ten correct at five minutes an answer
became two hours, which is why days ended in a bail rather than a paid quota.

A retrieval loop is the right thing for material that can be retrieved. Run on
material that cannot, it degenerates into surface pattern-matching: the learner
recognises the shape of a problem and reaches for the formula that usually goes
with it, which is exactly the "memorising, not understanding" complaint.

## Decision

**1. An item is served at one of three teaching stages, derived from the log.**

- `study` — the worked solution is shown *first*; the learner works through it
  and reproduces the answer. This is the teaching trial.
- `paired` — a fully solved *sibling* problem is shown (same generator, different
  seed), then a fresh instance is solved unaided.
- `solo` — the bare problem. What the loop used to do exclusively.

Derived, not stored, for the same reason resting is (`availability.is_rested`): a
stored flag must be maintained and goes stale the moment the evidence moves.

A sibling rather than the same numbers at `paired` matters — an example whose
answer *is* the answer being asked for teaches copying; one that shares only the
method teaches the method.

**2. Only `solo` attempts are measured.** `get_concept_accuracy` and
`recent_accuracy` filter on stage. This is load-bearing, not bookkeeping: accuracy
feeds mastery, drill targeting, resting, the frontier, and the projected exam
score. Counting scaffolded answers would inflate every readiness signal at once,
and the learner would walk into the sitting trusting a number that measured their
ability to copy a solution. A ladder that lies about readiness is worse than the
treadmill it replaced.

Study trials additionally never reach FSRS: with the solution on screen, neither
outcome is evidence about recall.

**3. A stuck concept is remediated, not re-tested.** Two independent triggers,
because they catch different failures — a run of consecutive misses (acute: the
concept is not available right now, and a fourth attempt will not make it
available), or many reps whose stability never leaves the floor (chronic: the
treadmill above). Reps alone are not enough; a concept can legitimately need many
reviews.

**4. The bar scales with downstream reach.** A foundation carries everything
above it: shaky conditional probability does not cost its own marks, it costs
Bayes, conditional expectation, and double expectation too. So the accuracy a
concept must clear is `ACCURACY_FLOOR + PREREQ_ACCURACY_BONUS × min(1, reach/4)`
— 0.80 for a leaf, 0.92 for a gateway. Saturating, because past a handful of
dependents a concept is already foundational and an unbounded ramp would demand
accuracy no honest measurement reaches. Reach is the number the frontier is
already ordered by, so no new graph analysis is introduced.

**5. Introductions stop below the accuracy floor.** The mirror of
`AHEAD_ACCURACY` — same evidence, read as a floor rather than a ceiling.
Introducing a concept to a learner answering at 40% widens the surface of the
same guessing, and the marks lost to the crowding outweigh what a first exposure
adds.

**6. …but the coverage backstop overrides it.** Coverage is the one part of
readiness that cannot be repaired late (ADR-0007). Held indefinitely, the floor
would strand unseen material at the guessing floor forever for a learner whose
accuracy never recovers. So the floor yields inside `COVERAGE_BACKSTOP_DAYS` of
the coverage deadline.

**7. A miss is repaired at its prerequisite, depth one.** If some prerequisite is
*weaker* than the concept that just missed, it is queued first. Depth one only:
following the chain down walks the session away from what the exam asks about,
and the prerequisite's own miss opens the next step down by itself if it really
is the problem. If the foundation is the stronger of the two, the miss belongs to
the concept and the detour teaches nothing.

**8. A miss asks which step broke.** Self-explanation, answered by picking a
numbered step of the worked solution, and the advance is held until it is
answered — a prompt you can click past trains clicking past it. It is also the
only record of *where* a concept fails rather than that it failed: misses that
cluster on one step need that step taught, misses that scatter need the concept
re-taught.

**9. Study trials pay the gate's quota.** `count_correct_today` stays unfiltered
by stage. A completed study trial is the work the ladder asks for on a concept
that is not yet answerable, and it is the *only* thing on offer for one in
remediation — excluding it would make the quota unpayable on precisely the days
the loop most needs to keep running. It cannot be farmed: the ladder decides when
a study trial is served, and a failed one pays nothing even with the solution up.

## Consequences

Applied to the live Exam P database, the five treadmill concepts above route to
`study`, the high-reach foundations (`gp.set_theory` reach 42, `gp.axioms` reach
41, `uv.rv_basics` reach 36) are held to 0.92 and drop to `paired`, and the four
concepts with real stability stay `solo`. The ladder demotes what is not working
and leaves alone what is.

Measured accuracy will *fall* at first and the projected score with it. That is
the point: the old number counted answers that had a worked solution in the
learner's recent memory, and the new one does not. A readiness number that
flatters is worse than no number at all before a dated sitting (ADR-0010).

Sessions get slower per item — an example to read, a step to name. Volume is an
output, not a lever (ADR-0010), and the quota being payable by study trials is
what keeps a low-accuracy day from becoming a two-hour grind that ends in a bail.

The accuracy floor currently has no effect on `examp`: its coverage deadline is
five days out, so the backstop carries introductions regardless. The floor binds
for subjects with distant deadlines, and for `examp` once coverage completes —
at which point there is nothing left to introduce anyway.
