CREATE TABLE IF NOT EXISTS concept (
    id              TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    domain          TEXT,                   -- e.g. Actuarial / Mathematics / CS
    name            TEXT NOT NULL,
    category        TEXT,
    mode            TEXT NOT NULL,          -- 'generator' | 'recall'
    generator_json  TEXT,                   -- {kind, params} for generator concepts
    card_question   TEXT,                   -- recall prompt (objective, multiple-choice)
    card_answer     TEXT,                   -- the one correct option
    card_distractors TEXT,                  -- JSON array of wrong options
    card_explanations TEXT,                 -- JSON {distractor: why-it's-wrong}
    theory_md       TEXT,
    exam_weight     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS concept_prereq (
    concept_id  TEXT NOT NULL REFERENCES concept(id),
    prereq_id   TEXT NOT NULL REFERENCES concept(id),
    PRIMARY KEY (concept_id, prereq_id)
);

CREATE TABLE IF NOT EXISTS card_state (
    concept_id  TEXT PRIMARY KEY REFERENCES concept(id),
    stability   REAL,
    difficulty  REAL,
    last_review TEXT,
    due         TEXT,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    step        INTEGER,
    state       TEXT NOT NULL DEFAULT 'learning'
);

CREATE TABLE IF NOT EXISTS session (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS interaction (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES session(id),
    concept_id      TEXT NOT NULL REFERENCES concept(id),
    subject         TEXT NOT NULL,
    kind            TEXT NOT NULL,
    seed            INTEGER NOT NULL DEFAULT 0,
    params_json     TEXT NOT NULL DEFAULT '{}',
    correct_answer  TEXT,
    user_answer     TEXT,
    is_correct      INTEGER,
    grade           INTEGER,
    elapsed_ms      INTEGER,
    shown_at        TEXT NOT NULL,
    answered_at     TEXT
);

CREATE TABLE IF NOT EXISTS setting (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_retry (
    concept_id  TEXT PRIMARY KEY REFERENCES concept(id),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_suppression (
    concept_id  TEXT PRIMARY KEY REFERENCES concept(id),
    until       TEXT,                   -- NULL: suspended indefinitely; else local ISO date
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_log (
    day         TEXT NOT NULL,          -- local ISO date the quest was completed
    quest_id    TEXT NOT NULL,
    bonus_xp    INTEGER NOT NULL,
    PRIMARY KEY (day, quest_id)
);

CREATE TABLE IF NOT EXISTS mnemonic (
    concept_id  TEXT PRIMARY KEY REFERENCES concept(id),
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_concept_subject ON concept(subject);
CREATE INDEX IF NOT EXISTS idx_interaction_concept ON interaction(concept_id);
CREATE INDEX IF NOT EXISTS idx_interaction_answered ON interaction(answered_at);
CREATE INDEX IF NOT EXISTS idx_card_due ON card_state(due);
