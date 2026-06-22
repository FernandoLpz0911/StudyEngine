import { useEffect, useState } from "react";
import { api } from "../api";
import type { Me, Progress, SubjectProgress } from "../types";

function Bar({ frac }: { frac: number }) {
  const pct = Math.round(frac * 100);
  const color = frac >= 0.7 ? "var(--green)" : frac >= 0.4 ? "var(--yellow)" : "var(--red)";
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

export default function Dashboard() {
  const [p, setP] = useState<Progress | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.progress().then(setP).catch((e) => setError(String(e)));
    api.me().then(setMe).catch(() => {});
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!p) return <div className="muted">Loading…</div>;

  const byDomain = groupByDomain(p.subjects);
  return (
    <div className="dash">
      {me && (
        <section className="card">
          <h2>
            🔥 {me.streak_days}-day streak · ⭐ Lvl {me.level}
            {me.freezes > 0 && ` · 🧊 ${me.freezes}`}
          </h2>
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
                title={a.desc}
              >
                {a.name}
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
        <h2>Combined readiness</h2>
        <div className="combined">{Math.round(p.combined_readiness * 100)}%</div>
        <Bar frac={p.combined_readiness} />
        <div className="muted">
          {p.dkt.active
            ? "DKT active — the global model is driving selection."
            : `DKT warming up — ${p.dkt.answered}/${p.dkt.gate} interactions until it activates.`}
        </div>
      </section>

      {Object.keys(byDomain).sort().map((domain) => (
        <section className="card" key={domain}>
          <h3>{domain}</h3>
          {byDomain[domain].map((s) => (
            <div className="srow" key={s.subject}>
              <div className="srow-head">
                <span>{s.subject}</span>
                <span>{Math.round(s.readiness * 100)}%</span>
              </div>
              <Bar frac={s.readiness} />
              <div className="muted small">
                seen {s.seen}/{s.n_concepts} · mastered {s.mastered} · due {s.due} ·{" "}
                {Math.round(s.accuracy * 100)}% correct
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
