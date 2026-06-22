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
