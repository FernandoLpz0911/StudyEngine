import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AnswerResult, NextItem, Subject } from "../types";

const REASON_LABEL: Record<string, string> = {
  new: "🌱 New",
  review: "🔄 Review",
  retry: "↩️ Retry",
};

export default function StudyView() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [scope, setScope] = useState("global");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [dktActive, setDktActive] = useState(false);
  const [item, setItem] = useState<NextItem | null>(null);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [hintSaved, setHintSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shownAt = useRef<number>(Date.now());

  useEffect(() => {
    api.subjects().then(setSubjects).catch(() => {});
  }, []);

  const loadNext = useCallback(async (sid: number) => {
    setFeedback(null);
    setSelected(null);
    setHint("");
    setHintSaved(false);
    const next = await api.next(sid);
    setItem(next);
    shownAt.current = Date.now();
  }, []);

  const startSession = useCallback(
    async (s: string) => {
      setError(null);
      try {
        const res = await api.startSession(s);
        setSessionId(res.session_id);
        setDktActive(res.dkt_active);
        await loadNext(res.session_id);
      } catch (e) {
        setError(String(e));
      }
    },
    [loadNext],
  );

  useEffect(() => {
    startSession(scope);
  }, [scope, startSession]);

  const choose = async (choice: string) => {
    if (feedback || !item?.item_id || sessionId === null) return;
    setSelected(choice);
    try {
      const res = await api.answer(sessionId, item.item_id, choice, Date.now() - shownAt.current);
      setFeedback(res);
    } catch (e) {
      setError(String(e));
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
      <div className="done">
        <h2>All caught up ✓</h2>
        <p className="muted">Nothing due in this scope. Switch scope or come back later.</p>
        <button className="btn" onClick={() => startSession(scope)}>Check again</button>
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
      <div className="study-bar">
        <select value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="global">🌐 Global (interleaved)</option>
          {subjects.map((s) => (
            <option key={s.key} value={s.key}>{s.title}</option>
          ))}
        </select>
        {dktActive && <span className="chip">DKT active</span>}
      </div>

      <div className="meta">
        <span className="concept">{item.concept_name}</span>
        {item.reason && <span className="reason">{REASON_LABEL[item.reason] ?? item.reason}</span>}
      </div>
      {item.note && <div className="note">📝 your note: {item.note}</div>}
      <div className="question">{item.question}</div>

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
            {feedback.reward && <span className="reward"> · {feedback.reward}</span>}
          </div>
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
