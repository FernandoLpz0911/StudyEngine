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
GRADE_FAST_MS: int = int(os.getenv("GRADE_FAST_MS", "8000"))
GRADE_SLOW_MS: int = int(os.getenv("GRADE_SLOW_MS", "30000"))

# Mastery for the progress dashboard: full rep-confidence is reached at
# MASTERY_TARGET_REPS reviews; a concept counts as "mastered" at/above
# MASTERY_THRESHOLD. Accuracy is measured over the last MASTERY_ACCURACY_WINDOW.
MASTERY_TARGET_REPS: int = int(os.getenv("MASTERY_TARGET_REPS", "3"))
MASTERY_THRESHOLD: float = float(os.getenv("MASTERY_THRESHOLD", "0.8"))
MASTERY_ACCURACY_WINDOW: int = int(os.getenv("MASTERY_ACCURACY_WINDOW", "20"))

# Endowed progress: every concept shows at least this much "familiarity" so a
# freshly added syllabus never reads 0% (motivation — you start partway up the
# hill). Real mastery and the "mastered" count still use measured signals only.
ENDOWED_BASELINE: float = float(os.getenv("ENDOWED_BASELINE", "0.1"))

# Streak day boundary: hours offset from UTC for "today" so the streak rolls over
# at the learner's local midnight, not UTC's.
STREAK_TZ_OFFSET: float = float(os.getenv("STREAK_TZ_OFFSET", "0"))

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

# Exam P question-pace target (seconds): the on-screen timer turns amber past this.
# 180s is a tighter practice pace than the real SOA exam (~6 min/question).
EXAM_TIMER_TARGET_S: int = int(os.getenv("EXAM_TIMER_TARGET_S", "180"))

# Daily-goal target: items answered per day that fills the progress ring and keeps
# the streak alive. Small enough to hit on a busy day (habit > heroics).
DAILY_GOAL: int = int(os.getenv("DAILY_GOAL", "20"))

# Global interleaved sessions: down-weight a candidate from the subject just
# studied so consecutive items come from different subjects (interleaving). Each
# session opens with WARMUP and closes with COOLDOWN "confidence builders" (items
# you are most likely to get right), pacing toward the ~85%-success sweet spot.
INTERLEAVE_PENALTY: float = float(os.getenv("INTERLEAVE_PENALTY", "0.5"))
GLOBAL_WARMUP: int = int(os.getenv("GLOBAL_WARMUP", "2"))
GLOBAL_COOLDOWN: int = int(os.getenv("GLOBAL_COOLDOWN", "2"))

# Global DKT (deep knowledge tracing): the trained model drives weak-concept
# selection only once it clears both gates — enough graded interactions and a
# validation AUC that beats this floor. Below the gate, FSRS retention drives it.
DKT_MIN_INTERACTIONS: int = int(os.getenv("DKT_MIN_INTERACTIONS", "300"))
DKT_MIN_AUC: float = float(os.getenv("DKT_MIN_AUC", "0.70"))
