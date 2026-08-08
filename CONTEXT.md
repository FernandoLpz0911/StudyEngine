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

## Readiness

**Projected score** — the raw mark the learner would be expected to earn sitting
the exam today: every concept's chance of being answered correctly, weighted by
its share of the paper. *The* readiness number. It replaced a count of concepts
over a mastery threshold, which was never calibrated to the exam and reported a
comfortable pass as a failure — and, when optimised, advised dropping material
that a projected score shows is worth keeping.

Built from [[measured-attempt]]s alone, in *both* its factors — accuracy and
retention. The exam is sat unaided, so an answer given with a worked example in
recent memory is evidence about a different task, and crediting it would report a
readiness the sitting will not honour. Deliberately not the number that rewards
effort: work done under guidance is real and is counted, but it is counted
somewhere else.

**Guessing floor** — the mark a pure guess earns on a multiple-choice paper. It is
why an unstudied concept is worth more than nothing, and why abandoning a concept
costs only the gap between studied and guessed rather than its whole weight. The
reason breadth beats depth here.

**Pass margin** — how far the [[projected-score]] sits above the pass mark. The
mark itself is an estimate: the sitting is scaled and the raw cut is unpublished
and moves, so readiness is declared with room to spare rather than on the line.

**Marks at stake** — what a concept is worth times how much of it is unearned.
What practice should be aimed at, and deliberately not the same as "weakest": a
heavily weighted concept answered moderately well carries more unearned marks than
a trivial one answered badly.

## Exam pacing

**Coverage** — how much of a subject has been *introduced* at all, as distinct
from how well it is known. Coverage and mastery fail differently: a half-learned
concept is worth something on exam day, a never-seen one is worth nothing, and
unlike mastery it cannot be repaired late — a first exposure in the final week can
only be crammed.

**Coverage deadline** — the day by which every concept in a subject must have been
seen at least once, set far enough before the [[exam-date]] that even the last
concept introduced still gets a full stretch of spaced review. Derived from the
exam date, never configured beside it, so it cannot drift out of step with the
sitting it serves.

**Intro quota** — the number of brand-new concepts a subject owes *today* against
its coverage deadline. Self-correcting: a skipped day raises tomorrow's number on
its own, and the quota falls to zero once coverage is complete. It paces in both
directions — a floor on a busy day, and equally a ceiling on a quiet one, since
racing through the syllabus leaves a wall of first exposures all maturing at once.

**Drill** — an extra, off-schedule rep served only to keep the day's [[quota]]
payable when the scheduled work has run out, aimed at the weakest concepts.
Distinct from a review, which is a card falling *due*. A drill is not evidence
the schedule can trust — the card was not due, so answering it correctly says
little — but failing one is real evidence of forgetting.

**Teaching stage** — how much of the answer an item shows before asking for it.
*Study* shows this problem's own worked solution and asks the learner to
reproduce it; *paired* shows a solved sibling problem and asks for a fresh one;
*solo* shows nothing. Derived from the log each time an item is served, never
stored, so it tracks the evidence rather than having to be kept in step with it.
The distinction exists because a retrieval loop run on material that cannot yet
be retrieved teaches surface pattern-matching, not the method.

**Measured attempt** — a [[solo]]-stage answer: the only kind that counts toward
accuracy, and so toward mastery, resting, drill targeting, the frontier, and the
[[projected-score]]. A scaffolded answer came with a worked solution in recent
memory; crediting it would report the learner's ability to copy one. The reason
readiness can be trusted to fall when the ladder is doing its job.

**Ascent** — how far a concept has climbed the [[teaching-stage]] ladder: which
rung it stands on, plus how far it has come toward leaving that rung. The measure
guided work moves, and the answer to "am I needing less help than I did". Distinct
from [[projected-score]], which only unaided work moves — the two are separate
because one number cannot honestly say both "you have worked through this" and
"you would pass on Sunday". They are not permanently divorced: on the top rung a
concept's remaining climb *is* its unaided accuracy against its bar, so ascent
converges on readiness exactly as the help stops being needed. The exam-weighted
mean over a subject is its ascent.

**Stuck** — a concept another attempt will not help: either a run of consecutive
misses, or many reps whose FSRS stability never leaves the floor. The second is
the treadmill the ladder exists for — eighteen attempts that left stability at
0.0 are eighteen answers that taught nothing. A stuck concept is remediated with
a study trial rather than tested again.

**Required accuracy** — the bar a concept must clear, raised by its downstream
reach. A foundation carries every concept above it, so a gateway is held to a
higher standard than a leaf: shaky conditional probability does not cost its own
marks, it costs Bayes and conditional expectation too. Saturating, because past a
few dependents a concept is already foundational.

**Accuracy floor** — the level of unaided accuracy below which no new concept is
introduced. The mirror of [[running-ahead]]: the same evidence read as a floor
rather than a ceiling. Widening the syllabus for a learner who cannot answer what
they already have widens the guessing.

**Coverage backstop** — the accuracy floor's escape hatch. Coverage is the one
part of readiness that cannot be repaired late, so the floor yields as the
[[coverage-deadline]] approaches and introductions resume whatever accuracy says.
Without it the floor would strand unseen material permanently for a learner whose
accuracy never recovers.

**Prerequisite repair** — re-testing the foundation a miss came from instead of
the concept that exposed it, when that foundation is the weaker of the two. Depth
one: following the chain down walks the session away from what the exam asks
about, and the prerequisite's own miss opens the next step by itself.

**Don't-know** — declining to answer rather than guessing at one. Counts as a
miss, because it is one, but it is *stronger* evidence than a wrong answer:
a wrong answer is ambiguous between a slip and ignorance, while this is
unambiguous non-retrieval. So it demotes the concept a rung on its own, where a
wrong answer needs a run of them. Pays nothing toward [[quota]] directly — the
[[teaching-stage|study trial]] it earns pays, once the answer is reproduced — so
admitting ignorance is the fast route to being taught and never a route out of
the day's work.

**Aided answer** — a [[teaching-stage|solo]] item answered with the concept
explanation open. Not a [[measured-attempt]]: the problem was made easier than the
exam will be, so counting it as unaided evidence is the same lie as counting a
worked example — just one the learner tells rather than the system. Declared
rather than detected, behind a confirmation that names the price, because the
habit it guards against is reaching for the explanation without noticing. It costs
the answer's XP and combo as well as its readiness credit, and still pays the
[[quota]] and [[ascent]] — the currencies it forfeits are the ones that stand for
unaided performance.

**Reflection** — naming which step of the worked solution first went wrong, after
a miss. What makes a shown solution a read one, and the only record of *where* a
concept breaks rather than that it broke. "Not sure" is stored as its own answer:
being unable to locate the break is the most informative thing the concept can
report.

**Slog** — a concept that costs disproportionate *time*, as distinct from a
[[leech]], which costs disproportionate *attempts*. Answered correctly and always
slowly, which is invisible to accuracy, to the schedule and to the
[[projected-score]], all of which are indifferent to how long a right answer took.
Read two ways, because the remedies differ: slow to *understand* blames the
explanation, slow to *solve* blames the practice. Diagnostic only — it is
reported, never acted on.

**Leech** — a concept eating disproportionate *attempts*: forgotten and
re-forgotten past a threshold of lapses. More reps demonstrably are not working,
so it is owed a reformulation rather than another rep. The [[slog]]'s counterpart.

**Guessing correction** — backing the luck out of a rate measured over answers
that offered options, since one in every `n` of them is right without knowing
anything. Applied to a rate, never to a single answer, and self-retiring: free
response carries no guessing, so the correction shrinks to nothing as real answers
replace the old ones.

**Bare statement** — a question states the situation and what to find, and nothing
else. Naming the tool ("using the law of total variance"), restating its closed
form inside the ask, or supplying an intermediate the learner should derive turns a
problem into arithmetic and measures nothing. The sitting supplies none of it, so
neither does practice.

**Readiness bar** — the standard a concept must clear to count as ready, set for
an exam *harder* than the one expected rather than the one hoped for. Deliberately
strict in three directions at once: answers are typed rather than chosen long
before a concept is comfortable, confidence takes many reviews to saturate, and
the mastery threshold sits above the comfortable reading. A readiness number that
flatters is worse than no number at all before a dated sitting.

**Exam taper** — the convergence of the schedule on the exam date: reviews are
compressed as the sitting approaches and never scheduled past the last day they
could be served. Without it the scheduler, which has no notion that an exam
exists, spaces concepts into intervals that are optimal for next year and useless
for September.

## The study day

**Study day** — the unit every "today" is counted in: streak, daily goal, quests,
new-per-day cap, records, and the gate's quota. It is the learner's *waking* day,
not the calendar's — it turns over in the early hours rather than at midnight, so
a session finished at 1am closes the day it began in. A calendar boundary would
break a streak mid-session, demand a fresh quota for a day not yet lived, and
split one sitting across two days of statistics.

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

**Rested** — held far enough above the readiness bar that reviewing it is spending
the day on something already known, while the concepts that decide the exam go
unpractised. Much of it is exercised indirectly anyway: a question about the
Normal distribution uses variance and standardisation whichever card is on screen.
Distinct from [[suspended]] in that nobody chooses it and nothing records it —
resting is *self-undoing*, because the mastery it is judged on decays with time
since the last review, so a rested concept slides back under the bar and rejoins
the rotation by itself. Resting stops near the sitting, so nothing goes in
untouched.

**Running ahead** — sustained recent accuracy above the level the plan assumed.
The [[coverage-deadline]] normally paces introductions in both directions, but a
learner outperforming it is allowed past the ceiling: the rest of the syllabus is
better met early than waited for.

## Study gate

**Gate** — the block placed between the learner and their own computer until
today's [[quota]] is paid. The gate is *closed* while the quota is unpaid and
*open* once it is met; it opens for the remainder of the local day and closes
again when the day rolls over. Opening is earned by answering, not by dismissing:
the gate has no close button.

**Quota** — the number of **correct** answers owed today before the gate opens.
Distinct from the **daily goal**, which counts answers *settled* regardless of
correctness. The two are deliberately different readings of the same number: the
daily goal measures effort shown up with, the quota measures work actually done.
A wrong answer costs time and pays nothing toward the quota, but never strands
the learner — the concept returns through the in-session retry queue.

**Bail** — a rationed manual opening of the gate without paying the quota.
Scarce and counted, so that a genuine emergency has an answer that is not
"abandon the whole system". Every bail is recorded; the remaining ration is shown
on the gate itself. Spending the last bail does not make the day unescapable —
it makes it inconvenient.

**Exam date** — the sitting the gate exists to serve. It bounds the gate's life:
the gate falls silent the night before so the learner sleeps and sits the exam,
and retires itself afterwards rather than outliving its reason. It also anchors
everything the schedule paces toward — the [[coverage-deadline]] and the
[[exam-taper]] are both derived from it, so moving the sitting moves the plan.
