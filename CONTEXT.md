# Domain Glossary

Canonical vocabulary for StudyEngine. Glossary only — no implementation detail,
no decisions. Terms are the shared language; when code and this file disagree,
one of them is wrong.

## Answer settlement

**Settle** — the full sequence that happens when one answer is graded: log it,
update spaced-repetition state, advance records, bank quests, record the retry
debt. One answer, one settlement, regardless of whether it came from the web API
or the CLI.

## Study loop

**Turn** — one served item plus its settlement: a concept is *selected*, an item
*served*, an answer *settled*. The unit the study loop advances by. In the CLI a
Turn is one pass of the loop; over the web API its two halves span two requests
(`GET next` serves, `POST answer` settles) with a network round-trip between.

**StudyLoop** — the live driver that advances Turns and owns all session-local
state (serving index, recent-answers list, in-session retry queue, combo streak,
best, session XP, last subject, the record tracker, DKT predictions). One
implementation behind two methods — *select the next item* and *settle an answer*
— that the CLI loop and each web request both drive, so the interleaving,
warmup/stall/cooldown pacing, and [[settle]] fold can't drift between front ends.
Distinct from the **session** *row* in the database (`create_session`): the
StudyLoop is that row's live, in-memory form and can be rebuilt from it after a
restart.

## Runs

Two distinct consecutive-correct counts. They are *not* the same number and have
different lifetimes.

**Combo streak** — consecutive correct answers **within the current session**.
Drives combo tiers, variable-ratio reward, and best-this-session framing. Resets
to zero when a session starts. A fresh session always begins with no combo.

**Record run** — consecutive correct answers **across the whole interaction
log**, spanning session boundaries. The only run that may set a longest-run
personal best. If the learner ends a session on a correct answer and continues
correctly in the next, the record run continues; the combo streak does not.

## Records

**Record (personal best)** — fastest correct answer, biggest single day, or
longest record run. Detected live as an answer is settled.

**Crossing** — the single answer at which a record is beaten. A record fires
**once**, at its crossing, never again on later answers still above the old mark.

**Baseline** — the prior best a new answer must beat to fire a record. Snapshotted
once per session; `best_day` excludes today so the daily record fires at its
crossing. Advanced in memory as records are set, and re-snapshotted when the local
day rolls over mid-session.

## Concept availability

**Introduced** — a concept that unlocks its dependents: seen at least once, *or*
suspended. A prerequisite must be introduced before its children become
selectable. One predicate, shared by selection and readiness, so the
suspended-counts / buried-doesn't rule lives in one place.

**Due** — a concept whose review is waiting *right now*: reviewed at least once,
its FSRS due time reached, and not currently suppressed. The same predicate backs
policy selection, the dashboard's per-concept flag, and the "reviews waiting"
count — a suspended or buried card is never due.

**Suspended** — taken out of rotation indefinitely by the learner ("I know
this"), until manually resumed. Counts as *introduced* for prerequisite purposes:
a suspended prereq does not block its children.

**Buried** — hidden until the next local day, then automatically back. Does *not*
count as mastery: a buried prereq keeps its children locked.

**Suppressed** — the union of suspended and buried: any concept currently hidden
from selection, for whatever reason.
