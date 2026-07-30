"""The study gate: a full-screen block held until the day's quota is paid.

Split so that everything worth testing is testable without a display. `quota` and
`schedule` are pure decision logic over the database and the clock; `keys` and
`window` are the desktop-facing half and are the only modules that need PyGObject,
X11 or GNOME. Importing this package pulls in none of them.
"""
