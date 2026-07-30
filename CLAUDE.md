# CLAUDE.md — Project Context for Claude Code

> Read at session start. Keep current.

## What this is

**Multi-subject adaptive study engine**. One shared core (FSRS spaced repetition
+ prerequisite concept graph + SQLite persistence) serves several university
courses, each plugged in as **subject module** in one of two modes:

- **generator** — algorithmic problems, closed-form answers, auto-graded, deterministic worked solution. No LLM in loop.
- **recall** — objective multiple-choice items (question + correct answer + distractors), auto-graded against key.

**Grading data-based only — no self-rating.** Correctness from computed key; FSRS grade derived from correctness + response time
(`engine/grading.derive_grade`).

Sibling project `../LearningModel` = single-subject ancestor (SOA Exam P);
this generalizes its architecture to many subjects.

## Subjects

| key | course | mode |
|---|---|---|
| `diffeq` | MATH 220 Differential Equations | generator |
| `databases` | CS 480 Database Systems | generator (FD/normalization) + recall |
| `proofs` | MATH 215 Introduction to Proofs | generator (logic, number theory, sets, functions, counting, floor) + recall |
| `econ` | ECON 111 Freakonomics | generator (decision math) + recall |

Generator subjects register `generators.py` (kinds). Each generator produces its
own worked solution on `Problem.explain` (ADR-0003). Legacy `solve.py` files
(central `engine.feedback.solve` registry) still back the not-yet-migrated
subjects; `build_item` prefers `Problem.explain` and falls back to the registry.
Migrated: `databases`. Remaining on the registry: `diffeq`, `econ`, `examfm`,
`proofs`, `examp`.

## Hard constraints

- **Local-first.** Pure Python + SQLite; no cloud services, no LLM in core.
- **Answers computed, never improvised.** A generator and its worked solution
  (`Problem.explain`) share one closed-form computation in the same function, so the
  shown solution cannot diverge from the graded answer. (Unmigrated subjects still
  split this across `solve.py` — being retired per ADR-0003.)
- **Reproducibility.** Generators take explicit `seed`; seed + params logged with every interaction.

## Layout

```
engine/
  config.py             runtime config (env-overridable defaults)
  settings.py           user-adjustable settings (SQLite `setting` table over config defaults)
  db/                   connection (closing ctx-manager), schema.sql, dao, seed
  scheduler/            fsrs_core (pure), store (py-fsrs), policy (next concept),
                        optimize (personal FSRS weight fit: engine.cli.fsrs_fit)
  generation/base.py    Problem (carries explain) + @register registry + make_mc_choices
  feedback/solve.py     legacy worked-solution registry (retiring, ADR-0003)
  subjects/             registry (SUBJECTS) + per-subject generators
    databases/          generators.py (explain inline)  ← template for generator subjects
    diffeq/             generators.py, solve.py         ← legacy split (unmigrated)
  recall/cards.py       flashcard model for recall subjects
  grading.py            numeric/string answer grading
  gate/                 study gate: quota + schedule (pure), keys + window (desktop)
  cli/study.py          interactive study loop (python -m engine.cli.study)
  cli/gate.py           study gate (python -m engine.cli.gate --status/--run/--install)
data/subjects/<key>/concept_graph.seed.json   concept graph + content per subject
tests/                  answer-key correctness, FSRS, policy, seed, recall
```

## Study gate

Blocks the whole X11 desktop until the day's quota of **correct** answers in
`GATE_SUBJECT` is paid, then stays out of the way for the rest of the local day.
Quota is the `daily_goal` number read against correct answers — the goal ring
still counts answers settled, so the two legitimately disagree (ADR-0005).

Runs as the user with no root: `Gtk.WindowType.POPUP` (override-redirect) +
`Gdk.Seat.grab`, with GNOME's compositor shortcuts snapshotted to disk and
cleared while it is up. Ctrl+Alt+F2 and SSH stay open on purpose, and every
failure path releases the desktop rather than blocking on a bug (ADR-0004).

- Needs the system GTK bindings — `python3-gi`, `gir1.2-webkit2-4.1` from apt.
  PyGObject is not pip-installable into a venv, so `gate/window.py` locates the
  distro copy and appends it to `sys.path` (append, never prepend — venv packages
  keep priority). No symlink to maintain; survives a venv rebuild.
  `engine/gate/{quota,schedule}.py` import none of it, so the whole decision is
  tested headlessly in `tests/test_gate.py`.
- X11 only — a Wayland session has no gate, which makes the login screen's
  session picker the one real bypass. `WaylandEnable=false` under `[daemon]` in
  `/etc/gdm3/custom.conf` closes it; `--status` warns when it is not set.
- `--dev` for a windowed no-grab run; Xephyr (`DISPLAY=:2`) contains grab
  testing; `--max-seconds` self-releases. Never debug grabs on a live session.
- `--repair` restores keybindings after an unclean death; a stale snapshot on
  disk is also replayed automatically by the next run.

## Conventions

- Type hints everywhere; `ruff` (line-length 100) clean; `pytest` green.
- **Tests first for math:** new generator needs answer-key test that
  independently recomputes answer across many seeds (see `tests/test_diffeq.py`).
- Pure functions for math (FSRS curve, generator answers) — unit-testable.
- No section-divider comments; prefer self-documenting names. Comments for
  *why* only (derivations, non-obvious choices).

## Adding a subject

- recall: add `data/subjects/<key>/concept_graph.seed.json` with `card` nodes
  (`question`, `answer`, `distractors`), register in
  `engine/subjects/__init__.py` SUBJECTS.
- generator: also add `engine/subjects/<key>/generators.py` (`@register("kind")`),
  each generator building its worked steps on `Problem.explain` from the same
  computation as the answer; import in `engine/subjects/__init__.py`, point concepts
  at kinds. Mirror `engine/subjects/databases/`. (No `solve.py` — that is the legacy
  path, ADR-0003.)