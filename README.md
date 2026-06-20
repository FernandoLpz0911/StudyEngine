# StudyEngine

A multi-subject adaptive study tool. One shared engine — **FSRS spaced-repetition
scheduling** + a **concept graph** with prerequisites — drives every course. Each
subject plugs in as one of two modes:

- **Generator mode** — problems are produced algorithmically with closed-form
  answers and auto-graded, with a deterministic worked solution (no LLM). Every
  subject uses it for its computational parts: ODEs/Laplace (MATH 220), functional
  dependencies and normalization (CS 480), set counting (MATH 250), and decision
  math — opportunity cost / margin / expected value (ECON 111).
- **Recall mode** — objective **multiple-choice** items (one correct option,
  curated distractors), auto-graded. Carries the conceptual topics that have no
  closed-form answer: proof techniques, ACID/2PL/recovery, economic intuitions.

**Grading is purely data-based — there is no self-rating anywhere.** Every item is
either right or wrong from a computed key, and the four-level FSRS rating (Again /
Hard / Good / Easy) is *derived* from correctness plus measured response time, never
chosen by feel.

## Courses included

| Subject key | Course | Mode | Status |
|---|---|---|---|
| `diffeq` | MATH 220 Differential Equations | generator | 8 generators: separable, 1st-order linear, 2nd-order roots, Laplace + inverse, Newton cooling, integrating factor, Euler's method |
| `databases` | CS 480 Database Systems | generator + recall | FD generators (closure, candidate keys, BCNF, prime attributes, superkeys) + concept cards |
| `proofs` | MATH 250 Intro to Advanced Maths | generator + recall | counting/logic generators (inclusion–exclusion 2- & 3-set, power sets, Cartesian, function counts, truth tables) + technique cards |
| `econ` | ECON 111 Freakonomics | generator + recall | decision generators (opportunity cost, margin, expected value, % change, ROI, elasticity) + concept cards |

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

Answer every item by picking a letter (`a`–`d`); generator problems also accept a
typed numeric value. You get the worked solution (generator) or the correct option
(recall) either way. The scheduler then derives the FSRS grade from whether you were
right and how quickly — fast+correct → Easy, slow+correct → Hard, wrong → Again.
Tune the thresholds with `GRADE_FAST_MS` / `GRADE_SLOW_MS`.

## How it picks what to study

`engine/scheduler/policy.py` selects, per subject: overdue review cards first
(ranked by how much you've likely forgotten × exam weight), otherwise the
highest-weighted concept whose prerequisites you've already seen.

## Adding your own content

Edit the seed file for a subject under `data/subjects/<key>/concept_graph.seed.json`.
A concept is either a generator (`"generator": {"kind": ..., "params": {...}}`)
or a recall card
(`"card": {"question": ..., "answer": ..., "distractors": [...]}`), with optional
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
