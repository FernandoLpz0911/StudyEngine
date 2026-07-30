# 4. The study gate blocks at user level and fails open

Date: 2026-07-29

## Status

Accepted

## Context

The learner wants to be *forced* to study before using their laptop, with an
overlay covering everything, ahead of a fixed SOA Exam P sitting on
2026-09-21 13:00. "Cover everything" on this machine is achievable — the session
is X11 (`XDG_SESSION_TYPE=x11`, Ubuntu GNOME on Xorg), where an
override-redirect window plus `XGrabKeyboard`/`XGrabPointer` genuinely covers the
desktop. The same design is not portable to Wayland, where no unprivileged client
can do this.

The strength question is where the real risk lives. Stronger enforcement is
available — a system service gating GDM, VT switching disabled, a PAM module
refusing login until the quota is paid — and each step up moves the failure mode
from "the gate is bypassable" to "the laptop is unusable". That trade is being
made 54 days before an exam, on the only machine available to prepare for it.

## Decision

The gate runs **as the learner's own user, never as root**, and holds the desktop
with X grabs plus a temporary rewrite of GNOME's compositor-level keybindings. VT
switching (`Ctrl+Alt+F2`) and SSH are left working *on purpose*: they are the
escape hatch, awkward enough to be friction rather than a door.

The gate **fails open, loudly**. Any startup or runtime failure it cannot recover
from — server won't bind, database locked, WebKit won't load, X grab refused —
releases the grabs, restores keybindings, fires a `notify-send`, logs, and exits
non-zero. The watchdog retries on its next tick.

Two consequences of user-level operation are handled explicitly rather than
assumed away:

- **Keybindings are snapshotted to disk before being cleared**, not held in
  memory. A `kill -9` or a crash therefore leaves a recoverable state: the next
  gate start sees a stale snapshot and restores it before doing anything else,
  and `--repair` does the same by hand.
- **A deadman timer** self-kills the gate if it stops responding while holding
  the grabs. A live process holding a keyboard grab it cannot service is a
  keyboard that does nothing in any window — recoverable only by TTY or a hard
  power-off.

## Considered options

- **System service gating the greeter (needs root)** — rejected: escapable only
  via recovery mode or a live USB, which is the wrong ratio of enforcement to
  blast radius for a two-month deadline.
- **PAM gate** — rejected: a bug in the login path locks the learner out of the
  machine they need for the exam.
- **Fail closed** — rejected for the same reason. A gate that blocks when it is
  broken converts every bug into a bricked laptop, and the bug that matters will
  happen on a morning with no time to debug it.

## Consequences

- The gate is bypassable by anyone who knows `Ctrl+Alt+F2` and `pkill` — which is
  the learner. This is accepted: the design buys friction and habit, not
  imprisonment, and pretending otherwise would trade a real risk for a fake
  guarantee.
- The gate is X11-only, so the login screen's session picker is its one real
  bypass: a Wayland session simply has no gate. Nothing user-level can fix that,
  because no unprivileged Wayland client can cover the screen or grab the
  keyboard. It is closed one level up instead, by `WaylandEnable=false` under
  `[daemon]` in `/etc/gdm3/custom.conf`, which stops GDM offering Wayland
  sessions at all. That setting is outside this repo's control, so `--status`
  reads it back and warns when it is missing rather than assuming.
- Loud failure means notification spam when something is persistently broken.
  Preferred over a gate that silently stops working and is discovered a week
  later.
