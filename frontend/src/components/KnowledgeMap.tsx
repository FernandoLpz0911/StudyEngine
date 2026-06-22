import { useEffect, useState } from "react";
import { api } from "../api";
import type { Progress, SubjectProgress } from "../types";

/** Foggy gray at 0 mastery → bright green at 1 — the "unfogging" effect. */
function nodeColor(mastery: number): string {
  const lightness = 22 + Math.round(mastery * 53);
  const saturation = Math.round(mastery * 70);
  return `hsl(140, ${saturation}%, ${lightness}%)`;
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

export default function KnowledgeMap() {
  const [p, setP] = useState<Progress | null>(null);
  useEffect(() => {
    api.progress().then(setP).catch(() => {});
  }, []);

  if (!p) return <div className="muted">Loading…</div>;
  const byDomain = groupByDomain(p.subjects);

  const concepts = p.subjects.flatMap((s) => s.concepts);
  const total = concepts.length || 1;
  const unfogged = concepts.reduce((a, c) => a + c.mastery, 0) / total;
  const lit = concepts.filter((c) => c.mastery > 0).length;
  const mastered = p.subjects.reduce((a, s) => a + s.mastered, 0);
  const foggy = total - lit;

  return (
    <div className="map">
      <section className="unfog-hero">
        <div className="unfog-pct">{Math.round(unfogged * 100)}%</div>
        <div className="unfog-label">of your knowledge map unfogged</div>
        <div className="bar">
          <div
            className="bar-fill"
            style={{ width: `${Math.round(unfogged * 100)}%`, background: "var(--green)" }}
          />
        </div>
        <div className="unfog-stats muted small">
          🟢 {mastered} mastered · ✨ {lit}/{total} lit ·{" "}
          {foggy > 0 ? `🌫️ ${foggy} still in the fog` : "🎉 every concept touched"}
        </div>
      </section>
      <p className="muted">
        Each node is a concept — it brightens as you master it and dims as it fades.
      </p>
      {Object.keys(byDomain).sort().map((domain) => (
        <section key={domain}>
          <h3>{domain}</h3>
          {byDomain[domain].map((s) => (
            <div className="map-subject" key={s.subject}>
              <div className="map-label">
                {s.subject} <span className="muted">({Math.round(s.readiness * 100)}%)</span>
              </div>
              <div className="nodes">
                {s.concepts.map((c) => (
                  <span
                    key={c.id}
                    className={c.due ? "node due" : "node"}
                    title={`${c.name} — ${Math.round(c.mastery * 100)}%${c.due ? " · due" : ""}`}
                    style={{ background: nodeColor(c.displayed) }}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
