# StudyEngine

Adaptive study tool for several university courses at once. One engine — **FSRS
spaced repetition** + a **prerequisite concept graph** — decides what you should
review next, every day, across all your subjects. Everything is auto-graded from a
computed key; there is no self-rating.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m engine.cli.app        # → opens http://127.0.0.1:8000 in your browser
```

That one command builds the app (first run needs [Node](https://nodejs.org)),
serves it, and opens it. Pick a subject, answer questions by clicking `a`–`d` (or
typing a number), and it schedules your next review for you. Progress is saved in
`data/app.db`, so you can close it and pick up where you left off.

Three tabs:

- **Study** — the session. Answer items; get the worked solution or correct answer
  every time. Fast + correct is treated as easier and pushed further out; wrong
  comes back sooner.
- **Dashboard** — readiness per subject and per concept.
- **Knowledge Map** — every concept as a glyph that brightens `░▒▓█` as you master it.

## What you can study

| Key | Course | Type |
|---|---|---|
| `diffeq` | MATH 220 Differential Equations | computational problems |
| `databases` | CS 480 Database Systems | problems + concept cards |
| `proofs` | MATH 250 Intro to Advanced Maths | problems + concept cards |
| `econ` | ECON 111 Freakonomics | problems + concept cards |
| `examfm` | Exam FM (Financial Mathematics) | problems + concept cards |
| `examp` | Exam P (Probability) | computational problems |

Two kinds of items. **Problems** are generated algorithmically with closed-form
answers and a deterministic worked solution — no LLM. **Concept cards** are
multiple-choice for topics that have no formula (proof techniques, ACID, economic
intuitions).

## Prefer the terminal?

The CLI *is* the engine — the app is a thin layer over it.

```bash
python -m engine.cli.study --n 12               # mixed session across all subjects
python -m engine.cli.study --subject diffeq     # cram one subject before an exam
python -m engine.cli.dashboard                  # readiness per subject
python -m engine.cli.dashboard --map            # knowledge map
```

## Add your own content

Edit a subject's seed file at `data/subjects/<key>/concept_graph.seed.json`. A
concept is either a generator or a recall card, with optional `prerequisites` and
`exam_weight`. Re-running re-seeds concepts without wiping your review history.

For a new **generator** subject, write generators in `engine/subjects/<key>/`
(register with `@register("kind")`) and point concepts at them —
`engine/subjects/diffeq/` is the template.

## Going further

- **Neural knowledge tracing (optional).** The engine runs fine on FSRS alone. To
  add the DKT model that sharpens weak-concept selection:
  ```bash
  pip install -r requirements-dkt.txt --extra-index-url https://download.pytorch.org/whl/cpu
  python -m engine.cli.train
  ```
- **Dev mode** with hot reload (two terminals):
  ```bash
  uvicorn engine.api:app --port 8000
  cd frontend && npm install && npm run dev      # → http://localhost:5173
  ```
- **Tests.**
  ```bash
  pytest
  ruff check engine tests
  ```
- **Design & roadmap** — `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`.
