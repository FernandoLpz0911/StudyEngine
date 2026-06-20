# StudyEngine

A multi-subject adaptive study tool. One shared engine — **FSRS spaced-repetition
scheduling** + a **concept graph** with prerequisites — drives every course. Each
subject plugs in as one of two modes:

- **Generator mode** — problems are produced algorithmically with closed-form
  answers and auto-graded, with a deterministic worked solution (no LLM). Used by
  **MATH 220 Differential Equations** (and ready for CS 480 normalization/SQL).
- **Recall mode** — flashcards (prompt → answer) self-graded into the same FSRS
  scheduler. Used by **MATH 250 Proofs**, **ECON 111 Freakonomics**, and the
  conceptual **CS 480** topics (ACID, 2PL, recovery, …).

## Courses included

| Subject key | Course | Mode | Status |
|---|---|---|---|
| `diffeq` | MATH 220 Differential Equations | generator | **full** — 4 generators, worked solutions |
| `databases` | CS 480 Database Systems | recall | starter cards (FD/normalization/SQL/ACID/2PL/WAL) |
| `proofs` | MATH 250 Intro to Advanced Maths | recall | starter cards (logic, techniques, sets, functions) |
| `econ` | ECON 111 Freakonomics | recall | starter cards (incentives, marginal, causation, …) |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Study a subject (progress persists in data/app.db between runs):
python -m engine.cli.study --subject diffeq --n 10
python -m engine.cli.study --subject proofs --n 10
python -m engine.cli.study --subject databases
python -m engine.cli.study --subject econ
```

In generator mode, answer with a letter (`a`–`d`) or type the value; you get the
worked solution either way. In recall mode, reveal the answer then rate yourself
`a`/`h`/`g`/`e` (again/hard/good/easy) — the rating schedules the next review.

## How it picks what to study

`engine/scheduler/policy.py` selects, per subject: overdue review cards first
(ranked by how much you've likely forgotten × exam weight), otherwise the
highest-weighted concept whose prerequisites you've already seen.

## Adding your own content

Edit the seed file for a subject under `data/subjects/<key>/concept_graph.seed.json`.
A concept is either a generator (`"generator": {"kind": ..., "params": {...}}`)
or a recall card (`"card": {"front": ..., "back": ...}`), with optional
`prerequisites` and `exam_weight`. Re-running the CLI re-seeds concepts without
wiping your review history.

To add a new **generator** subject, write generators in
`engine/subjects/<key>/` (register with `@register("kind")`) and point concepts
at them — see `engine/subjects/diffeq/` as the template.

## Tests

```bash
pytest          # answer-key correctness, FSRS, policy, seed loading, recall
ruff check engine tests
```

The MATH 220 answer keys are property-tested across many seeds: the generator, the
multiple-choice options, and the worked solution must all agree.
