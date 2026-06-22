import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AnswerResult, NextItem, Profile, SessionSummary, Subject } from "../types";

const REASON_LABEL: Record<string, string> = {
  new: "🌱 New",
  review: "🔄 Review",
  retry: "↩️ Retry",
};

const SOUND_KEY = "studyengine.sound";
let _ac: AudioContext | null = null;
function ding(freq: number) {
  if (localStorage.getItem(SOUND_KEY) !== "1") return;
  try {
    _ac = _ac ?? new AudioContext();
    const o = _ac.createOscillator();
    const g = _ac.createGain();
    o.connect(g);
    g.connect(_ac.destination);
    o.frequency.value = freq;
    g.gain.value = 0.05;
    o.start();
    o.stop(_ac.currentTime + 0.12);
  } catch {
    /* audio unavailable — silent */
  }
}

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

export default function StudyView() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [scope, setScope] = useState("global");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [dktActive, setDktActive] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [item, setItem] = useState<NextItem | null>(null);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [hintSaved, setHintSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sound, setSound] = useState(localStorage.getItem(SOUND_KEY) === "1");
  const shownAt = useRef<number>(Date.now());
  const restartRef = useRef<(s: string) => void>(() => {});

  useEffect(() => {
    api.subjects().then(setSubjects).catch(() => {});
  }, []);

  const refreshStats = useCallback(() => {
    api.stats().then(setProfile).catch(() => {});
  }, []);

  const loadNext = useCallback(async (sid: number) => {
    setFeedback(null);
    setSelected(null);
    setHint("");
    setHintSaved(false);
    try {
      const next = await api.next(sid);
      setItem(next);
      shownAt.current = Date.now();
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

  const choose = async (choice: string) => {
    if (feedback || !item?.item_id || sessionId === null) return;
    setSelected(choice);
    try {
      const res = await api.answer(sessionId, item.item_id, choice, Date.now() - shownAt.current);
      setFeedback(res);
      ding(res.is_correct ? (res.combo ? 880 : 660) : 180);
      refreshStats();
    } catch (e) {
      if (String(e).includes("404")) startSession(scope);
      else setError(String(e));
    }
  };

  // Keyboard flow: a–d / 1–4 to answer, Enter to advance.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (feedback) {
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
    if (next) ding(660);
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
        <select value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="global">🌐 Global (interleaved)</option>
          {subjects.map((s) => (
            <option key={s.key} value={s.key}>{s.title}</option>
          ))}
        </select>
        {dktActive && <span className="chip">DKT active</span>}
        <button className="bell" onClick={toggleSound} title="Sound effects">
          {sound ? "🔊" : "🔇"}
        </button>
        <span className="muted small kbd-hint">a–d / 1–4 · Enter</span>
      </div>

      <div className="meta">
        <span className="concept">{item.concept_name}</span>
        {item.reason && <span className="reason">{REASON_LABEL[item.reason] ?? item.reason}</span>}
      </div>
      {item.note && <div className="note">📝 your note: {item.note}</div>}
      <div className="question">{item.question}</div>
      {item.theory && (
        <details className="theory">
          <summary>📖 Learn this concept</summary>
          {item.theory}
        </details>
      )}

      <div className="choices">
        {item.choices?.map((c) => (
          <button key={c} className={choiceClass(c)} disabled={!!feedback} onClick={() => choose(c)}>
            {c}
          </button>
        ))}
      </div>

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
          {feedback.why_wrong && (
            <div className="theory-jit">✗ {feedback.why_wrong}</div>
          )}
          {!feedback.is_correct && feedback.theory && (
            <div className="theory-jit">📖 {feedback.theory}</div>
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
                <li key={i}>{s}</li>
              ))}
            </ol>
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
          <button className="btn" onClick={() => loadNext(sessionId!)}>Next →</button>
        </div>
      )}
    </div>
  );
}
