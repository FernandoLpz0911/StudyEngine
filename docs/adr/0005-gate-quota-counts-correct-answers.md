# 5. The gate quota counts correct answers; the daily goal keeps counting answers

Date: 2026-07-29

## Status

Accepted

## Context

The gate opens when the learner has done "20 questions" — reusing the existing
`daily_goal` number rather than introducing a second one to tune. But
`daily_goal` is measured by `answered_today`: items *settled*, right or wrong. It
feeds the goal ring, the streak, the quests and the XP curve.

Read against `answered_today`, the gate has an obvious hole. Twenty deliberate
wrong answers open it in about two minutes, and that escape will be taken the
first morning the learner is in a hurry — after which the gate is theatre.

Read against correct answers instead, the hole closes, but the number 20 now
means two different costs depending on which counter is asking.

## Decision

The gate reads a **correct-answer** count for the day. The daily goal, the goal
ring, the streak, quests and XP are left exactly as they are, still counting
answers settled. One configured number (`daily_goal`), two readings of it.

`daily_goal` is *not* redefined to mean correct-only. Doing so would make the
domain cleaner but would silently re-scope the streak, the quest targets and the
XP curve, and would retroactively change what every past goal-hit day meant.

## Consequences

- The goal ring can read 20/20 while the gate is still closed. At 80% accuracy
  the ring fills at 20 answers and the gate opens at about 25. This is a genuine
  UI inconsistency and the gate must state its own count plainly
  ("17 / 20 correct") rather than borrowing the ring's framing.
- The gate cost is variable: a bad day costs more wall-clock than a good one.
  Accepted as correct — the quota is denominated in work done, not attempts made.
- A wrong answer never strands the learner. The concept is requeued by the
  existing in-session retry queue (`RETRY_GAP`), so every wrong answer is
  followed by another shot at the same material and the count always converges.
- No new setting to tune, and no schema change for the count itself — correct
  answers for the local day are derivable from the `interaction` log.
