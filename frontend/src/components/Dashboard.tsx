import { useEffect, useState } from "react";
import { api } from "../api";
import type { DailyQuest, Me, Progress, SubjectProgress } from "../types";

const SUBJECT_ICON: Record<string, string> = {
  examp: "🎲",
  examfm: "💰",
  diffeq: "📈",
  databases: "🗄️",
  proofs: "📐",
  econ: "📊",
};

function Bar({ frac, started = true }: { frac: number; started?: boolean }) {
  const pct = Math.round(frac * 100);
  const color = !started
    ? "var(--surface2)"
    : frac >= 0.7
      ? "var(--green)"
      : frac >= 0.4
        ? "var(--yellow)"
        : "var(--accent)";
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function Heatmap({ days }: { days: string[] }) {
  const set = new Set(days);
  const cells: { date: string; on: boolean }[] = [];
  const today = new Date();
  for (let i = 118; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    cells.push({ date: iso, on: set.has(iso) });
  }
  return (
    <div className="heatmap">
      {cells.map((c) => (
        <span
          key={c.date}
          className={c.on ? "hcell on" : "hcell"}
          title={`${c.date}${c.on ? " · studied" : ""}`}
        />
      ))}
    </div>
  );
}

function groupByDomain(subjects: SubjectProgress[]): Record<string, SubjectProgress[]> {
  const grouped: Record<string, SubjectProgress[]> = {};
  for (const s of subjects) {
    const domain = s.domain ?? "Other";
    if (!grouped[domain]) grouped[domain] = [];
    grouped[domain].push(s);
  }
  return grouped;
}

// Started subjects first, then by readiness — so momentum sits at the top and the
// untouched ones don't dominate as a wall of empty bars.
function ranked(subjects: SubjectProgress[]): SubjectProgress[] {
  return [...subjects].sort((a, b) => {
    const sa = a.seen > 0 ? 1 : 0;
    const sb = b.seen > 0 ? 1 : 0;
    return sb - sa || b.readiness - a.readiness;
  });
}

export default function Dashboard({ onStudy }: { onStudy: (scope: string) => void }) {
  const [p, setP] = useState<Progress | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [quests, setQuests] = useState<DailyQuest[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.progress().then(setP).catch((e) => setError(String(e)));
    api.me().then(setMe).catch(() => {});
    api.quests().then(setQuests).catch(() => {});
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!p) return <div className="muted">Loading…</div>;

  const due = me?.due_count ?? 0;
  const goalLeft = me ? Math.max(0, me.daily_goal - me.answered_today) : 0;

  return (
    <div className="dash">
      <section className="hero-cta">
        <div>
          <div className="hero-line">
            {due > 0
              ? `${due} review${due > 1 ? "s" : ""} due now`
              : goalLeft > 0
                ? `${goalLeft} to hit today's goal`
                : "All caught up — keep the streak alive"}
          </div>
          {me && (
            <div className="muted small">
              🔥 {me.streak_days}-day streak · ⭐ Lvl {me.level}
              {me.freezes > 0 && ` · 🧊 ${me.freezes}`}
            </div>
          )}
        </div>
        <button className="btn big" onClick={() => onStudy("global")}>
          {due > 0 ? "Review now →" : "Study →"}
        </button>
      </section>

      {quests.length > 0 && (
        <section className="card">
          <h3>Today's quests</h3>
          {quests.map((q) => (
            <div className="quest" key={q.id}>
              <div className="srow-head">
                <span className={q.done ? "quest-done" : ""}>
                  {q.name} <span className="muted small">— {q.desc}</span>
                </span>
                <span className="muted small">
                  {q.done ? `✓ +${q.bonus_xp} XP` : `${q.progress}/${q.target}`}
                </span>
              </div>
              <Bar frac={q.progress / q.target} />
            </div>
          ))}
        </section>
      )}

      {me && (
        <section className="card">
          <h3>Activity</h3>
          <Heatmap days={me.heatmap} />
          <div className="muted small">
            fastest {me.bests.fastest_ms ? `${(me.bests.fastest_ms / 1000).toFixed(1)}s` : "—"}{" "}
            · best day {me.bests.best_day} · longest run {me.bests.longest_run}
          </div>
          <div className="badges">
            {me.achievements.map((a) => (
              <span
                key={a.id}
                className={a.earned ? "badge earned" : "badge"}
                title={a.earned ? a.desc : `${a.desc} — ${a.progress_text}`}
              >
                {a.name}
                {!a.earned && (
                  <span className="badge-progress">
                    <span style={{ width: `${Math.round(a.progress * 100)}%` }} />
                  </span>
                )}
              </span>
            ))}
          </div>
          {me.leeches.length > 0 && (
            <div className="leeches">
              <strong>⚠️ Leeches</strong> (repeatedly missed — add a mnemonic):
              {me.leeches.slice(0, 5).map((l) => (
                <div key={l.id} className="muted small">
                  {l.lapses}× {l.name} ({l.subject})
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="card">
        <div className="srow-head">
          <h3 style={{ margin: 0 }}>Combined readiness</h3>
          <span className="combined-pct">{Math.round(p.combined_readiness * 100)}%</span>
        </div>
        <Bar frac={p.combined_readiness} />
        <div className="muted small">
          {p.dkt.active
            ? "DKT active — the global model is driving selection."
            : `DKT warming up — ${p.dkt.answered}/${p.dkt.gate} interactions until it activates.`}
        </div>
        {p.fsrs_fit && (
          <div className="muted small">
            {p.fsrs_fit.fitted
              ? "🧠 FSRS personally fitted — intervals match how you forget."
              : `🧠 Personal FSRS fit at ${Math.min(p.fsrs_fit.reviews, p.fsrs_fit.gate)}/${p.fsrs_fit.gate} reviews (then run engine.cli.fsrs_fit).`}
          </div>
        )}
      </section>

      {Object.keys(groupByDomain(p.subjects)).sort().map((domain) => (
        <section className="card" key={domain}>
          <h3>{domain}</h3>
          {ranked(groupByDomain(p.subjects)[domain]).map((s) => {
            const started = s.seen > 0;
            return (
              <button className="srow srow-btn" key={s.subject} onClick={() => onStudy(s.subject)}>
                <div className="srow-head">
                  <span>
                    {SUBJECT_ICON[s.subject] ?? "📚"} {s.subject}
                  </span>
                  <span className={started ? "" : "muted"}>
                    {started ? `${Math.round(s.readiness * 100)}%` : "Start →"}
                  </span>
                </div>
                <Bar frac={started ? s.readiness : 0} started={started} />
                <div className="muted small">
                  {started
                    ? `seen ${s.seen}/${s.n_concepts} · mastered ${s.mastered} · due ${s.due} · ${Math.round(s.accuracy * 100)}% correct`
                    : `${s.n_concepts} concepts · not started yet`}
                  {s.days_left !== null && (
                    <span className={s.days_left <= 14 ? "exam-soon" : ""}>
                      {" · 📅 "}
                      {s.days_left < 0
                        ? "exam passed"
                        : s.days_left === 0
                          ? "exam today!"
                          : `${s.days_left}d to exam`}
                      {s.pace_new_per_day !== null && ` · ${s.pace_new_per_day} new/day to cover it`}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </section>
      ))}
    </div>
  );
}
