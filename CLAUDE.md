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
- generator: also add `engine/subjects/<key>/generators.py` (`@register("kind")`),
  each generator building its worked steps on `Problem.explain` from the same
  computation as the answer; import in `engine/subjects/__init__.py`, point concepts
  at kinds. Mirror `engine/subjects/databases/`. (No `solve.py` — that is the legacy
  path, ADR-0003.)