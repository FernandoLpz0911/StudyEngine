import { useEffect, useState } from "react";
import { api } from "../api";
import type { Progress, SubjectProgress } from "../types";

function Bar({ frac }: { frac: number }) {
  const pct = Math.round(frac * 100);
  const color = frac >= 0.7 ? "var(--green)" : frac >= 0.4 ? "var(--yellow)" : "var(--red)";
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.progress().then(setP).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!p) return <div className="muted">Loading…</div>;

  const byDomain = groupByDomain(p.subjects);
  return (
    <div className="dash">
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
