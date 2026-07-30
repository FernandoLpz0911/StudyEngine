# 11. Generator kinds are globally unique, enforced at import

Date: 2026-07-29

## Status

Accepted

## Context

`generation.base._generators` and `feedback.solve._solvers` are flat dicts keyed by
`kind` alone. Nothing scopes a kind to the subject that defined it, and nothing
objected when two subjects claimed the same one — the later import simply replaced
the earlier entry.

Two subjects did claim the same one. Exam P and MATH 215 Proofs both registered
`combinatorics`, and `engine/subjects/__init__.py` imports proofs after examp. So
Exam P's *Combinatorics* concept had been serving Proofs problems, graded against
the Proofs answer key, while the worked solution came from whichever solver won
the same race. The concept had accumulated twelve reviews and a readiness score
before anyone noticed; nothing in the system was capable of noticing, because the
existing test only asserted that the key appeared among the choices and that
*some* worked solution existed — both true of the wrong subject's problem.

This is the failure mode ADR-0003 exists to close, arriving through a different
door: not generator and solution disagreeing within a subject, but a whole subject
substituting another's content.

## Decision

A kind may be registered once. `register` and `register_solver` raise on a second,
different registration, naming both modules.

The colliding Proofs kind is renamed `proofs_combinatorics`; Exam P keeps
`combinatorics`. Two tests back this up:

- every Exam P kind/ask must have its solver reach the same number the answer is
  graded against, across many seeds — the invariant that would have caught this on
  day one;
- statements must not name the method or restate its closed form.

## Consequences

- Collisions now fail at import, loudly, with both module paths — impossible to
  ship silently, and cheap to fix by renaming.
- Kinds stay a single global namespace rather than becoming `(subject, kind)`
  pairs. Namespacing would remove the collision by construction, but every call
  site would have to thread a subject through, and the seed files would all need
  rewriting. A hard error at import buys most of the safety for none of that.
- Subject-prefixed names are now the convention for anything generic enough that
  another course might want it (`combinatorics`, `variance`, `expectation`).
- A stored `generator_json` still holds the old kind until the seed is reloaded.
  `load_all` runs on every app start and upserts, so this self-heals; the Proofs
  concept was re-seeded directly as part of this change.
