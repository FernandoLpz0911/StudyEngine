"""SQLite connection factory and schema initialisation."""
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _db_path() -> str:
    return os.getenv("DB_PATH", "data/app.db")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection that commits on success, rolls back on error, then closes."""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the database file and apply the schema."""
    db_dir = Path(_db_path()).parent
    if str(db_dir):
        db_dir.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        # Idempotent migration for databases created before a column was added.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(concept)")}
        if "card_explanations" not in cols:
            conn.execute("ALTER TABLE concept ADD COLUMN card_explanations TEXT")
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(interaction)")}
        if "reason" not in cols:
            conn.execute("ALTER TABLE interaction ADD COLUMN reason TEXT")
        if "stage" not in cols:
            # Everything logged before the teaching ladder existed was an
            # unscaffolded attempt, so backfilling 'solo' keeps the whole history
            # measurable rather than silently dropping it out of accuracy.
            conn.execute(
                "ALTER TABLE interaction ADD COLUMN stage TEXT NOT NULL DEFAULT 'solo'"
            )
        if "choices_n" not in cols:
            # Everything logged before free response became universal was served as
            # four-option multiple choice, so the backfill is 4 rather than 0. It has
            # to be right: this column is what the guessing correction reads, and a
            # default of 0 would silently declare the whole history uncontaminated —
            # exactly the overstatement the correction exists to remove.
            conn.execute(
                "ALTER TABLE interaction ADD COLUMN choices_n INTEGER NOT NULL DEFAULT 4"
            )
        if "dont_know" not in cols:
            conn.execute(
                "ALTER TABLE interaction ADD COLUMN dont_know INTEGER NOT NULL DEFAULT 0"
            )
        if "aided" not in cols:
            # Backfilled to 0: before the confirmation existed the explanation could
            # be opened silently, so the log cannot say which past answers used it.
            # 0 is the optimistic reading, and the only honest one available — the
            # alternative would be inventing a fact about every historical answer.
            conn.execute(
                "ALTER TABLE interaction ADD COLUMN aided INTEGER NOT NULL DEFAULT 0"
            )
