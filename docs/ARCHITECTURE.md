# Architecture

## Data flow (one study item)

```
cli/study.py
  └─ policy.select_next(subject)            pick concept + reason (review|new)
       ├─ generator concept
       │    ├─ generation.generate(kind, ask, params, seed)  → Problem (closed-form answer)
       │    ├─ grading.grade_answer(user, correct)            → bool
       │    └─ subjects/<key>/solve.solve(...)                → worked steps
       └─ recall concept
            ├─ recall.cards.as_question(concept, rng)         → shuffled multiple-choice
            └─ chosen option == correct?                      → bool
  └─ grading.derive_grade(is_correct, elapsed_ms)            objective FSRS grade (1–4)
  └─ store.apply_rating(card, grade) → store.save(...)        FSRS schedules next due
  └─ dao.log_shown / log_answered (+ elapsed_ms)             every interaction logged
```

## Layers

- **db** — SQLite is the single source of truth: `concept`, `concept_prereq`,
  `card_state`, `session`, `interaction`. `get_connection()` is a context manager
  that commits, rolls back on error, and always closes.
- **scheduler** — `fsrs_core` is the pure forgetting curve (cross-tested against
  py-fsrs); `store` applies ratings via py-fsrs with an early-reinforcement cap;
  `policy` ranks overdue reviews by `(1 − retrievability) × exam_weight`, then opens
  the frontier by exam weight once prerequisites are met.
- **generation** — a `kind → fn` registry; each generator returns a `Problem` with a
  closed-form `correct_answer`, multiple-choice distractors encoding common errors,
  and the `params` needed to reproduce it and to render the worked solution.
- **subjects** — `SUBJECTS` metadata + per-subject generator/solver modules. Adding a
  generator subject means adding a module and seed concepts that reference its kinds.
- **recall** — multiple-choice presentation for subjects without closed-form
  answers; the chosen option is checked against the key, so the same objective FSRS
  path applies. No self-rating: `grading.derive_grade` maps (correct?, elapsed_ms) to
  the FSRS rating, so scheduling is driven by measured performance, not feelings.

## Why two modes

The ancestor engine assumed a finite computational domain (probability) where every
question has a closed-form answer. Differential Equations fits that directly. Proofs
and qualitative economics do not — there is no single gradeable answer — so those run
as spaced-repetition recall, still benefiting from FSRS scheduling and the concept
graph. CS 480 is deliberately split: conceptual topics as recall now, with SQL and
normalization generators as a natural next step (they're auto-checkable).

## Next steps (not yet built)

- CS 480 generators: functional-dependency closure / normalization problems, and SQL
  queries graded by executing against an in-memory SQLite.
- Optional DKT knowledge-tracing per subject (port from `../LearningModel`) once
  enough interaction history accrues.
- Readiness/analytics + a web UI (the ancestor has a React dashboard to adapt).
