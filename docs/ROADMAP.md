# StudyEngine Roadmap

Goal: one unified "central nervous system" for the whole degree — every exam and
course in a single app with global spaced repetition, interleaving, and a
motivating progress map. Built on cognitive-science principles (interleaved
practice, the 85% rule, endowed progress, the Zeigarnik effect).

## Done

- **Shared engine** — FSRS scheduling, prerequisite concept graph, SQLite, two
  modes (generator / objective multiple-choice recall). No self-rating: grade is
  derived from correctness + response time.
- **Subjects** — MATH 220 Diff Eq, CS 480 Databases, MATH 250 Proofs,
  ECON 111 Econ, **Exam FM**, **Exam P** (44 concepts ported from LearningModel).
  60+ generator kinds, all property-tested.
- **Global interleaved mode** (`engine.cli.study`, default) — weakest-first across
  all subjects, interleaving (down-weights the last subject), warm-up/cool-down
  confidence builders, dopamine pacing toward ~85% success. `--subject X` =
  focus/cram mode.
- **Progress dashboard** (`engine.cli.dashboard`) — data-based readiness per
  subject and per concept (accuracy × FSRS retention × rep-confidence).
- **Global DKT** (`engine.cli.train`) — one PyTorch LSTM trained on the whole
  cross-subject interaction log; once it clears the gate (interactions + AUC) it
  predicts P(correct) per concept and drives weak-concept selection in global
  sessions. FSRS drives until then. `--pretrain` cold-starts it on synthetic data.
- **Knowledge-graph hierarchy + endowed progress** — a `domain` tag groups the
  dashboard (Actuarial / Mathematics / CS / Economics); `ENDOWED_BASELINE` means a
  freshly added syllabus reads ~10%, never 0%.
- **Knowledge map** (`dashboard --map`) — the "unfogging" view: each concept a
  glyph (░ ▒ ▓ █) that brightens with mastery, grouped by domain.
- **Engagement** — mnemonics (write a hint on a miss; it resurfaces — IKEA effect)
  and variable-ratio rewards (occasional praise + streak milestones).

The engine side of the unified-app vision is complete: every cognitive principle
(interleaving, 85% pacing, endowed progress, the unfogging map, variable rewards,
IKEA investment) is implemented and tested at the CLI/data layer.

## Later (a graphical client — out of scope for a Python CLI)

These need a real UI and are a separate frontend project over this same engine and
SQLite (the data + APIs are already here):

- **Graphical knowledge map** — animated node graph instead of glyph rows; nodes
  visibly dim as the forgetting curve decays (Zeigarnik "repair your map" itch).
- **Juicy reward animations + haptics** — the variable-reward *logic* exists; the
  satisfying visuals/sound/vibration are GUI concerns.
- **Analog bridge / Flutter** — "paper mode" (dim → solve on paper → reveal →
  objective self-check) and a cross-platform Flutter/web client with synced state.

## Notes

- `../LearningModel` (Exam P, with DKT + a React dashboard) is the single-subject
  ancestor; its Exam P content and DKT are now folded into this unified app.
