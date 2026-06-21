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
  sessions. FSRS drives until then.

## Next (high value)

1. **Knowledge-graph hierarchy + endowed progress.** Add a `domain` tag
   (Domain → Course/subject → Module/category → KC/concept) so the dashboard groups
   Actuarial / Mathematics / Computer Science / Economics. Add an
   `ENDOWED_BASELINE` so a freshly added syllabus shows ~10% familiarity (seeded
   from prerequisite mastery) instead of 0% — "never start at zero."

2. **DKT pretraining on synthetic data** (optional). Port LearningModel's synthetic
   warm-up so the model is useful before the real-interaction gate is met — a
   cold-start boost. FSRS already covers this window, so it is a nicety.

## Later (needs a real UI — CLI can't express these well)

4. **Knowledge-map visualization (the "unfogging" map).** Render the concept graph
   as nodes that brighten with mastery and dim as the forgetting curve decays
   (Zeigarnik "repair your map" itch). The dashboard's per-concept mastery already
   provides the data.

5. **Engagement mechanics.** Variable-reward animations on milestones, "juicy"
   micro-interactions, the IKEA effect (let the user attach a one-line mnemonic to
   a missed item and resurface it), frictionless "Start Daily Optimization" button.

6. **Analog bridge / cross-platform.** "Paper mode" for heavy problems (dim screen
   → solve on paper → reveal → objective self-check), and a Flutter/web client over
   the same engine with synced global state.

## Notes

- `../LearningModel` (Exam P, with DKT + a React dashboard) is the single-subject
  ancestor; this repo generalizes it. The plan above folds its Exam P content and
  DKT into the unified app rather than running two tools.
