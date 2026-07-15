# 3. A generator owns its worked solution

Date: 2026-07-14

## Status

Accepted

## Context

Each problem `kind` was registered in two independent registries keyed by the same
magic string: `generation.base.register` (produces `(statement, answer, params)`)
and `feedback.solve.register_solver` (produces the worked-solution steps). Nothing
enforced that the two agreed — a kind with a generator but no solver silently
returned `[]`.

Between them ran an untyped contract: the generator stashed a `params` dict and the
solver reverse-engineered it by branching on key presence (`econ/solve.py` keyed off
`"values"`, `"mb"`, `"old"`, `"cost"`, `"dq"`, `"pct"`). Worse, the answer was
computed *twice*: `databases/generators.py` computed `fd.closure(x, fds)` for the
key, and `databases/solve.py` re-ran the same `fd.closure` to narrate its steps. The
CLAUDE.md hard constraint — "generator and its worked solution share one closed-form
computation — shown solution cannot diverge from graded answer" — was upheld only by
convention (both files calling the same `fd` helpers), not by construction.

## Decision

Fold the worked solution into the generator. `Problem` carries an `explain:
list[str]`, produced by the generator from the *same* computation that yields
`correct_answer` — the intermediate values (closure, candidate keys, violations) are
already in scope, so the steps reuse them instead of recomputing. `service.build_item`
prefers `problem.explain`, falling back to the legacy `feedback.solve` registry only
when it is empty:

```python
explain = problem.explain or worked_solution(spec["kind"], ask, problem.params)
```

`params` stays on `Problem` — it is still logged with every interaction for
reproducibility — but it is no longer a handshake to a second function.

Rollout is incremental. The fallback lets migrated and unmigrated subjects coexist:
each subject's `solve.py` is deleted as its generators start carrying `explain`.
`databases` is migrated first (5 kinds); `diffeq`, `econ`, `examfm`, `proofs`, and
`examp` still use the legacy registry. When the last subject lands, `feedback.solve`
and the `build_item` fallback are deleted.

## Consequences

- The answer key and its explanation share one closed form by construction, not
  convention — they cannot diverge, and the FD closure/keys are computed once.
- One registration per kind instead of two; the untyped `params` handshake and the
  per-kind `if kind == …` switch inside each `solve.py` disappear as subjects
  migrate.
- During migration two mechanisms coexist (generator `explain` + legacy registry) —
  accepted as the price of a reviewable, subject-at-a-time rollout rather than one
  huge diff across ~87 kinds.
- The subject-authoring template changes: a new generator subject produces its worked
  steps inline (see CLAUDE.md), no separate `solve.py`.
