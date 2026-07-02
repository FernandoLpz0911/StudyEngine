"""User-adjustable settings, persisted in SQLite with engine.config as defaults.

config.py stays the env-overridable *default* layer; this module lets the learner
change the values that shape their own study rhythm (daily goal, new-concept pace)
from the UI without touching the environment. Unknown keys are rejected so the
settings surface stays a deliberate, documented set.
"""
from __future__ import annotations

from engine import config
from engine.db import dao

# key -> (default from config, type caster, human description)
USER_SETTINGS: dict[str, tuple[object, type, str]] = {
    "daily_goal": (config.DAILY_GOAL, int, "Items answered per day to fill the goal ring"),
    "new_per_day": (config.NEW_PER_DAY, int, "Max brand-new concepts introduced per day"),
    "typed_answer_mastery": (
        config.TYPED_ANSWER_MASTERY, float,
        "Mastery above which generator problems switch to typed answers (1 disables)",
    ),
}


def get_int(key: str) -> int:
    return int(_get(key))


def get_float(key: str) -> float:
    return float(_get(key))


def _get(key: str) -> object:
    default, caster, _ = USER_SETTINGS[key]
    raw = dao.get_setting(key)
    if raw is None:
        return default
    try:
        return caster(raw)
    except ValueError:
        return default


def set_value(key: str, value: object) -> None:
    """Validate against the declared type and persist; raises on unknown keys."""
    if key not in USER_SETTINGS:
        raise KeyError(f"unknown setting '{key}'")
    _, caster, _ = USER_SETTINGS[key]
    dao.set_setting(key, str(caster(value)))


def all_settings() -> list[dict]:
    """Every user setting with its current (possibly overridden) value."""
    return [
        {
            "key": key,
            "value": _get(key),
            "default": default,
            "description": desc,
        }
        for key, (default, _, desc) in USER_SETTINGS.items()
    ]
