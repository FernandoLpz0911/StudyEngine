# ADR-0014 — Readiness is unaided, or it is fiction

**Status:** accepted (2026-08-07)
**Amends:** ADR-0010, ADR-0012, ADR-0013

## Context

ADR-0013 introduced the teaching ladder and asserted that only `solo` attempts
would be measured. That assertion was **false as implemented**, in two separate
places, and the errors compounded.

**1. Retention was never filtered.** Readiness is `p_skill = accuracy × retention`.
`accuracy` was filtered to solo attempts; `retention` came straight from FSRS,
which resets its decay clock on *any* review — including a guided one. Measured
on the live database: eighteen `paired` concepts × six correct scaffolded answers,
with no unaided evidence whatsoever, moved the projected score **16.5 → 17.9**.
The identical hole sat in the rep-confidence term of `mastery`, which drives
resting, drill targeting and typed promotion.

The general failure: it is not enough to filter *the obvious factor*. A model is
unaided only if **every** factor is unaided, or it is "unaided except in the term
nobody is looking at".

**2. The guessing floor was counted twice.** `projection.py` documented its own
premise — *"practice is free response … so measured accuracy understates exam
accuracy"*. Free response was gated behind `TYPED_ANSWER_MASTERY = 0.55`, which
almost nothing reached while it mattered. So the entire 199-answer Exam P log was
four-option multiple choice: the 25% floor was already baked into `accuracy`, and
then `p_exam` added a five-option floor on top of it.

Backing the floor out of the observed rates:

```
last 20    observed 40%   ->  true unaided skill ~20%
last 50    observed 56%   ->  ~41%
all 199    observed 69%   ->  ~58%
```

Recent real ability was **half** what the system reported. The learner had also
noticed it from the inside — getting complex concepts right by accident, with no
way to say "I don't know".

**3. Time was being read as difficulty when it could not be.** ADR-0013 attached
worked examples to `paired` items, which advance FSRS. The answer clock starts
when the item loads, so *reading the example* counted as answering. On a threshold
already mis-tuned — 40% of correct answers graded Hard at 150s while still being
multiple choice — this would have shortened intervals on nearly everything,
recreating the review crowding ADR-0007 exists to prevent.

## Decision

**Readiness is unaided in every factor.** `accuracy` (solo only), `retention`
(decaying from `last_solo_review`, not from the last review of any kind), and
rep-confidence (`solo_reps`). A concept never answered unaided scores zero
retention rather than the 0.5 prior — the prior is for a card whose *stability* is
unknown, not for a learner who has never been tested.

**Generator problems are always free response.** No mastery threshold, no stage
exemption; `TYPED_ANSWER_MASTERY` is deleted rather than left as a dead lever.
The ladder is the support now, and it is a real one — options were a crude
substitute that let a learner reason backwards to an answer they could not
produce. Recall cards keep their options: a flashcard has no computed answer, so
typed grading would be string matching, and marking "BCNF" wrong against
"Boyce-Codd Normal Form" corrupts accuracy in the other direction.

**Historical rates are guessing-corrected, not discarded.** `interaction.choices_n`
records how many options were offered; `dao.deguess` applies
`(observed − ḡ) / (1 − ḡ)`. Discarding the multiple-choice history was tempting
and defensible — "you have never answered unaided, so there is no evidence" is
literally true, and it would have needed no correction factor to explain. It was
rejected because the log still carries real *triage* signal (`gp.independence` at
5 reps and 100% versus `mv.covariance` at 18 and 50%), and with 45 days to the
sitting, a week of the system not knowing where to point is a real cost. The
correction self-retires: ḡ is 0 for free response, so it shrinks to nothing as
real answers replace the old ones. No flag day.

**"I don't know" is a first-class answer.** It counts as a miss — it is one — but
it is *stronger* evidence than a wrong answer, which is ambiguous between a slip
and ignorance. So it demotes the concept a rung on its own, where a wrong answer
needs a run of three. It pays nothing toward quota directly, or a locked morning
has a ten-click exit; the `study` trial it earns pays, once the answer is
reproduced. That makes admitting ignorance the *fast* route to being taught and
never a route out of the day's work — which is what stops guessing from quietly
dominating it.

**Response time grades `solo` items only.** With a worked example on screen the
clock cannot distinguish reading from solving from copying, so a scaffolded item
grades on correctness alone. The solo thresholds move to 60s/300s for typed free
response against a real ~360s/question pace. `EXAM_TIMER_TARGET_S` remains the
pacing instrument; a grade threshold is an input to a difficulty model and makes a
poor whip.

**Promotion off the scaffold is the same comparison as demotion onto it** —
accuracy against the concept's own reach-scaled bar, measured at the rung it
stands on. The fixed streak it replaces ignored the bar entirely, releasing a
gateway on exactly the evidence that released a leaf: two correct guided answers
once graduated a concept with 0.64 unaided accuracy against a 0.92 requirement.

**Records are earned unaided.** A study trial has the answer on screen and is
answerable in two seconds, which would take the fastest-answer record permanently
and pad the record run. XP and the streak still flow from guided work — they are
the effort ledger, and effort was genuinely spent.

**Opening the explanation on a bare item is declared and costs.** The learner
reported reaching for it by habit mid-problem — which makes the problem easier
than the exam will be, while the answer goes into the log as unaided evidence. A
fourth silent inflation, and the only one the system had no way to see.

So it sits behind a confirmation that names the price, and `interaction.aided`
records the answer. An aided answer is excluded from every readiness read (which
is why the predicate is written once, as `dao.MEASURED`), carries no timing signal
to FSRS, sets no records, and forfeits its XP and combo. It still pays the quota
and still counts toward ascent, at the guided rung — the work was done, and the
day has to stay payable.

Client-reported, and therefore an honesty mechanism rather than an enforcement
one. That is the correct shape: the learner asked for the friction, and a
confirmation they must click past is what converts an unnoticed habit into a
decision. Nothing here can stop someone reading the theory in another tab, and
nothing should try.

**Ascent is a separate number, and guided work moves it.** See below.

## The two-number split

The learner's objection to all of this was correct and load-bearing: *"I need
guidance from time to time — don't build something that punishes me for taking
it."*

Making readiness honest does not remove one item of guidance; the ladder serves
the same things either way. But it exposed a real gap. One number was being asked
to answer two incompatible questions — *"would I pass on Sunday"* and *"am I
getting anywhere"* — and a single number asked both ends up saying the more
flattering one.

So there are two:

| | moved by | drives |
|---|---|---|
| **Projected score** | unaided evidence only | the readiness verdict |
| **Ascent** | guided work counts fully | display only |

Ascent is rung plus fraction toward leaving that rung, exam-weighted. It moves on
a hard guided day that graduates nothing, which is precisely the day the old
single number would have read zero on.

The property that keeps it from being a second flattering number: **on the top
rung the remaining climb *is* unaided accuracy against the bar**, so ascent
converges onto readiness exactly as the help stops being needed. They meet at the
top, and the gap between them is exactly how much of the learner's standing is
still propped up.

`mastery` stays on the readiness side, because everything it drives — resting,
drills, the map's node colouring — is a readiness question. A mastery that guided
reps inflated would rest a concept the learner can only do with help.

## Slogs

A leech costs repeated *attempts*. A **slog** costs *time*: a concept answered
correctly but always slowly, invisible to accuracy, FSRS and the projection, all
of which are indifferent to how long a right answer took. Two readings, because
the fixes differ — slow to *understand* (scaffolded rungs; the explanation is not
landing) versus slow to *solve* (unaided; the method is known but not fluent).
Relative to the subject's own median, since no constant works for both an ODE and
a flashcard.

**Diagnostic only.** It feeds no schedule, no accuracy, no projection, no
selection. It exists to tell the author where to fix a generator or rewrite a
`theory_md`.

Deliberately *not* folded into readiness. The obvious next step — model whether
questions get reached in time — was tested and rejected on the numbers: expected
160s/question weighted against a 360s budget, 80 minutes for a 30-question paper
against 180 available. Time is not the binding constraint, and modelling a
problem the data says does not exist would add one more input that can drift out
of true. Risk is *concentrated*, not general — three concepts run at or past the
per-question budget — which is exactly what a report catches and a model would
blur.

## Consequences

The projected score falls, immediately and substantially, and climbs back only on
unaided work. That is the correction, not a regression: the previous number was
inflated by scaffolded retention *and* by double-counted guessing, and a readiness
number that flatters is worse than none before a dated sitting (ADR-0010).

`mastery` for a concept in long remediation reads near zero and its map node stays
dark. Survivable now, because Ascent carries the progress reading; before the
split it would have been demoralising with nothing to offset it.

The whole 199-answer history is reinterpreted rather than replayed. Every accuracy
read now depends on `choices_n` being right, which is why the migration backfills
it to **4** and not 0 — a default of 0 would silently declare the entire history
uncontaminated, which is the exact overstatement the correction exists to remove.

ADR-0013's `PAIRED_PROMOTE_STREAK` and ADR-0010's `TYPED_ANSWER_MASTERY` are
retired. ADR-0012's guessing floor is unchanged and now correct — the sitting
really is five-option multiple choice, and the floor is applied exactly once, to
clean evidence.
