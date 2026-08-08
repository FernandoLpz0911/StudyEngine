"""Runtime configuration — all values overridable via environment variables."""
import os

TARGET_RETENTION: float = float(os.getenv("TARGET_RETENTION", "0.9"))

# Cap the first few review intervals to one day so a freshly seen concept is not
# pushed to an 8+ day gap before it is actually encoded.
EARLY_REINFORCEMENT_REPS: int = int(os.getenv("EARLY_REINFORCEMENT_REPS", "5"))

# Database location (gitignored; created on first seed).
DB_PATH: str = os.getenv("DB_PATH", "data/app.db")

# Where each subject's concept-graph seed JSON lives.
SUBJECTS_DIR: str = os.getenv("SUBJECTS_DIR", "data/subjects")

# Objective FSRS grading from response time (no self-rating): a correct answer
# under FAST_MS is graded Easy, over SLOW_MS is graded Hard, otherwise Good.
# Recall cards are recognition (fast by nature); generator problems need multi-step
# work, so they get their own, much wider thresholds — otherwise every generator
# answer grades Hard and FSRS under-spaces them.
GRADE_FAST_MS: int = int(os.getenv("GRADE_FAST_MS", "8000"))
GRADE_SLOW_MS: int = int(os.getenv("GRADE_SLOW_MS", "30000"))
# Response time is consulted at the `solo` stage only (ADR-0014). With a worked
# example on screen the clock cannot tell reading from solving from copying, so a
# scaffolded item grades on correctness alone rather than on a number that means
# nothing. `study` never reaches the scheduler at all.
#
# The solo thresholds are for typed free response against a real ~360s/question
# exam pace. At 150s, 40% of correct answers already graded Hard *while still
# multiple choice* — every one of them shortening an interval on evidence that was
# really about how long an answer takes to produce. 300s marks "laboured even by
# exam standards" instead of marking "typed the answer". The amber question timer
# (EXAM_TIMER_TARGET_S) is the pacing instrument; a grade threshold is an input to
# a difficulty model and makes a poor whip.
GRADE_FAST_MS_GEN: int = int(os.getenv("GRADE_FAST_MS_GEN", "60000"))
GRADE_SLOW_MS_GEN: int = int(os.getenv("GRADE_SLOW_MS_GEN", "300000"))

# Mastery for the progress dashboard: full rep-confidence is reached at
# MASTERY_TARGET_REPS reviews; a concept counts as "mastered" at/above
# MASTERY_THRESHOLD. Accuracy is measured over the last MASTERY_ACCURACY_WINDOW.
# Six reps rather than three: a concept answered right three times is not an
# established one, and since mastery also ranks drill selection, a slower-
# saturating confidence term keeps under-practised concepts at the front of the
# queue instead of quietly reading as done.
MASTERY_TARGET_REPS: int = int(os.getenv("MASTERY_TARGET_REPS", "6"))
MASTERY_THRESHOLD: float = float(os.getenv("MASTERY_THRESHOLD", "0.85"))
MASTERY_ACCURACY_WINDOW: int = int(os.getenv("MASTERY_ACCURACY_WINDOW", "20"))

# Endowed progress: every concept shows at least this much "familiarity" so a
# freshly added syllabus never reads 0% (motivation — you start partway up the
# hill). Real mastery and the "mastered" count still use measured signals only.
ENDOWED_BASELINE: float = float(os.getenv("ENDOWED_BASELINE", "0.1"))

# The learner's day boundary. Everything that means "today" — streak, daily goal,
# quests, new-per-day cap, records, the study gate's quota — rolls over at
# DAY_ROLLOVER_HOUR in this zone. An IANA name rather than a fixed UTC offset because a
# fixed offset is wrong for half the year anywhere that observes DST: Chicago is
# UTC-6 in winter and UTC-5 in summer, and a hardcoded offset silently moves the
# rollover by an hour every spring and autumn.
STUDY_TIMEZONE: str = os.getenv("STUDY_TIMEZONE", "America/Chicago")

# The hour the study day turns over. Not midnight: a session finished at 1am is the
# tail of the day the learner is still awake in, not the start of a new one. Rolling
# over at midnight would break the streak of anyone studying late, pay the gate's
# quota for a day not yet lived, and split one sitting across two days' statistics.
DAY_ROLLOVER_HOUR: int = int(os.getenv("DAY_ROLLOVER_HOUR", "3"))

# Streak freeze: one earned per this many distinct study days; each earned freeze
# silently bridges one missed day so a single slip never resets the streak.
STREAK_FREEZE_EARN_DAYS: int = int(os.getenv("STREAK_FREEZE_EARN_DAYS", "5"))

# A concept with at least this many lapses is a "leech" — surfaced for special
# attention (a mnemonic / reformulation) since it is eating disproportionate effort.
LEECH_LAPSES: int = int(os.getenv("LEECH_LAPSES", "4"))

# Fatigue guard: if accuracy over the last FATIGUE_WINDOW answers drops below
# FATIGUE_THRESHOLD, suggest ending the session (quality over grind).
FATIGUE_WINDOW: int = int(os.getenv("FATIGUE_WINDOW", "5"))
FATIGUE_THRESHOLD: float = float(os.getenv("FATIGUE_THRESHOLD", "0.4"))

# Errorful-retrieval retry: a missed concept is re-queued to reappear this many
# items later in the same session. Re-testing a fresh miss after a short, filled
# gap (not immediately) is among the strongest known boosts to retention.
RETRY_GAP: int = int(os.getenv("RETRY_GAP", "3"))

# Cold start: a served concept whose measured mastery is below this counts as
# "not yet learned" — the UI auto-opens its explanation up front (never seen,
# never answered correctly, or low mastery all fall under this threshold).
COLD_START_MASTERY: float = float(os.getenv("COLD_START_MASTERY", "0.5"))

# Ceiling on a single answer's recorded time. The client measures *active* time
# (it stops while the tab is hidden), but a stale or misbehaving one can still post
# wall clock — one abandoned tab once logged an answer at 43 hours, which grades as
# Hard and drags the concept's interval down for a walk away from the desk. Well
# past any genuine question, so clamping cannot change an honest grade.
MAX_ANSWER_MS: int = int(os.getenv("MAX_ANSWER_MS", str(20 * 60 * 1000)))

# Exam P question-pace target (seconds): the on-screen timer turns amber past this.
# 180s is a tighter practice pace than the real SOA exam (~6 min/question).
EXAM_TIMER_TARGET_S: int = int(os.getenv("EXAM_TIMER_TARGET_S", "180"))

# Daily-goal target: items answered per day that fills the progress ring and keeps
# the streak alive. Small enough to hit on a busy day (habit > heroics).
DAILY_GOAL: int = int(os.getenv("DAILY_GOAL", "20"))

# Cap on brand-new concepts introduced per day. Every new concept becomes several
# future reviews; without a cap an eager first session floods the review queue
# three days later and buries the learner. (Anki's default is comparable.)
NEW_PER_DAY: int = int(os.getenv("NEW_PER_DAY", "8"))

# The sitting itself, and what readiness is measured against (ADR-0012). Readiness
# is a projected raw score rather than a count of concepts over a threshold: that
# count read 6/34 for a plan implying ~88% per-concept accuracy, which is a
# comfortable pass reported as a failure.
#
# The SOA scales Exam P to 0-10 and passes at 6 without publishing the raw cut,
# which moves between sittings — hence a margin rather than a bare comparison, and
# hence a readout that states the assumption instead of hiding it.
EXAM_QUESTIONS: int = int(os.getenv("EXAM_QUESTIONS", "30"))
EXAM_PASS_MARK: int = int(os.getenv("EXAM_PASS_MARK", "21"))
EXAM_TARGET_MARGIN: int = int(os.getenv("EXAM_TARGET_MARGIN", "4"))
# Five options, so a blank guess scores one in five. Crediting it is what makes the
# projection an estimate of the mark actually earned — and what correctly prices
# dropping a concept as the gap between studied and guessed, not its whole weight.
EXAM_GUESS_P: float = float(os.getenv("EXAM_GUESS_P", "0.2"))

# Resting: a concept held this far above the readiness bar stops being reviewed,
# freeing the day's quota for material that actually decides the exam. Much of it
# is exercised indirectly anyway — a Normal question uses variance and
# standardisation whichever card is on screen. Self-undoing rather than permanent:
# mastery carries a decaying retention factor, so a rested concept slides back
# under the threshold on its own. Resting stops inside the last REST_STOP_DAYS so
# nothing goes into the sitting untouched.
REST_MASTERY: float = float(os.getenv("REST_MASTERY", "0.92"))
REST_STOP_DAYS: int = int(os.getenv("REST_STOP_DAYS", "10"))

# The accuracy the plan assumes, and the floor under introducing anything new.
# Set at 0.80 rather than the ~0.6 a "desirable difficulty" argument would pick:
# accuracy measured here is measured on *solo* items only, and a subject answered
# at 0.6 unaided is one being pattern-matched, not understood. Below the floor the
# frontier closes — a syllabus met at 40% accuracy is a wider surface of the same
# guessing, and the marks lost to consolidation outweigh the marks gained by
# coverage (see COVERAGE_BACKSTOP_DAYS for the escape).
ACCURACY_FLOOR: float = float(os.getenv("ACCURACY_FLOOR", "0.80"))

# A concept's bar rises with how much is built on top of it: a shaky prerequisite
# does not cost its own marks, it costs every dependent's too. The bonus is added
# on a saturating ramp over downstream reach — past a few dependents a concept is
# already foundational, and an unbounded ramp would demand accuracy no honest
# measurement reaches. 0.80 floor + 0.12 => 0.92 for a full gateway concept.
PREREQ_ACCURACY_BONUS: float = float(os.getenv("PREREQ_ACCURACY_BONUS", "0.12"))
PREREQ_REACH_SATURATION: int = int(os.getenv("PREREQ_REACH_SATURATION", "4"))

# The teaching ladder (ADR-0013). A concept below its bar is served with a worked
# example instead of being tested into the ground.
#   STUCK_MISSES         consecutive misses that mean the concept is gone right now
#   STUCK_MIN_REPS       reps before the chronic (stability-floor) test can fire
#   STUCK_STABILITY_DAYS stability under this after that many reps is a treadmill:
#                        18 reps once left one concept at 0.0, which is 18 answers
#                        that taught nothing
#   PAIRED_PROMOTE_WINDOW attempts the scaffold is judged over before it comes off
#   MAX_CONSECUTIVE_STUDY cap on repeated study trials, so remediation terminates
#   TEACHING_WINDOW      trailing attempts the stage is derived from
STUCK_MISSES: int = int(os.getenv("STUCK_MISSES", "3"))
STUCK_MIN_REPS: int = int(os.getenv("STUCK_MIN_REPS", "8"))
STUCK_STABILITY_DAYS: float = float(os.getenv("STUCK_STABILITY_DAYS", "1.0"))
MAX_CONSECUTIVE_STUDY: int = int(os.getenv("MAX_CONSECUTIVE_STUDY", "3"))
TEACHING_WINDOW: int = int(os.getenv("TEACHING_WINDOW", "8"))
# Promotion off the scaffold is the *same* comparison as demotion onto it —
# accuracy against the concept's own bar, measured at the rung it is standing on —
# rather than a fixed streak. A fixed streak ignored the bar entirely: two correct
# guided answers once graduated a concept with 0.64 unaided accuracy against a
# 0.92 requirement. One comparison, applied at whichever rung you are on, is also
# what makes ascent's within-rung credit computable the same way everywhere.
PAIRED_PROMOTE_WINDOW: int = int(os.getenv("PAIRED_PROMOTE_WINDOW", "4"))

# Slog: a concept costing disproportionate *time*, as distinct from a leech, which
# costs disproportionate *attempts*. Purely diagnostic — it feeds no schedule, no
# accuracy and no projection (ADR-0014). Relative to the subject's own median for
# the same stage class, because an absolute threshold cannot be shared between an
# ODE and a flashcard and would need retuning whenever content changed.
SLOG_MULTIPLE: float = float(os.getenv("SLOG_MULTIPLE", "1.5"))
SLOG_MIN_SAMPLES: int = int(os.getenv("SLOG_MIN_SAMPLES", "3"))

# The accuracy floor's escape hatch. Pausing the frontier protects consolidation,
# but held indefinitely it strands the unseen syllabus at the guessing floor —
# and unlike mastery, coverage cannot be repaired late (ADR-0007). So the pause
# yields once the coverage deadline is this close, and the deadline resumes
# driving introductions whatever recent accuracy says.
COVERAGE_BACKSTOP_DAYS: int = int(os.getenv("COVERAGE_BACKSTOP_DAYS", "14"))

# Running ahead: when recent accuracy is this high and the day's scheduled work is
# done, the coverage deadline stops being a ceiling and the frontier opens up to
# the new-per-day cap. Pacing exists to stop a flood of first exposures maturing
# at once (ADR-0007) — but a learner outperforming the plan should be allowed to
# reach the rest of the syllabus early rather than wait out the schedule.
AHEAD_ACCURACY: float = float(os.getenv("AHEAD_ACCURACY", "0.9"))
AHEAD_WINDOW: int = int(os.getenv("AHEAD_WINDOW", "20"))

# Coverage deadline: every concept in a subject must be introduced this many days
# before its exam. Coverage is the one part of readiness with a hard deadline — a
# concept first met the week of the exam can only be crammed, never spaced — so
# introduction is driven by this deadline rather than by whatever the review queue
# happens to leave over (ADR-0007).
CONSOLIDATION_DAYS: int = int(os.getenv("CONSOLIDATION_DAYS", "40"))

# Exam taper: FSRS normally schedules toward TARGET_RETENTION with no idea an exam
# exists, so it will happily place a review after the sitting. Over the final
# EXAM_TAPER_DAYS the target ramps to EXAM_PEAK_RETENTION and intervals are clamped
# to the exam date, so every concept is fresh when it is actually needed (ADR-0009).
EXAM_TAPER_DAYS: int = int(os.getenv("EXAM_TAPER_DAYS", "30"))
EXAM_PEAK_RETENTION: float = float(os.getenv("EXAM_PEAK_RETENTION", "0.96"))

# Generator concepts are *always* free response (ADR-0014). There is no mastery
# threshold any more: four options let a learner who could not produce the answer
# reason backwards to it, and a lucky guess is a false positive in the one number
# every readiness signal is built from. The whole 199-answer Exam P log was
# multiple choice, and backing the 25% floor out of it put true unaided skill at
# ~20% against an observed 40%. The ladder now supplies the support that the
# options were crudely standing in for.
#
# Recall cards keep their options: a flashcard has no computed answer, so typed
# grading would be string matching, and marking "BCNF" wrong against "Boyce-Codd
# Normal Form" corrupts accuracy in the opposite direction.

# Guessing correction. An answer chosen from `choices_n` options carries a 1/n
# chance of being right without knowing anything, so a *rate* measured over such
# answers overstates skill and is corrected by (observed - ḡ) / (1 - ḡ). Self-
# retiring: ḡ is 0 for free response, so the correction vanishes as real answers
# replace the multiple-choice history rather than needing a flag day.
DEGUESS_HISTORY: bool = os.getenv("DEGUESS_HISTORY", "1") != "0"

# Relative tolerance for grading a typed numeric answer (choices are exact-match).
# 1%, not 0.5%: the key is rounded to three decimals, so a correctly solved 0.4237
# keyed as 0.424 would mark a learner's 0.42 wrong. Penalising rounding costs a
# quota answer and teaches nothing, and real answer choices are far wider apart.
TYPED_REL_TOLERANCE: float = float(os.getenv("TYPED_REL_TOLERANCE", "0.01"))

# Global interleaved sessions: down-weight a candidate from the subject just
# studied so consecutive items come from different subjects (interleaving). Each
# session opens with WARMUP and closes with COOLDOWN "confidence builders" (items
# you are most likely to get right), pacing toward the ~85%-success sweet spot.
INTERLEAVE_PENALTY: float = float(os.getenv("INTERLEAVE_PENALTY", "0.5"))
GLOBAL_WARMUP: int = int(os.getenv("GLOBAL_WARMUP", "2"))
GLOBAL_COOLDOWN: int = int(os.getenv("GLOBAL_COOLDOWN", "2"))

# Personal FSRS fit: re-fitting the 21 FSRS weights to the learner's own review
# log needs enough data to beat the population defaults it starts from.
FSRS_MIN_REVIEWS: int = int(os.getenv("FSRS_MIN_REVIEWS", "400"))

# Global DKT (deep knowledge tracing): the trained model drives weak-concept
# selection only once it clears both gates — enough graded interactions and a
# validation AUC that beats this floor. Below the gate, FSRS retention drives it.
DKT_MIN_INTERACTIONS: int = int(os.getenv("DKT_MIN_INTERACTIONS", "300"))
DKT_MIN_AUC: float = float(os.getenv("DKT_MIN_AUC", "0.70"))

# Study gate: the full-screen block held until the day's quota of *correct*
# answers is paid (ADR-0004, ADR-0005). The quota number is DAILY_GOAL, read
# against correct answers rather than answers settled.
GATE_SUBJECT: str = os.getenv("GATE_SUBJECT", "examp")
# Emergency bails, rationed over a trailing window so a genuine emergency has an
# answer that is not "uninstall the gate", while staying too scarce to spend idly.
GATE_BAIL_RATION: int = int(os.getenv("GATE_BAIL_RATION", "3"))
GATE_BAIL_WINDOW_DAYS: int = int(os.getenv("GATE_BAIL_WINDOW_DAYS", "30"))
# Watchdog cadence (minutes) for the systemd --user timer. Since the gate raises
# at most once per local day (ADR-0006), every tick after the first is a no-op, so
# a tight interval buys nothing: the timer's only job is to notice an unpaid day
# boundary while already logged in. Hourly is well inside that.
GATE_WATCHDOG_MIN: int = int(os.getenv("GATE_WATCHDOG_MIN", "60"))
# Exam eve: the gate falls silent from this local hour the day before the exam so
# the learner sleeps and sits it, and retires permanently once the exam has passed.
GATE_EVE_HOUR: int = int(os.getenv("GATE_EVE_HOUR", "22"))
# Deadman: a gate holding the seat grab that stops servicing its own timer is a
# dead keyboard in every window, so it self-kills if this many seconds elapse
# between watchdog ticks.
GATE_DEADMAN_SEC: int = int(os.getenv("GATE_DEADMAN_SEC", "20"))
# The gate runs its own uvicorn on a private port so it never collides with the
# normal `python -m engine.cli.app` on 8000.
GATE_PORT: int = int(os.getenv("GATE_PORT", "8765"))
