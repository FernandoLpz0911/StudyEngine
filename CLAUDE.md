# CLAUDE.md — Project Context for Claude Code

> Read at session start. Keep current.

## What this is

**Multi-subject adaptive study engine**. One shared core (FSRS spaced repetition + prereq concept graph + SQLite persist) serve many uni course. Each plug in as **subject module**, one of two mode:

- **generator** — algo problem, closed-form answer, auto-grade, deterministic worked solution. No LLM in loop.
- **recall** — objective multi-choice item (question + correct answer + distractor), auto-grade vs key.

**Grading data-based only — no self-rate.** Correctness from computed key; FSRS grade derive from correctness + response time (`engine/grading.derive_grade`).

Sibling project `../LearningModel` = single-subject ancestor (SOA Exam P); this generalize its architecture to many subject.

## Subjects

| key | course | mode |
|---|---|---|
| `diffeq` | MATH 220 Differential Equations | generator |
| `databases` | CS 480 Database Systems | generator (FD/normalization) + recall |
| `proofs` | MATH 215 Introduction to Proofs | generator (logic, number theory, sets, functions, counting, floor) + recall |
| `econ` | ECON 111 Freakonomics | generator (decision math) + recall |

Generator subject register `generators.py` (kinds). Each generator make own worked solution on `Problem.explain` (ADR-0003). Legacy `solve.py` file (central `engine.feedback.solve` registry) still back not-yet-migrate subject; `build_item` prefer `Problem.explain`, fallback to registry. Migrated: `databases`. Still on registry: `diffeq`, `econ`, `examfm`, `proofs`, `examp`.

## Hard constraints

- **Local-first.** Pure Python + SQLite; no cloud service, no LLM in core.
- **Answer computed, never improvise.** Generator and its worked solution (`Problem.explain`) share one closed-form computation in same function, so shown solution can't diverge from graded answer. (Unmigrated subject still split this across `solve.py` — retiring per ADR-0003.)
- **Reproducibility.** Generator take explicit `seed`; seed + param log with every interaction.

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

- Type hint everywhere; `ruff` (line-length 100) clean; `pytest` green.
- **Test first for math:** new generator need answer-key test that independently recompute answer across many seed (see `tests/test_diffeq.py`).
- Pure function for math (FSRS curve, generator answer) — unit-testable.
- No section-divider comment; prefer self-documenting name. Comment for *why* only (derivation, non-obvious choice).

## Adding a subject

- recall: add `data/subjects/<key>/concept_graph.seed.json` with `card` node (`question`, `answer`, `distractors`), register in `engine/subjects/__init__.py` SUBJECTS.
- generator: also add `engine/subjects/<key>/generators.py` (`@register("kind")`), each generator build worked step on `Problem.explain` from same computation as answer; import in `engine/subjects/__init__.py`, point concept at kind. Mirror `engine/subjects/databases/`. (No `solve.py` — that legacy path, ADR-0003.)