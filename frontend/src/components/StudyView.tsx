import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AnswerResult, NextItem, Profile, SessionSummary, Subject } from "../types";
import Markdown from "./Markdown";
import Tex from "./Math";
import QuestionTimer from "./QuestionTimer";
import { playCorrect, playLevelUp, playWrong } from "./sound";
import { unlockedAt } from "../themes";
import { useActiveElapsed } from "../useActiveElapsed";

const REASON_LABEL: Record<string, string> = {
  new: "🌱 New",
  review: "🔄 Review",
  retry: "↩️ Retry",
};

// The teaching ladder (ADR-0013). Shown so it is obvious when an item is teaching
// rather than testing — a scaffolded correct answer should not feel like a solo one.
const STAGE_LABEL: Record<string, string> = {
  study: "📘 Learn",
  paired: "🪜 Guided",
};

/** The worked example that precedes the question at the study and paired stages. */
function WorkedExample({ item }: { item: NextItem }) {
  if (!item.example?.length) return null;
  const isStudy = item.stage === "study";
  return (
    <div className={isStudy ? "example study" : "example"}>
      <div className="example-head">
        {isStudy
          ? "📘 Worked solution — follow it through, then give the answer below."
          : "📘 Worked example — same method, different numbers."}
      </div>
      {item.example_statement && (
        <div className="example-statement"><Tex>{item.example_statement}</Tex></div>
      )}
      <ol className="steps">
        {item.example.map((s, i) => (
          <li key={i}><Tex>{s}</Tex></li>
        ))}
      </ol>
    </div>
  );
}

/** The concept explanation on a bare item, behind a confirmation.
 *
 *  Reaching for the explanation mid-problem makes the problem easier than the
 *  exam will be, and the log had no way to know it happened — the answer went in
 *  as unaided evidence. So it is asked for out loud, and it costs: the answer
 *  stops counting toward readiness, and forfeits its XP and combo. Only at the
 *  `solo` stage; at `study` and `paired` the explanation *is* the teaching and is
 *  free. */
function GatedTheory({
  theory,
  onOpen,
  opened,
}: {
  theory: string;
  onOpen: () => void;
  opened: boolean;
}) {
  const [asking, setAsking] = useState(false);

  if (opened) {
    return (
      <div className="theory aided">
        <div className="theory-aided-head">
          📖 Opened — this answer won't count toward readiness.
        </div>
        <Markdown>{theory}</Markdown>
      </div>
    );
  }
  if (asking) {
    return (
      <div className="theory confirm">
        <div className="confirm-head">Open the explanation?</div>
        <p className="muted small">
          This answer will be logged as aided: no readiness credit, no XP, and the
          combo resets. It still counts toward today's quota, and toward Ascent.
        </p>
        <div className="confirm-actions">
          <button className="btn ghost" onClick={() => setAsking(false)}>
            No — let me try
          </button>
          <button className="btn danger" onClick={onOpen}>
            Yes, I'm certain
          </button>
        </div>
      </div>
    );
  }
  return (
    <button className="btn ghost theory-ask" onClick={() => setAsking(true)}>
      📖 I need the explanation…
    </button>
  );
}

/** Decline to guess. Counts as a miss, but drops the concept a rung straight
 *  away — so saying it is the fast route to being taught, not a way out. */
function DontKnow({ disabled, onPick }: { disabled: boolean; onPick: () => void }) {
  return (
    <button
      type="button"
      className="btn ghost dont-know"
      disabled={disabled}
      title="Counts as a miss — and gets this concept taught again next time"
      onClick={onPick}
    >
      🤷 I don't know
    </button>
  );
}

/** After a miss: name the step it broke at, so the solution gets read, not skipped. */
function Reflection({
  steps,
  onPick,
}: {
  steps: string[];
  onPick: (index: number | null) => void;
}) {
  const [picked, setPicked] = useState<number | null | undefined>(undefined);
  const choose = (index: number | null) => {
    if (picked !== undefined) return;
    setPicked(index);
    onPick(index);
  };
  if (picked !== undefined) {
    return (
      <div className="muted small">
        {picked === null
          ? "Noted — not sure where it broke."
          : `Noted — step ${picked + 1}.`}
      </div>
    );
  }
  return (
    <div className="reflect">
      <div className="reflect-head">Which step first went wrong?</div>
      <div className="reflect-steps">
        {steps.map((_, i) => (
          <button key={i} className="btn ghost small-btn" onClick={() => choose(i)}>
            {i + 1}
          </button>
        ))}
        <button className="btn ghost small-btn" onClick={() => choose(null)}>
          Not sure
        </button>
      </div>
    </div>
  );
}

// Sent instead of an answer to decline guessing. Must match service.DONT_KNOW —
// a guess that happens to land is a false positive in the one number every
// readiness signal is built from, so there has to be a way to say nothing.
const DONT_KNOW = "__dont_know__";

const SOUND_KEY = "studyengine.sound";
const AUTO_ADVANCE_KEY = "studyengine.autoadvance";
const AUTO_ADVANCE_MS = 1400;

function StatsBar({ p }: { p: Profile }) {
  const xpPct = Math.round((100 * p.xp_into_level) / p.xp_for_next);
  const goalPct = Math.min(100, Math.round((100 * p.answered_today) / p.daily_goal));
  return (
    <div className="hud">
      <span className={p.streak_days ? "hud-streak live" : "hud-streak"}>
        🔥 {p.streak_days}
        <small>day streak</small>
      </span>
      <div className="hud-xp">
        <div className="hud-xp-head">
          <span>⭐ Lvl {p.level}</span>
          <span className="muted small">
            {p.xp_into_level}/{p.xp_for_next} XP
          </span>
        </div>
        <div className="bar">
          <div className="bar-fill" style={{ width: `${xpPct}%`, background: "var(--green)" }} />
        </div>
      </div>
      <span className="hud-goal" title="Daily goal">
        🎯 {p.answered_today}/{p.daily_goal}
        {goalPct >= 100 && " ✓"}
      </span>
      {p.freezes > 0 && (
        <span className="hud-goal" title="Streak freezes — each bridges one missed day">
          🧊 {p.freezes}
        </span>
      )}
      {p.due_count > 0 && (
        <span className="hud-due" title="Reviews waiting">
          ↩️ {p.due_count}
        </span>
      )}
    </div>
  );
}

function Summary({
  s,
  onContinue,
}: {
  s: SessionSummary;
  onContinue: () => void;
}) {
  const acc = Math.round(s.accuracy * 100);
  const goalHit = s.answered_today >= s.daily_goal;
  return (
    <div className="done summary">
      <h2>Session complete</h2>
      <div className="summary-grid">
        <div className="stat">
          <div className="stat-num">{acc}%</div>
          <div className="muted small">{s.correct}/{s.answered} correct</div>
        </div>
        <div className="stat">
          <div className="stat-num">+{s.xp_gained}</div>
          <div className="muted small">XP earned</div>
        </div>
        <div className="stat">
          <div className="stat-num">🔥 {s.streak_days}</div>
          <div className="muted small">day streak {s.studied_today ? "held" : ""}</div>
        </div>
        <div className="stat">
          <div className="stat-num">×{s.best_streak}</div>
          <div className="muted small">best combo</div>
        </div>
      </div>
      <p className={goalHit ? "verdict ok" : "muted"}>
        {goalHit
          ? `🎯 Daily goal hit (${s.answered_today}/${s.daily_goal})!`
          : `🎯 ${s.daily_goal - s.answered_today} more to hit today's goal.`}
      </p>
      <button className="btn" onClick={onContinue}>
        {s.due_count > 0 ? `Keep going · ${s.due_count} waiting →` : "Go again →"}
      </button>
    </div>
  );
}

export default function StudyView({
  initialScope = "global",
  lockScope = false,
}: {
  initialScope?: string;
  /** Gate mode: the subject is the quota's subject, so switching it is meaningless. */
  lockScope?: boolean;
}) {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [scope, setScope] = useState(initialScope);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [dktActive, setDktActive] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [item, setItem] = useState<NextItem | null>(null);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [hintSaved, setHintSaved] = useState(false);
  const [reflected, setReflected] = useState(false);
  // Per-item, reset by loadNext: the explanation was opened on *this* problem.
  const [aided, setAided] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sound, setSound] = useState(localStorage.getItem(SOUND_KEY) === "1");
  const [autoAdvance, setAutoAdvance] = useState(
    localStorage.getItem(AUTO_ADVANCE_KEY) !== "0",
  );
  const [typed, setTyped] = useState("");
  const activeTime = useActiveElapsed(!!feedback);
  const restartRef = useRef<(s: string) => void>(() => {});
  const advanceTimer = useRef<number | null>(null);

  useEffect(() => {
    api.subjects().then(setSubjects).catch(() => {});
  }, []);

  const refreshStats = useCallback(() => {
    api.stats().then(setProfile).catch(() => {});
  }, []);

  // Fanfare when XP crosses a level boundary — plus the theme it unlocks, so the
  // level number pays out something visible.
  const prevLevel = useRef<number | null>(null);
  const [levelNote, setLevelNote] = useState<string | null>(null);
  useEffect(() => {
    if (!profile) return;
    if (prevLevel.current !== null && profile.level > prevLevel.current) {
      playLevelUp();
      const unlocked = unlockedAt(profile.level);
      setLevelNote(
        unlocked.length
          ? `⭐ Level ${profile.level}! Theme unlocked: ${unlocked.map((t) => t.name).join(", ")} → Settings`
          : `⭐ Level ${profile.level}!`,
      );
    }
    prevLevel.current = profile.level;
  }, [profile]);

  const loadNext = useCallback(async (sid: number) => {
    if (advanceTimer.current !== null) {
      window.clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
    setFeedback(null);
    setSelected(null);
    setTyped("");
    setHint("");
    setHintSaved(false);
    setReflected(false);
    setAided(false);
    try {
      const next = await api.next(sid);
      setItem(next);
      activeTime.reset();
    } catch (e) {
      if (String(e).includes("404")) restartRef.current(scope);
      else setError(String(e));
    }
  }, [scope]);

  const startSession = useCallback(
    async (s: string) => {
      setError(null);
      try {
        const res = await api.startSession(s);
        setSessionId(res.session_id);
        setDktActive(res.dkt_active);
        refreshStats();
        await loadNext(res.session_id);
      } catch (e) {
        setError(String(e));
      }
    },
    [loadNext, refreshStats],
  );

  useEffect(() => {
    restartRef.current = startSession;
  }, [startSession]);

  useEffect(() => {
    startSession(scope);
  }, [scope, startSession]);

  useEffect(
    () => () => {
      if (advanceTimer.current !== null) window.clearTimeout(advanceTimer.current);
    },
    [],
  );

  const choose = async (choice: string) => {
    if (feedback || !item?.item_id || sessionId === null) return;
    setSelected(choice);
    try {
      const res = await api.answer(
        sessionId, item.item_id, choice, activeTime.read(), aided,
      );
      setFeedback(res);
      if (res.is_correct) playCorrect(res.streak);
      else playWrong();
      refreshStats();
      // Correct answers flow on by themselves; misses wait so the explanation is
      // read, and a pending mnemonic ask (leech) waits for the input.
      if (res.is_correct && autoAdvance && !res.fatigued && !res.ask_mnemonic) {
        advanceTimer.current = window.setTimeout(() => loadNext(sessionId), AUTO_ADVANCE_MS);
      }
    } catch (e) {
      // Item lost to a server restart: the session itself is rebuilt server-side,
      // so just fetch the next item; loadNext restarts only if the session is gone.
      if (String(e).includes("404")) loadNext(sessionId);
      else setError(String(e));
    }
  };

  // Keyboard flow: a–d / 1–4 to answer, Enter to advance.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (feedback) {
        // Enter advances, except while a reflection is still owed — the keyboard
        // must not be the way around the prompt the button already blocks.
        if (feedback.ask_reflection && !reflected) return;
        if (e.key === "Enter" && sessionId !== null) {
          if (item?.done) startSession(scope);
          else loadNext(sessionId);
        }
        return;
      }
      const choices = item?.choices ?? [];
      const idx = "abcd".indexOf(e.key.toLowerCase());
      const num = parseInt(e.key, 10) - 1;
      const pick = idx >= 0 ? idx : Number.isInteger(num) ? num : -1;
      if (pick >= 0 && pick < choices.length) choose(choices[pick]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const toggleSound = () => {
    const next = !sound;
    setSound(next);
    localStorage.setItem(SOUND_KEY, next ? "1" : "0");
    if (next) playCorrect(3);
  };

  const toggleAutoAdvance = () => {
    const next = !autoAdvance;
    setAutoAdvance(next);
    localStorage.setItem(AUTO_ADVANCE_KEY, next ? "1" : "0");
    if (!next && advanceTimer.current !== null) {
      window.clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
  };

  const saveHint = async () => {
    if (!item?.concept_id || !hint.trim()) return;
    await api.mnemonic(item.concept_id, hint.trim());
    setHintSaved(true);
  };

  if (error) {
    return (
      <div className="error">
        Backend error: {error}
        <p className="muted">
          Start it with <code>uvicorn engine.api:app --port 8000</code>.
        </p>
      </div>
    );
  }
  if (!item) return <div className="muted">Loading…</div>;
  if (item.done) {
    return (
      <div className="study">
        {profile && <StatsBar p={profile} />}
        {item.summary ? (
          <Summary s={item.summary} onContinue={() => startSession(scope)} />
        ) : (
          <div className="done">
            <h2>All caught up ✓</h2>
            <p className="muted">Nothing due in this scope. Switch scope or come back later.</p>
            <button className="btn" onClick={() => startSession(scope)}>Check again</button>
          </div>
        )}
      </div>
    );
  }

  const choiceClass = (c: string) => {
    if (!feedback) return selected === c ? "choice selected" : "choice";
    if (c === feedback.correct_answer) return "choice correct";
    if (c === selected) return "choice wrong";
    return "choice";
  };

  return (
    <div className="study">
      {profile && <StatsBar p={profile} />}
      <div className="study-bar">
        {lockScope ? (
          <span className="chip">
            {subjects.find((s) => s.key === scope)?.title ?? scope}
          </span>
        ) : (
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="global">🌐 Global (interleaved)</option>
            {subjects.map((s) => (
              <option key={s.key} value={s.key}>{s.title}</option>
            ))}
          </select>
        )}
        {dktActive && <span className="chip">DKT active</span>}
        <button className="bell" onClick={toggleSound} title="Sound effects">
          {sound ? "🔊" : "🔇"}
        </button>
        <button
          className="bell"
          onClick={toggleAutoAdvance}
          title="Auto-advance after a correct answer"
        >
          {autoAdvance ? "⏩" : "⏸"}
        </button>
        <span className="muted small kbd-hint">a–d / 1–4 · Enter</span>
      </div>

      <div className="meta">
        <span className="concept">{item.concept_name}</span>
        {item.stage && STAGE_LABEL[item.stage] && (
          <span className="reason stage">{STAGE_LABEL[item.stage]}</span>
        )}
        {item.reason && <span className="reason">{REASON_LABEL[item.reason] ?? item.reason}</span>}
        {item.subject === "examp" && (
          <QuestionTimer elapsedMs={activeTime.elapsedMs} />
        )}
      </div>
      {levelNote && (
        <div className="note" onClick={() => setLevelNote(null)}>
          {levelNote} <span className="muted small">(click to dismiss)</span>
        </div>
      )}
      {item.leech && (
        <div className="note leech">
          ⚠️ Leech — missed {item.lapses}× before. Slow down; re-read, then answer.
        </div>
      )}
      {item.note && <div className="note">📝 your note: {item.note}</div>}
      <div className="question"><Tex>{item.question}</Tex></div>
      {item.theory &&
        (item.stage === "solo" ? (
          // Bare item: the explanation costs something, so it is asked for. Note
          // this deliberately ignores `cold` and `leech` — auto-opening would
          // spend the penalty on the learner's behalf and, worse, would make the
          // aided flag meaningless by setting it on nearly every item.
          <GatedTheory
            key={item.item_id}
            theory={item.theory}
            opened={aided}
            onOpen={() => setAided(true)}
          />
        ) : (
          <details className="theory" key={item.item_id} open={item.cold || item.leech}>
            <summary>
              {item.cold ? "📖 Start here — concept explained" : "📖 Learn this concept"}
            </summary>
            <Markdown>{item.theory}</Markdown>
          </details>
        ))}
      <WorkedExample item={item} />

      {item.input_mode === "typed" ? (
        <form
          className="typed-answer"
          onSubmit={(e) => {
            e.preventDefault();
            if (!feedback && typed.trim()) choose(typed.trim());
          }}
        >
          <div className="muted small">✍️ You know this one — no options. Type the value:</div>
          <input
            autoFocus
            inputMode="decimal"
            placeholder="Your answer…"
            value={typed}
            disabled={!!feedback}
            onChange={(e) => setTyped(e.target.value)}
          />
          <button className="btn" type="submit" disabled={!!feedback || !typed.trim()}>
            Answer
          </button>
          <DontKnow disabled={!!feedback} onPick={() => choose(DONT_KNOW)} />
        </form>
      ) : (
        <div className="choices">
          {item.choices?.map((c) => (
            <button key={c} className={choiceClass(c)} disabled={!!feedback} onClick={() => choose(c)}>
              {c}
            </button>
          ))}
          <DontKnow disabled={!!feedback} onPick={() => choose(DONT_KNOW)} />
        </div>
      )}

      {feedback && (
        <div className="feedback">
          <div className={feedback.is_correct ? "verdict ok" : "verdict bad"}>
            {feedback.is_correct ? "✓ Correct" : `✗ Incorrect — ${feedback.correct_answer}`}
            {" · "}
            {feedback.label}
            {feedback.xp_gained > 0 && <span className="reward"> · +{feedback.xp_gained} XP</span>}
            {feedback.reward && <span className="reward"> · {feedback.reward}</span>}
          </div>
          {feedback.combo && (
            <div className="combo">
              {feedback.combo} ×{feedback.streak}
            </div>
          )}
          {feedback.records?.map((r) => (
            <div className="reward" key={r}>{r}</div>
          ))}
          {feedback.aided && (
            <div className="note aided-note">
              📖 Aided — didn't count toward readiness, and no XP for this one.
            </div>
          )}
          {feedback.combo_break && (
            <div className="muted">{feedback.combo_break}</div>
          )}
          {feedback.why_wrong && (
            <div className="theory-jit">✗ <Tex>{feedback.why_wrong}</Tex></div>
          )}
          {feedback.theory && (
            <details className="theory" open={!feedback.is_correct}>
              <summary>📖 Concept explanation</summary>
              <Markdown>{feedback.theory}</Markdown>
            </details>
          )}
          {feedback.fatigued && (
            <div className="note">😮‍💨 Accuracy dipping — a short break may help.</div>
          )}
          {feedback.next_review_days !== null && (
            <div className="muted small">
              ↩️ back in {feedback.next_review_days} day(s)
            </div>
          )}
          {feedback.steps.length > 0 && (
            <ol className="steps">
              {feedback.steps.map((s, i) => (
                <li key={i}><Tex>{s}</Tex></li>
              ))}
            </ol>
          )}
          {feedback.ask_reflection && !reflected && (
            <Reflection
              steps={feedback.steps}
              onPick={(index) => {
                setReflected(true);
                api.reflect(feedback.item_id, item.concept_id!, index).catch(() => {});
              }}
            />
          )}
          {feedback.ask_mnemonic && !hintSaved && (
            <div className="mnemonic">
              <input
                placeholder="Add a hint for next time…"
                value={hint}
                onChange={(e) => setHint(e.target.value)}
              />
              <button className="btn ghost" onClick={saveHint}>Save hint</button>
            </div>
          )}
          {hintSaved && <div className="muted">Hint saved — you'll see it next time.</div>}
          <div className="feedback-actions">
            {/* Held until the step is named: a self-explanation you can click past
                is one that trains clicking past it. */}
            <button
              className="btn"
              disabled={feedback.ask_reflection && !reflected}
              onClick={() => loadNext(sessionId!)}
            >
              Next →
            </button>
            <button
              className="btn ghost small-btn"
              title="Hide this concept until tomorrow"
              onClick={async () => {
                await api.buryConcept(item.concept_id!);
                loadNext(sessionId!);
              }}
            >
              😴 Bury today
            </button>
            <button
              className="btn ghost small-btn"
              title="I know this — stop scheduling it (resume from Settings)"
              onClick={async () => {
                await api.suspendConcept(item.concept_id!);
                loadNext(sessionId!);
              }}
            >
              ✋ I know this
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
