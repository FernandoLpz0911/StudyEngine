# 6. The gate raises once per local day, on a real timezone

Date: 2026-07-29

## Status

Accepted — supersedes the always-on watchdog behaviour described in ADR-0004.

## Context

ADR-0004 armed a `systemd --user` timer that re-raised the gate every 15 minutes
for as long as the day's quota was unpaid, at any hour. That was chosen
deliberately over a once-a-day gate, with the interruption risk noted at the time.

First contact with it settled the question. On the first live day the gate came
up, was bailed out of, and then came back on the next tick — turning one
enforceable decision ("pay the quota now") into a recurring interruption that
costs a bail or a `pkill` every fifteen minutes. A gate that has to be fought
repeatedly is a gate that gets uninstalled.

The same day exposed a second, quieter bug. `STREAK_TZ_OFFSET` defaulted to `0`,
so "today" meant the **UTC** day for the streak, the daily goal, the quests, the
new-per-day cap, the records and the gate's quota. For a learner in Chicago the
day was rolling over at 19:00 local, and the gate's midnight reset — the thing
that decides when it may raise again — landed in the middle of the evening.

## Decision

**One raise per local day.** A `gate_raise` row is written when the gate comes up,
and `quota.should_raise()` refuses if one exists for the current local day. The
row is written *before* the window is shown, so a gate that is killed rather than
paid still counts as the day's raise. The watchdog timer stays at 15 minutes but
is now a cheap no-op after the first raise; it exists to catch the first unpaid
day boundary while already logged in.

This is deliberately kept out of `quota.status()`. That function answers "is the
quota paid", which the *running* gate polls to know when to release; folding the
raise record into it would make a gate release itself the instant it recorded its
own raise.

**A real timezone, not an offset.** `STREAK_TZ_OFFSET` is replaced by
`STUDY_TIMEZONE` (IANA name, default `America/Chicago`). A fixed offset cannot be
correct year-round anywhere that observes DST — Chicago is UTC-6 in winter and
UTC-5 in summer — so the rollover would drift by an hour twice a year.

Day-bounded queries no longer use SQLite's `date(ts, '+N hours')` modifier, which
can only express one fixed offset. They compare stored UTC timestamps against
precomputed UTC bounds for the local day (`local_day_bounds`), which is exact and
uses the existing index on `answered_at`. The two queries that group the *whole*
history by day — the streak's `_answered_days` and the `best_day` record — group
in Python instead, because each timestamp needs the offset that was in force for
it, which no single modifier can provide.

## Consequences

- **A killed gate is a free day.** `pkill` once and nothing raises again until
  tomorrow. This is the real cost of the change and it is accepted knowingly: the
  gate buys a daily habit and a moment of friction, not imprisonment, and it was
  never unbypassable (ADR-0004). The interruption it inflicts is now bounded and
  predictable, which is what makes it survivable for the weeks before the exam.
- The gate can still land at an awkward moment — it just lands once. The bail
  ration remains for the times that moment is genuinely impossible.
- Changing the day boundary re-scopes historical data: days that were grouped by
  UTC are now grouped by Chicago local time, so an evening answer moves from one
  day to the previous one. Streak lengths and `best_day` can shift by one as a
  result. Accepted as a one-off correction — the new grouping is the true one.
- `STUDY_TIMEZONE` is now the single place the day boundary is defined, and the
  gate no longer keeps its own copy of the offset arithmetic.
