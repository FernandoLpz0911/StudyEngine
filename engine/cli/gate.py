"""The study gate: python -m engine.cli.gate [--run | --dev | --status | ...].

Blocks the desktop until the day's quota of correct answers is paid, then gets
out of the way for the rest of the local day (ADR-0004, ADR-0005).

    --status      what the gate thinks right now; never touches the screen
    --dev         windowed, no grabs — safe to iterate on the UI
    --run         raise the gate for real if the quota is unpaid
    --repair      restore GNOME keybindings after an unclean death
    --install     autostart entry + systemd --user watchdog timer
    --uninstall   remove both, and restore keybindings

Every failure path here is fail-open: the desktop is handed back, a desktop
notification fires, and the reason lands in the log. A gate that cannot serve
questions must not hold the screen.
"""
from __future__ import annotations

import argparse
import atexit
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from engine import config
from engine.db import dao
from engine.db.seed import load_all
from engine.gate import keys, quota, server

_REPO = Path(__file__).resolve().parent.parent.parent
_SERVICE = "studygate"


def _state_dir() -> Path:
    path = keys.state_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')}  {message}"
    print(line, file=sys.stderr)
    try:
        with (_state_dir() / "gate.log").open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _notify(title: str, body: str) -> None:
    binary = shutil.which("notify-send")
    if binary:
        subprocess.run([binary, "-u", "critical", title, body], check=False)


def _acquire_singleton() -> object | None:
    """One gate at a time — autostart and the watchdog timer can race on login."""
    handle = (_state_dir() / "gate.lock").open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


_GDM_CONF = Path("/etc/gdm3/custom.conf")


def wayland_offered() -> bool | None:
    """Whether GDM would offer a Wayland session — the gate's one real bypass.

    The gate cannot cover a Wayland session, so a Wayland entry in the login
    screen's gear menu is a one-click way past it. `WaylandEnable=false` in GDM's
    config closes that. Returns None when the question can't be answered (no GDM,
    unreadable config) rather than guessing.
    """
    try:
        for raw in _GDM_CONF.read_text().splitlines():
            line = raw.strip()
            if line.startswith("#"):
                continue
            if line.replace(" ", "").lower() == "waylandenable=false":
                return False
    except OSError:
        return None
    return True


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY"))


def _session_is_x11() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"


def cmd_status(as_json: bool) -> int:
    load_all()
    state = quota.status()
    if as_json:
        print(json.dumps(state.as_dict(), indent=2))
        return 0
    verdict = "OPEN" if state.is_open else "CLOSED"
    print(f"gate: {verdict}  ({state.reason})")
    print(f"subject: {state.subject}")
    print(f"quota: {state.correct}/{state.quota} correct today — {state.remaining} to go")
    print(f"bails: {state.bails_left} of {state.bails_ration} left")
    if dao.raised_today():
        print("raised: already came up today — will not raise again until tomorrow")
    elif not state.is_open:
        print("raised: not yet today — the gate will come up")
    if state.exam_date:
        print(f"exam: {state.exam_date} ({state.days_left} days left)")
        pace = "on track" if state.coverage_on_track else "BEHIND"
        verdict = (
            "ready" if state.projected_score >= state.ready_target
            else "passing" if state.projection_passing
            else "NOT PASSING"
        )
        print(
            f"projected: {state.projected_score}/{state.questions_total} correct — "
            f"{verdict} (pass ~{state.pass_mark}, ready at {state.ready_target})"
        )
        print(
            f"pace: seen {state.concepts_seen}/{state.concepts_total} · "
            f"coverage {pace}"
        )
    else:
        print("exam: not set — run with --set-exam-date YYYY-MM-DD to arm the countdown")
    if keys.has_stale_snapshot():
        print("WARNING: stale keybinding snapshot — run --repair")
    if wayland_offered():
        print(
            "WARNING: GDM still offers Wayland — the gate cannot cover a Wayland\n"
            "         session, so that is a one-click bypass at the login screen.\n"
            f"         Set WaylandEnable=false under [daemon] in {_GDM_CONF}."
        )
    return 0


def cmd_reset_bails() -> int:
    load_all()
    removed = dao.reset_bails()
    print(f"cleared {removed} bail record(s) — {quota.bails_left()} available again")
    return 0


def cmd_repair() -> int:
    restored = keys.restore()
    print(f"restored {restored} keybinding(s)" if restored else "nothing to repair")
    return 0


def cmd_run(dev: bool, max_seconds: float | None) -> int:
    load_all()
    state = quota.status()
    if not dev and not quota.should_raise():
        reason = state.reason if state.is_open else "already raised today"
        _log(f"not raising the gate ({reason})")
        return 0

    if not dev:
        if not _has_display():
            _log("no DISPLAY — not a graphical session, skipping")
            return 0
        if not _session_is_x11():
            _log("session is not X11; the gate cannot cover a Wayland session")
            _notify("StudyGate inactive", "Wayland session — log in on Xorg for the gate.")
            return 1

    lock = _acquire_singleton()
    if lock is None:
        _log("another gate already holds the lock — exiting")
        return 0

    try:
        from engine.gate.window import GateWindow
    except Exception as exc:  # PyGObject / typelib missing
        _log(f"cannot load the window layer: {exc}")
        _notify("StudyGate failed", "PyGObject/WebKit unavailable — gate did not start.")
        return 1

    if not server.port_is_free(config.GATE_PORT):
        _log(f"port {config.GATE_PORT} busy — refusing to trust a server I did not start")
        _notify("StudyGate failed", f"Port {config.GATE_PORT} is in use.")
        return 1
    server.start(config.GATE_PORT)
    if not server.wait_until_ready(config.GATE_PORT, timeout=25.0):
        _log("private server never came up")
        _notify("StudyGate failed", "Study server did not start — desktop left unlocked.")
        return 1

    cleaned = {"done": False}

    def cleanup() -> None:
        if cleaned["done"]:
            return
        cleaned["done"] = True
        if not dev:
            keys.restore()

    atexit.register(cleanup)

    url = f"http://127.0.0.1:{config.GATE_PORT}/?gate=1"
    def on_grabbed() -> None:
        # Only once the gate actually holds the screen does it count as today's
        # raise. A gate that never got that far — grab refused, page dead — leaves
        # no record, so the watchdog is free to try again rather than the learner
        # silently losing a day to a bug (ADR-0006).
        dao.record_raise()
        cleared = keys.neutralize()
        _log(f"gate up — {state.remaining} correct to go; {cleared} keybinding(s) cleared")

    gate = GateWindow(
        url,
        is_paid=lambda: quota.status().is_open,
        grab=not dev,
        deadman_seconds=config.GATE_DEADMAN_SEC,
        max_seconds=max_seconds,
        on_release=cleanup,
        on_grabbed=None if dev else on_grabbed,
    )

    def on_signal(_signum, _frame) -> None:
        gate.release("signal")

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    failure = gate.run()
    cleanup()

    if failure:
        _log(f"gate failed open: {failure}")
        _notify("StudyGate failed", f"{failure} — desktop released.")
        return 1
    _log("gate released")
    return 0


def _unit_files() -> dict[Path, str]:
    python = sys.executable
    run = f"{python} -m engine.cli.gate --run"
    systemd = Path.home() / ".config" / "systemd" / "user"
    autostart = Path.home() / ".config" / "autostart"
    return {
        autostart / f"{_SERVICE}.desktop": (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=StudyGate\n"
            "Comment=Block the desktop until today's study quota is paid\n"
            f"Exec={run}\n"
            f"Path={_REPO}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Phase=Applications\n"
        ),
        systemd / f"{_SERVICE}.service": (
            "[Unit]\n"
            "Description=StudyGate — raise the study gate if today's quota is unpaid\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"WorkingDirectory={_REPO}\n"
            f"ExecStart={run}\n"
        ),
        systemd / f"{_SERVICE}.timer": (
            "[Unit]\n"
            "Description=StudyGate watchdog\n\n"
            "[Timer]\n"
            "OnStartupSec=2min\n"
            f"OnUnitActiveSec={config.GATE_WATCHDOG_MIN}min\n"
            "AccuracySec=30s\n"
            "Persistent=true\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        ),
    }


def _systemctl(*args: str) -> None:
    binary = shutil.which("systemctl")
    if binary:
        subprocess.run([binary, "--user", *args], check=False)


def cmd_install() -> int:
    try:
        import engine.gate.window  # noqa: F401  (resolves the system PyGObject too)
    except Exception as exc:
        print(f"The gate's window layer will not load:\n  {exc}", file=sys.stderr)
        return 1
    for path, body in _unit_files().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        print(f"wrote {path}")
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", f"{_SERVICE}.timer")
    print(
        f"\nStudyGate armed. Watchdog every {config.GATE_WATCHDOG_MIN} min, plus login.\n"
        f"Escape hatch: Ctrl+Alt+F2, then `pkill -f 'engine.cli.gate'`.\n"
        f"Turn it off with: python -m engine.cli.gate --uninstall"
    )
    return 0


def cmd_uninstall() -> int:
    _systemctl("disable", "--now", f"{_SERVICE}.timer")
    for path in _unit_files():
        if path.exists():
            path.unlink()
            print(f"removed {path}")
    _systemctl("daemon-reload")
    restored = keys.restore()
    if restored:
        print(f"restored {restored} keybinding(s)")
    print("StudyGate disarmed.")
    return 0


def cmd_set_exam_date(iso: str) -> int:
    load_all()
    try:
        dao.set_exam_date(config.GATE_SUBJECT, iso)
    except ValueError:
        print(f"bad date '{iso}' — want YYYY-MM-DD", file=sys.stderr)
        return 2
    state = quota.status()
    print(f"exam for {config.GATE_SUBJECT} set to {iso} ({state.days_left} days away)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Study gate — block the desktop until the day's quota is paid."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true", help="raise the gate for real")
    mode.add_argument("--dev", action="store_true", help="windowed, no grabs")
    mode.add_argument("--status", action="store_true", help="report and exit")
    mode.add_argument("--repair", action="store_true", help="restore keybindings")
    mode.add_argument(
        "--reset-bails", action="store_true", help="clear bail history, restore the ration"
    )
    mode.add_argument("--install", action="store_true", help="arm autostart + watchdog")
    mode.add_argument("--uninstall", action="store_true", help="disarm everything")
    mode.add_argument(
        "--set-exam-date",
        metavar="YYYY-MM-DD",
        help=f"set the exam the gate serves (subject: {config.GATE_SUBJECT})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable --status")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="self-release after N seconds — use this the first time you arm it",
    )
    args = parser.parse_args()

    if args.set_exam_date:
        raise SystemExit(cmd_set_exam_date(args.set_exam_date))
    if args.status:
        raise SystemExit(cmd_status(args.json))
    if args.repair:
        raise SystemExit(cmd_repair())
    if args.reset_bails:
        raise SystemExit(cmd_reset_bails())
    if args.install:
        raise SystemExit(cmd_install())
    if args.uninstall:
        raise SystemExit(cmd_uninstall())
    raise SystemExit(cmd_run(dev=args.dev, max_seconds=args.max_seconds))


if __name__ == "__main__":
    main()
