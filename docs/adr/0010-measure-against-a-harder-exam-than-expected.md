# 10. Measure against a harder exam than the one expected

Date: 2026-07-29

## Status

Accepted

## Context

Simulating the 54 days to the Exam P sitting produced two outcomes that differ by
one variable. With per-concept accuracy improving as material is practised, the
existing settings reach the mastery target on 42 of 44 concepts at a median 24
questions a day. With accuracy flat, the same settings reach 5 of 44 — and the
day costs a median of 41 questions rather than 24.

That second number is the important one, and not because of the grind. Since the
quota is denominated in *correct* answers (ADR-0005), low accuracy already raises
the day's question count on its own: 20 correct cost 41 questions without a single
setting being changed. **Daily volume is therefore not a lever worth pulling by
hand** — it is an output, not an input. Accuracy per concept is the only binding
constraint, and the way to move it is to make each question test more.

Meanwhile the calibration was soft in three places. `TYPED_ANSWER_MASTERY` at 0.75
meant nearly everything was served as multiple choice, where four numeric options
can often be reasoned backwards from by someone who could not produce the answer.
`MASTERY_TARGET_REPS` at 3 meant the confidence term saturated after three correct
reviews, so a barely-established concept read as fully confident. And
`MASTERY_THRESHOLD` at 0.8 set the bar below where a hard sitting would want it.

## Decision

Calibrate for a harder exam than the one expected.

- `TYPED_ANSWER_MASTERY` 0.75 → **0.55**. Free response starts much earlier. The
  real sitting is five-option multiple choice, so typing the answer is strictly
  harder than the exam.
- `MASTERY_TARGET_REPS` 3 → **6**. Confidence saturates slower.
- `MASTERY_THRESHOLD` 0.8 → **0.85**.
- `GRADE_FAST_MS_GEN` 25s → **30s**, `GRADE_SLOW_MS_GEN` 90s → **150s**.
- `TYPED_REL_TOLERANCE` 0.5% → **1%**.

`EXAM_PEAK_RETENTION` is deliberately *not* raised — see ADR-0009.

## Consequences

- The mastery number drops immediately and sharply: Exam P went from 4 of 44
  "mastered" to 1 of 44 on identical knowledge. Nothing regressed; the previous
  number was measuring a softer thing. A readiness figure that flatters is worse
  than useless before a dated exam.
- The two headline changes partially oppose each other, and the numbers were
  picked knowing it. More target reps *lowers* mastery, and the free-response
  switch triggers *on* mastery, so raising reps delays typed answers. At 0.55 and
  6 reps a five-rep concept at 90% accuracy still lands near 0.67 and is typed.
- Widening the timing thresholds is a consequence of the typed switch, not an
  independent softening. Producing and typing a worked numeric answer takes far
  longer than picking an option; left at 90s almost every typed answer would grade
  Hard, shortening intervals on evidence that is really about typing speed.
- Loosening the typed tolerance to 1% likewise buys rigor rather than spending it.
  The key is rounded to three decimals, so at 0.5% a correctly solved 0.4237 keyed
  as 0.424 marks a learner's 0.42 wrong. Penalising rounding costs a quota answer
  and teaches nothing.
- These are global config defaults, so every subject gets the stricter reading,
  not just the gated one. Accepted: the softness was never specific to Exam P.
