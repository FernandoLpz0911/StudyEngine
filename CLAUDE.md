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

Generator subjects register both `generators.py` (kinds) and `solve.py`
(worked-solution steps) via central `engine.feedback.solve` registry.

## Hard constraints

- **Local-first.** Pure Python + SQLite; no cloud services, no LLM in core.
- **Answers computed, never improvised.** Generator and its worked solution
  (`engine/subjects/<key>/solve.py`) share one closed-form computation — shown solution cannot diverge from graded answer.
- **Reproducibility.** Generators take explicit `seed`; seed + params logged with every interaction.

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
- **Tests first for math:** new generator needs answer-key test that
  independently recomputes answer across many seeds (see `tests/test_diffeq.py`).
- Pure functions for math (FSRS curve, generator answers) — unit-testable.
- No section-divider comments; prefer self-documenting names. Comments for
  *why* only (derivations, non-obvious choices).

## Adding a subject

- recall: add `data/subjects/<key>/concept_graph.seed.json` with `card` nodes
  (`question`, `answer`, `distractors`), register in
  `engine/subjects/__init__.py` SUBJECTS.
- generator: also add `engine/subjects/<key>/generators.py` (`@register("kind")`)
  and `solve.py`, import in `engine/subjects/__init__.py`, point concepts at
  kinds. Mirror `engine/subjects/diffeq/`.