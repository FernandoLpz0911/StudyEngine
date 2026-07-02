# CLAUDE.md — Project Context for Claude Code

> Read at the start of every session. Keep current.

## What this is

A **multi-subject adaptive study engine**. One shared core (FSRS spaced repetition
+ a prerequisite concept graph + SQLite persistence) serves several university
courses, each plugged in as a **subject module** in one of two modes:

- **generator** — algorithmic problems with closed-form answers, auto-graded, with
  a deterministic worked solution. No LLM in the loop.
- **recall** — objective multiple-choice items (question + correct answer +
  distractors), auto-graded against the key.

**Grading is data-based only — no self-rating.** Correctness comes from a computed
key; the FSRS grade is derived from correctness + response time
(`engine/grading.derive_grade`).

Sibling project `../LearningModel` is the single-subject ancestor (SOA Exam P);
this generalizes its architecture to many subjects.

## Subjects

| key | course | mode |
|---|---|---|
| `diffeq` | MATH 220 Differential Equations | generator |
| `databases` | CS 480 Database Systems | generator (FD/normalization) + recall |
| `proofs` | MATH 215 Introduction to Proofs | generator (logic, number theory, sets, functions, counting, floor) + recall |
| `econ` | ECON 111 Freakonomics | generator (decision math) + recall |

Generator subjects register both a `generators.py` (kinds) and a `solve.py`
(worked-solution steps) via the central `engine.feedback.solve` registry.

## Hard constraints

- **Local-first.** Pure Python + SQLite; no cloud services, no LLM in the core.
- **Answers are computed, never improvised.** A generator and its worked solution
  (`engine/subjects/<key>/solve.py`) share one closed-form computation, so the
  shown solution cannot diverge from the graded answer.
- **Reproducibility.** Generators take an explicit `seed`; the seed and params are
  logged with every interaction.

## Layout

```
engine/
  config.py             runtime config (env-overridable defaults)
  settings.py           user-adjustable settings (SQLite `setting` table over config defaults)
  db/                   connection (closing ctx-manager), schema.sql, dao, seed
  scheduler/            fsrs_core (pure), store (py-fsrs), policy (next concept),
                        optimize (personal FSRS weight fit: engine.cli.fsrs_fit)
  generation/base.py    Problem + @register registry + make_mc_choices
  subjects/             registry (SUBJECTS) + per-subject generators/solve
    diffeq/             generators.py, solve.py   ← template for generator subjects
  recall/cards.py       flashcard model for recall subjects
  grading.py            numeric/string answer grading
  cli/study.py          interactive study loop (python -m engine.cli.study)
data/subjects/<key>/concept_graph.seed.json   concept graph + content per subject
tests/                  answer-key correctness, FSRS, policy, seed, recall
```

## Conventions

- Type hints everywhere; `ruff` (line-length 100) clean; `pytest` green.
- **Tests first for math:** any new generator needs an answer-key test that
  independently recomputes the answer across many seeds (see `tests/test_diffeq.py`).
- Pure functions for the math (FSRS curve, generator answers) so they're unit-testable.
- No section-divider comments; prefer self-documenting names. Keep comments for the
  *why* (derivations, non-obvious choices).

## Adding a subject

- recall: add `data/subjects/<key>/concept_graph.seed.json` with `card` nodes
  (`question`, `answer`, `distractors`) and register it in
  `engine/subjects/__init__.py` SUBJECTS.
- generator: also add `engine/subjects/<key>/generators.py` (`@register("kind")`)
  and `solve.py`, import it in `engine/subjects/__init__.py`, and point concepts at
  the kinds. Mirror `engine/subjects/diffeq/`.
