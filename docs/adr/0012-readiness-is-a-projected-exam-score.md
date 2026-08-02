# 12. Readiness is a projected exam score, not a count of mastered concepts

Date: 2026-08-02

## Status

Accepted

## Context

Readiness was "concepts at or above `MASTERY_THRESHOLD`". That threshold was never
calibrated against anything the exam decides, and the number turned out to be
actively misleading.

Simulating fifty days of study at ten correct answers a day ended with an
exam-weighted mean mastery of 0.815 — implying roughly 88% per-concept accuracy at
exam-time retention, on a paper whose pass mark is near 70%. The same run reported
**6 of 34 mastered**. A comfortable pass, reported as a failure.

Worse, the metric gave bad advice. Reading it, the recommendation was to drop ten
low-weight concepts so the remaining ones could be practised harder. Under a
projected score that change **costs about a mark**: a dropped concept does not
leave the paper, it becomes a guess. Taking a concept from 0.20 (blind guess) to
0.65 (thinly studied) gains more than taking one from 0.72 to 0.79, so breadth
beats depth precisely because the exam is multiple choice.

Two competing signals also can't share a readout. "6 mastered" next to "projected
23/30" invites the reader to believe the pessimistic one, which is the whole
failure repeating.

## Decision

Readiness is the raw score the learner would be expected to earn today.

- `p_skill = accuracy × retention`. Not mastery: mastery multiplies in a
  rep-confidence term that measures how much *evidence* exists, not how good the
  learner is, so including it marks a lightly practised concept down twice.
- `p_exam = p_skill + (1 − p_skill) × EXAM_GUESS_P`, five options, floor 0.2.
  Every concept contributes its exam-weight share of the paper, studied or not.
- Reported against `EXAM_PASS_MARK` with `EXAM_TARGET_MARGIN` on top, because the
  SOA scales to 0–10 and does not publish the raw cut, which moves between
  sittings.
- The gate carries `projected N/30 · pass ~21 · seen N/44`. The mastered count is
  removed; coverage stays, because it has a deadline the score cannot express.
- Drills rank by `exam_weight × (1 − p_exam)` — marks at stake — instead of lowest
  mastery, so effort and readout optimise the same quantity. Rotation still wins,
  so nothing gets massed.
- `concept_p_exam` is shared by the projection and by drill targeting, so the
  number reported and the number acted on cannot drift apart.

Mastery is unchanged and keeps its jobs: resting, the dashboard, and the
per-concept diagnosis.

## Consequences

- The headline number falls sharply and honestly. The real database projects
  **14.1/30** today, because 25 of 44 concepts are unseen and contribute only the
  guessing floor. The old readout showed "1/44 mastered", which was true and
  useless; this says how far from passing the learner actually is.
- `exam_weight` becomes load-bearing. It only broke ties before; now it sets each
  concept's share of the paper *and* drill priority. General Probability was
  raised from 18.2% to 20.9% to sit inside its syllabus band — the other two
  categories were already inside theirs.
- The projection is only as good as `EXAM_QUESTIONS`, `EXAM_PASS_MARK` and the
  weights. The pass mark in particular is an estimate of an unpublished number,
  which is why it is config and why the readout states it rather than hiding it.
- Two known biases, both conservative. Practice is free response well below the
  mastery at which the real exam still offers five options, so measured accuracy
  understates exam accuracy; and retention is read at "now" rather than exam day,
  which the taper (ADR-0009) is separately arranging to be high.
- It can now answer "am I done", which a threshold count never could.
