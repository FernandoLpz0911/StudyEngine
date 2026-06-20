import pytest

from engine.db.seed import load_all


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated SQLite database seeded with every subject's concept graph."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    load_all()
    yield
