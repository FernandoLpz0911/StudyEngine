"""User-adjustable settings, persisted in SQLite with engine.config as defaults.

config.py stays the env-overridable *default* layer; this module lets the learner
change the values that shape their own study rhythm (daily goal, new-concept pace)
from the UI without touching the environment. Unknown keys are rejected so the
settings surface stays a deliberate, documented set.
"""
from __future__ import annotations

from engine import config
from engine.db import dao

# key -> (default from config, type caster, human description, (min, max))
USER_SETTINGS: dict[str, tuple[object, type, str, tuple[float, float]]] = {
    "daily_goal": (
        config.DAILY_GOAL, int,
        "Items answered per day to fill the goal ring", (1, 500),
    ),
    "new_per_day": (
        config.NEW_PER_DAY, int,
        "Max brand-new concepts introduced per day (0 = reviews only)", (0, 100),
    ),
    "typed_answer_mastery": (
        config.TYPED_ANSWER_MASTERY, float,
        "Mastery above which generator problems switch to typed answers (1 disables)",
        (0.0, 1.0),
    ),
}


def get_int(key: str) -> int:
    return int(_get(key))


def get_float(key: str) -> float:
    return float(_get(key))


def _get(key: str) -> object:
    """Stored value if it parses and sits in range; the config default otherwise.

    The range check guards rows written before validation existed (or edited
    directly in SQLite) — they must not bypass what set_value now enforces.
    """
    default, caster, _, (lo, hi) = USER_SETTINGS[key]
    raw = dao.get_setting(key)
    if raw is None:
        return default
    try:
        cast = caster(raw)
    except ValueError:
        return default
    return cast if lo <= cast <= hi else default


def set_value(key: str, value: object) -> None:
    """Validate type and range, then persist; raises on unknown keys or bad values.

    Range matters: daily_goal=0 would auto-complete the overachiever quest and a
    negative new_per_day would silently freeze the frontier.
    """
    if key not in USER_SETTINGS:
        raise KeyError(f"unknown setting '{key}'")
    _, caster, _, (lo, hi) = USER_SETTINGS[key]
    cast = caster(value)
    if not lo <= cast <= hi:
        raise ValueError(f"'{key}' must be between {lo} and {hi}, got {cast}")
    dao.set_setting(key, str(cast))


def all_settings() -> list[dict]:
    """Every user setting with its current (possibly overridden) value."""
    return [
        {
            "key": key,
            "value": _get(key),
            "default": default,
            "description": desc,
        }
        for key, (default, _, desc, _) in USER_SETTINGS.items()
    ]
