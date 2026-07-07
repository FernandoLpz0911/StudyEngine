# Domain Glossary

Canonical vocabulary for StudyEngine. Glossary only — no implementation detail,
no decisions. Terms are the shared language; when code and this file disagree,
one of them is wrong.

## Answer settlement

**Settle** — the full sequence that happens when one answer is graded: log it,
update spaced-repetition state, advance records, bank quests, record the retry
debt. One answer, one settlement, regardless of whether it came from the web API
or the CLI.

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

**Suspended** — taken out of rotation indefinitely by the learner ("I know
this"), until manually resumed. Counts as *introduced* for prerequisite purposes:
a suspended prereq does not block its children.

**Buried** — hidden until the next local day, then automatically back. Does *not*
count as mastery: a buried prereq keeps its children locked.

**Suppressed** — the union of suspended and buried: any concept currently hidden
from selection, for whatever reason.
