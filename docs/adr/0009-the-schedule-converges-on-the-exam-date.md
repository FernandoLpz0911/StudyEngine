# 9. The schedule converges on the exam date

Date: 2026-07-29

## Status

Accepted

## Context

FSRS optimises for indefinite retention and knows nothing about a sitting. Left
alone it will schedule a concept's next review for after the exam — an interval
that is correct for remembering the material next year and useless for
remembering it in September. A card due after the exam is, for this purpose, a
card that is never reviewed again.

The mastery score compounds this. `mastery = accuracy × retention × confidence`,
with retention read at the moment of measurement. Since FSRS holds retention at
`TARGET_RETENTION` (0.90), the ceiling on any concept's mastery is `0.90 ×
accuracy` — so an all-concepts-at-0.8 target silently demands ~89% sustained
accuracy per concept, and a concept reviewed in August genuinely reads worse in
September even if nothing was forgotten.

## Decision

The schedule tapers toward the exam.

- `desired_retention` ramps linearly from `TARGET_RETENTION` to
  `EXAM_PEAK_RETENTION` (0.96) over the final `EXAM_TAPER_DAYS` (30). Linear so
  there is no cliff where the day's review count suddenly doubles.
- Any scheduled review is clamped so it falls no later than the **day before** the
  exam. Not the exam day itself: the gate is eve-suppressed from 22:00 the night
  before through the end of exam day (ADR-0004), so a review landing on exam day
  is one that never happens.

Both are driven by the concept's own subject exam date, so an ungated subject with
no exam date is entirely unaffected.

## Consequences

- Review load rises through the final month. That is the trade being bought, and
  it lands in the weeks where the extra load is worth most.
- The mastery ceiling rises from `0.90 × accuracy` to `0.96 × accuracy`, so the
  0.85 threshold needs ~89% per-concept accuracy rather than ~94%. Still demanding,
  and still bounded by accuracy rather than by scheduling — the taper makes the
  target reachable, it does not make it easy.
- `EXAM_PEAK_RETENTION` stops at 0.96 rather than going higher on purpose. At 0.98
  the intervals roughly halve again, and in a day capped at a fixed number of
  correct answers those extra reviews of already-known material crowd out the
  drills aimed at weak concepts — strictly worse practice for two points of
  ceiling.
- The Sept 20 dashboard becomes an honest reading rather than a snapshot of stale
  cards, because every concept has been refreshed close to the sitting.
- Stability estimates drift slightly low for tapered cards, since intervals are
  shortened relative to what FSRS asked for. Same direction of error as ADR-0008
  and accepted for the same reason.
- The gate retires after the exam (ADR-0004), so the taper has no life beyond the
  sitting it serves.
