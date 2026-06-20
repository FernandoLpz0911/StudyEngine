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
