"""Temporarily disarm GNOME's compositor-level shortcuts while the gate is up.

X seat grabs are not enough on their own: GNOME Shell binds Super, Alt+Tab,
Alt+F2 and Ctrl+Alt+T above any ordinary client, so those keys act on the desktop
behind the gate rather than reaching it.

The snapshot is written to disk *before* anything is cleared, so an unclean death
— `kill -9`, an X crash, a power cut — leaves a recoverable state rather than a
desktop with no shortcuts. Any later run repairs it before doing anything else
(ADR-0004).

Deliberately left alone: volume, brightness, screenshots, power/suspend, screen
lock, and VT switching. None of them dismiss the gate, and taking away the power
and volume keys punishes the learner without enforcing anything.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

_WM = "org.gnome.desktop.wm.keybindings"
_SHELL = "org.gnome.shell.keybindings"
_MUTTER = "org.gnome.mutter"
_MUTTER_KB = "org.gnome.mutter.keybindings"
_MEDIA = "org.gnome.settings-daemon.plugins.media-keys"

_WORKSPACE_KEYS = [
    f"{prefix}-{suffix}"
    for prefix in ("switch-to-workspace", "move-to-workspace")
    for suffix in [*(str(n) for n in range(1, 13)), "left", "right", "up", "down", "last"]
]

# (schema, key) pairs cleared while the gate holds the screen. Missing keys are
# skipped at runtime, so this list stays valid across GNOME versions.
MANAGED: list[tuple[str, str]] = [
    *((_WM, k) for k in _WORKSPACE_KEYS),
    *(
        (_WM, k)
        for k in (
            "switch-applications",
            "switch-applications-backward",
            "switch-windows",
            "switch-windows-backward",
            "switch-group",
            "switch-group-backward",
            "switch-panels",
            "switch-panels-backward",
            "cycle-windows",
            "cycle-windows-backward",
            "cycle-group",
            "cycle-group-backward",
            "cycle-panels",
            "cycle-panels-backward",
            "panel-run-dialog",
            "panel-main-menu",
            "show-desktop",
            "minimize",
            "close",
            "begin-move",
            "begin-resize",
            "lower",
            "raise",
            "raise-or-lower",
            "toggle-fullscreen",
            "toggle-maximized",
            "unmaximize",
            "activate-window-menu",
            "switch-input-source",
            "switch-input-source-backward",
        )
    ),
    *(
        (_SHELL, k)
        for k in (
            "toggle-overview",
            "toggle-application-view",
            "toggle-message-tray",
            "toggle-quick-settings",
            "focus-active-notification",
            "shift-overview-up",
            "shift-overview-down",
            *(f"switch-to-application-{n}" for n in range(1, 10)),
            *(f"open-new-window-application-{n}" for n in range(1, 10)),
        )
    ),
    (_MUTTER, "overlay-key"),  # the bare Super press that opens Activities
    (_MUTTER, "locate-pointer-key"),
    *((_MUTTER_KB, k) for k in ("switch-monitor", "rotate-monitor", "cancel-input-capture")),
    *(
        (_MEDIA, k)
        for k in (
            "terminal",
            "control-center",
            "logout",
            "search",
            "www",
            "home",
            "email",
            "calculator",
            "help",
            "on-screen-keyboard",
        )
    ),
]

_CUSTOM_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "studygate"


def snapshot_path() -> Path:
    return state_dir() / "keys.json"


def _gsettings(*args: str) -> str | None:
    """Run gsettings, returning stdout or None when the key/schema is absent."""
    try:
        done = subprocess.run(
            ["gsettings", *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _get(schema: str, key: str) -> str | None:
    return _gsettings("get", schema, key)


def _set(schema: str, key: str, value: str) -> bool:
    return _gsettings("set", schema, key, value) is not None


def _empty_for(value: str) -> str:
    """The 'no binding' literal matching the GVariant type we just read.

    Inferred from the serialised value rather than a hand-kept type table. A
    populated array prints as `['<Super>a']`, a plain string as `'Super_L'` — and
    an *already empty* array prints with its type annotation, `@as []`, which is
    why the `@a` prefix has to count as an array too. Getting this wrong means
    setting `''` on an array key, which gsettings rejects and we would skip.
    """
    return "[]" if value.startswith(("[", "@a")) else "''"


def _custom_binding_targets() -> list[tuple[str, str]]:
    """User-defined shortcuts, as (schema:path, key) — any one could be an exit."""
    raw = _get(_MEDIA, "custom-keybindings")
    if not raw or raw.startswith("@as []") or raw == "[]":
        return []
    paths = [p.strip().strip("'\"") for p in raw.strip("[]").split(",") if p.strip()]
    return [(f"{_CUSTOM_SCHEMA}:{p}", "binding") for p in paths if p]


def _targets() -> list[tuple[str, str]]:
    return [*MANAGED, *_custom_binding_targets()]


def has_stale_snapshot() -> bool:
    return snapshot_path().exists()


def restore() -> int:
    """Put every snapshotted binding back and drop the snapshot. Idempotent."""
    path = snapshot_path()
    if not path.exists():
        return 0
    try:
        saved: dict[str, str] = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return 0
    restored = 0
    for ident, value in saved.items():
        schema, _, key = ident.rpartition(" ")
        if schema and _set(schema, key, value):
            restored += 1
    path.unlink(missing_ok=True)
    return restored


def neutralize() -> int:
    """Snapshot the managed bindings to disk, then clear them. Returns count cleared.

    A stale snapshot means a previous gate died without restoring; it is replayed
    first so we never snapshot the *cleared* state over the real one and make the
    damage permanent.
    """
    restore()
    state_dir().mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}
    for schema, key in _targets():
        current = _get(schema, key)
        if current is not None:
            saved[f"{schema} {key}"] = current

    path = snapshot_path()
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as fh:
        json.dump(saved, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)  # atomic: the snapshot exists in full before anything is cleared

    cleared = 0
    for ident, value in saved.items():
        schema, _, key = ident.rpartition(" ")
        if _set(schema, key, _empty_for(value)):
            cleared += 1
    return cleared
