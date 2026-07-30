"""The screen-covering half of the gate: GTK window, seat grab, deadman.

Only this module and `keys` touch the desktop. It is imported lazily so the rest
of the gate — and the test suite — runs with no display and no PyGObject.

Two properties matter more than anything else here:

- **The grab dies with the process.** X releases every grab held by a client when
  that client disconnects, so `os._exit` is a complete release. The deadman
  therefore does not need a working GTK main loop to free the keyboard, which is
  precisely the situation it exists for.
- **Failure is open.** Anything that stops the gate doing its job releases the
  desktop and says so, rather than leaving a half-gate that blocks input but
  serves no questions (ADR-0004).
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path


def _ensure_gi_importable() -> None:
    """Fall back to the distro's PyGObject when the venv has no copy of its own.

    PyGObject is an apt package, not a pip one, so a venv built with the usual
    `python -m venv` cannot see it and the gate dies on import. Rather than
    depend on someone having symlinked it in — which silently breaks the next
    time the venv is rebuilt — locate the system copy and append (never prepend)
    its directory, so venv packages still win every other name.

    The bindings are compiled per Python minor version, so a venv on a different
    minor than the system interpreter cannot borrow them; say so plainly instead
    of failing later with an opaque ABI error.
    """
    try:
        import gi  # noqa: F401
        return
    except ImportError:
        pass
    version = f"python3.{sys.version_info.minor}"
    for candidate in (
        Path("/usr/lib/python3/dist-packages"),
        Path(f"/usr/lib/{version}/dist-packages"),
        Path(f"/usr/lib/{version}/site-packages"),
    ):
        if (candidate / "gi").is_dir():
            sys.path.append(str(candidate))
            return
    raise ImportError(
        "PyGObject not found. Install it with:\n"
        "  sudo apt install python3-gi gir1.2-webkit2-4.1\n"
        f"(this interpreter is {sys.version.split()[0]}; the apt bindings are "
        "built for the system Python, so the two minor versions must match)"
    )


_ensure_gi_importable()

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:  # older Ubuntu ships the 4.0 typelib
    gi.require_version("WebKit2", "4.0")

from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

GRAB_RETRY_SECONDS = 20.0
POLL_SECONDS = 2


class GateWindow:
    """A window that covers every monitor and holds the seat until released."""

    def __init__(
        self,
        url: str,
        is_paid: Callable[[], bool],
        *,
        grab: bool = True,
        deadman_seconds: float = 20.0,
        max_seconds: float | None = None,
        on_release: Callable[[], None] | None = None,
        on_grabbed: Callable[[], None] | None = None,
    ) -> None:
        self.url = url
        self.is_paid = is_paid
        self.grab_wanted = grab
        self.deadman_seconds = deadman_seconds
        self.max_seconds = max_seconds
        self.on_release = on_release
        self.on_grabbed = on_grabbed
        self.failure: str | None = None
        self._seat: Gdk.Seat | None = None
        self._released = False
        self._heartbeat = time.monotonic()
        self._started = time.monotonic()

        # POPUP is override-redirect: the window manager neither decorates it,
        # stacks it, nor lets anything else be raised over it by user action.
        kind = Gtk.WindowType.POPUP if grab else Gtk.WindowType.TOPLEVEL
        self.window = Gtk.Window(type=kind)
        self.window.set_title("StudyGate")
        self.window.set_keep_above(True)
        self.window.set_decorated(False)
        self.window.connect("delete-event", lambda *_: True)  # no close button path

        self.view = WebKit2.WebView()
        self.view.load_uri(self.url)
        self.view.connect("load-failed", self._on_load_failed)
        self.window.add(self.view)

        if grab:
            self.window.stick()  # follow the learner across every workspace
            self._cover_all_monitors()
            screen = self.window.get_screen()
            if screen is not None:
                screen.connect("monitors-changed", lambda *_: self._cover_all_monitors())
        else:
            self.window.set_default_size(1100, 800)

    def _cover_all_monitors(self) -> None:
        """Size to the union of every monitor, so a second screen is covered too."""
        display = Gdk.Display.get_default()
        if display is None:
            return
        rects = [
            display.get_monitor(i).get_geometry() for i in range(display.get_n_monitors())
        ]
        if not rects:
            return
        left = min(r.x for r in rects)
        top = min(r.y for r in rects)
        right = max(r.x + r.width for r in rects)
        bottom = max(r.y + r.height for r in rects)
        self.window.move(left, top)
        self.window.resize(right - left, bottom - top)

    def _on_load_failed(self, _view, _event, _uri, error) -> bool:
        self.fail(f"page failed to load: {error.message}")
        return True

    def _try_grab(self) -> bool:
        display = Gdk.Display.get_default()
        gdk_window = self.window.get_window()
        if display is None or gdk_window is None:
            return False
        seat = display.get_default_seat()
        status = seat.grab(
            gdk_window, Gdk.SeatCapabilities.ALL, True, None, None, None, None
        )
        if status == Gdk.GrabStatus.SUCCESS:
            self._seat = seat
            return True
        return False

    def _grab_with_retry(self) -> None:
        """Keep trying to take the seat; another client may hold it transiently.

        At login, GNOME Shell itself often holds a grab for a second or two. Only
        a sustained failure is fatal — a gate that cannot take the keyboard is a
        gate the learner can type straight past, so we do not pretend otherwise.
        """
        deadline = time.monotonic() + GRAB_RETRY_SECONDS

        def attempt() -> bool:
            if self._released:
                return False
            if self._try_grab():
                # The gate is genuinely holding the screen now. Anything recorded
                # here — notably "the gate raised today" — is recorded because it
                # actually happened, not merely because it was attempted.
                if self.on_grabbed is not None:
                    self.on_grabbed()
                return False
            if time.monotonic() > deadline:
                self.fail("could not grab keyboard/pointer — another client holds it")
                return False
            return True  # try again on the next tick

        GLib.timeout_add(250, attempt)

    def _tick(self) -> bool:
        if self._released:
            return False
        self._heartbeat = time.monotonic()

        if self.max_seconds and time.monotonic() - self._started > self.max_seconds:
            self.release("time limit reached (--max-seconds)")
            return False
        try:
            if self.is_paid():
                self.release("quota paid")
                return False
        except Exception as exc:  # a gate that cannot read the quota must not block
            self.fail(f"could not read gate status: {exc}")
            return False

        gdk_window = self.window.get_window()
        if gdk_window is not None:
            gdk_window.raise_()  # stay above anything that mapped itself since
        return True

    def _start_deadman(self) -> None:
        """Kill the process if the main loop stops servicing its own timer.

        A live process holding the seat grab but not running is a keyboard that
        does nothing in any window. Exiting hands the grab back to X, so this
        path needs nothing from GTK and works precisely when GTK is the problem.
        """

        def watch() -> None:
            while not self._released:
                time.sleep(1.0)
                if time.monotonic() - self._heartbeat > self.deadman_seconds:
                    try:
                        from engine.gate import keys

                        keys.restore()
                    finally:
                        os._exit(3)

        threading.Thread(target=watch, name="gate-deadman", daemon=True).start()

    def fail(self, message: str) -> None:
        """Give the desktop back and record why — the fail-open path."""
        self.failure = message
        self.release(f"failed: {message}")

    def release(self, _why: str = "") -> None:
        if self._released:
            return
        self._released = True
        if self._seat is not None:
            self._seat.ungrab()
            self._seat = None
        if self.on_release is not None:
            self.on_release()
        self.window.hide()
        Gtk.main_quit()

    def run(self) -> str | None:
        """Show the gate and block until it is released. Returns a failure, if any."""
        self.window.show_all()
        if self.grab_wanted:
            self._grab_with_retry()
            self._start_deadman()
        GLib.timeout_add_seconds(POLL_SECONDS, self._tick)
        Gtk.main()
        return self.failure
