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
# The generator thresholds are widened for free response: producing and typing a
# numeric answer takes materially longer than picking from four options, and these
# were tuned when generator items were still multiple choice. Left at 90s, almost
# every typed answer would grade Hard, shortening intervals and inflating review
# load on evidence that is really about typing speed. 150s is still far tighter
# than the real ~6 min/question pace.
GRADE_FAST_MS_GEN: int = int(os.getenv("GRADE_FAST_MS_GEN", "30000"))
GRADE_SLOW_MS_GEN: int = int(os.getenv("GRADE_SLOW_MS_GEN", "150000"))

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
# quests, new-per-day cap, records, the study gate's quota — rolls over at local
# midnight in this zone. An IANA name rather than a fixed UTC offset because a
# fixed offset is wrong for half the year anywhere that observes DST: Chicago is
# UTC-6 in winter and UTC-5 in summer, and a hardcoded offset silently moves the
# rollover by an hour every spring and autumn.
STUDY_TIMEZONE: str = os.getenv("STUDY_TIMEZONE", "America/Chicago")

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

# Generator concepts at/above this measured mastery are served as free-response
# (typed answer) instead of multiple choice: recognition is easier than recall, so
# once a concept is known the four options give it away and stop testing anything.
# Set low deliberately. Four numeric options can often be reasoned backwards from
# by a learner who could not produce the answer, and the real sitting is five-option
# multiple choice — so practising by typing is strictly harder than the exam, which
# is the direction worth erring in.
TYPED_ANSWER_MASTERY: float = float(os.getenv("TYPED_ANSWER_MASTERY", "0.55"))
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
