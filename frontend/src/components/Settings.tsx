import { useEffect, useState } from "react";
import { api } from "../api";
import { THEMES, applyTheme, currentTheme } from "../themes";
import type { Setting, SubjectProgress } from "../types";

const LABEL: Record<string, string> = {
  daily_goal: "🎯 Daily goal",
  new_per_day: "🌱 New concepts per day",
  typed_answer_mastery: "✍️ Typed-answer mastery",
};

/** Server-side study settings (persisted in SQLite, shared by web + CLI).
 *
 * Client-only toggles (sound, auto-advance) live next to the study loop; this
 * panel owns the values that shape scheduling itself.
 */
export default function Settings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectProgress[]>([]);
  const [level, setLevel] = useState(0);
  const [theme, setTheme] = useState(currentTheme());

  useEffect(() => {
    api.settings().then(setSettings).catch((e) => setError(String(e)));
    api.progress().then((p) => setSubjects(p.subjects)).catch(() => {});
    api.stats().then((p) => setLevel(p.level)).catch(() => {});
  }, []);

  const pickTheme = (id: string) => {
    applyTheme(id);
    setTheme(id);
  };

  const saveExamDate = async (subject: string, date: string) => {
    await api.setExamDate(subject, date || null);
    setSubjects((subs) =>
      subs.map((s) => (s.subject === subject ? { ...s, exam_date: date || null } : s)),
    );
    setSaved(`exam.${subject}`);
    setTimeout(() => setSaved(null), 1500);
  };

  const save = async (key: string) => {
    const value = drafts[key];
    if (value === undefined || value === "") return;
    try {
      const res = await api.setSetting(key, value);
      setSettings(res.settings);
      setDrafts(({ [key]: _dropped, ...rest }) => rest);
      setSaved(key);
      setTimeout(() => setSaved(null), 1500);
    } catch (e) {
      setError(String(e));
    }
  };

  if (error) return <div className="error">{error}</div>;

  return (
    <div className="settings">
      <h2>Settings</h2>
      {settings.map((s) => (
        <div className="setting-row" key={s.key}>
          <div className="grow">
            <div>{LABEL[s.key] ?? s.key}</div>
            <div className="muted small">
              {s.description} (default {s.default})
            </div>
          </div>
          <input
            type="number"
            step={Number.isInteger(s.default) ? 1 : 0.05}
            value={drafts[s.key] ?? String(s.value)}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
            onBlur={() => save(s.key)}
            onKeyDown={(e) => e.key === "Enter" && save(s.key)}
          />
          {saved === s.key && <span className="verdict ok">✓</span>}
        </div>
      ))}
      <h3>🎨 Theme</h3>
      <p className="muted small">Level up to unlock more. You're level {level}.</p>
      <div className="theme-grid">
        {THEMES.map((t) => {
          const locked = level < t.unlockLevel;
          return (
            <button
              key={t.id}
              className={theme === t.id ? "theme-swatch active" : "theme-swatch"}
              disabled={locked}
              onClick={() => pickTheme(t.id)}
              title={locked ? `Unlocks at level ${t.unlockLevel}` : t.name}
            >
              <span className="dot" style={{ background: t.swatch }} />
              {t.name}
              <span className="muted small">
                {locked ? `🔒 Lvl ${t.unlockLevel}` : theme === t.id ? "active" : ""}
              </span>
            </button>
          );
        })}
      </div>

      <h3>📅 Exam dates</h3>
      <p className="muted small">
        Set a date to see the countdown and the new-concepts-per-day pace on the
        dashboard. Clear the field to remove it.
      </p>
      {subjects.map((s) => (
        <div className="setting-row" key={s.subject}>
          <div className="grow">{s.subject}</div>
          <input
            type="date"
            value={s.exam_date ?? ""}
            onChange={(e) => saveExamDate(s.subject, e.target.value)}
          />
          {saved === `exam.${s.subject}` && <span className="verdict ok">✓</span>}
        </div>
      ))}
      <p className="muted small">
        Changes apply from the next item served. Sound and auto-advance are on the
        study screen itself.
      </p>
    </div>
  );
}
