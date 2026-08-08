import { useEffect, useState } from "react";
import { api } from "../api";
import type { Progress, SubjectAscent, SubjectProgress } from "../types";

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

export default function KnowledgeMap({ onStudy }: { onStudy: (scope: string) => void }) {
  const [p, setP] = useState<Progress | null>(null);
  const [ascents, setAscents] = useState<SubjectAscent[]>([]);
  useEffect(() => {
    api.progress().then(setP).catch(() => {});
  }, []);
  // The hero is Ascent, not mastery: mastery reads unaided evidence only, so a
  // week of legitimate guided work leaves it flat. Ascent is the number that
  // moves when you are being taught, which is what this surface is for.
  useEffect(() => {
    if (!p) return;
    Promise.all(p.subjects.map((s) => api.ascent(s.subject).catch(() => null)))
      .then((rows) => setAscents(rows.filter((r): r is SubjectAscent => r !== null)));
  }, [p]);

  if (!p) return <div className="muted">Loading…</div>;
  const byDomain = groupByDomain(p.subjects);

  const concepts = p.subjects.flatMap((s) => s.concepts);
  const total = concepts.length || 1;
  const mastered = p.subjects.reduce((a, s) => a + s.mastered, 0);
  const climbed = ascents.length
    ? ascents.reduce((a, s) => a + s.ascent * s.concepts.length, 0) /
      ascents.reduce((a, s) => a + s.concepts.length, 0)
    : 0;
  const atStudy = ascents.reduce((a, s) => a + s.at_study, 0);
  const atPaired = ascents.reduce((a, s) => a + s.at_paired, 0);
  const atSolo = ascents.reduce((a, s) => a + s.at_solo, 0);

  return (
    <div className="map">
      <section className="unfog-hero">
        <div className="unfog-pct">{Math.round(climbed * 100)}%</div>
        <div className="unfog-label">climbed — how much you can do with less help</div>
        <div className="bar">
          <div
            className="bar-fill"
            style={{ width: `${Math.round(climbed * 100)}%`, background: "var(--green)" }}
          />
        </div>
        <div className="unfog-stats muted small">
          📘 {atStudy} being taught · 🪜 {atPaired} guided · ✍️ {atSolo} unaided ·{" "}
          🟢 {mastered}/{total} mastered
        </div>
      </section>
      <p className="muted">
        Each node is a concept — it brightens with unaided mastery and dims as that fades. The bar above tracks something different: how far up the teaching ladder you have climbed.
      </p>
      {Object.keys(byDomain).sort().map((domain) => (
        <section key={domain}>
          <h3>{domain}</h3>
          {byDomain[domain].map((s) => (
            <div className="map-subject" key={s.subject}>
              <button className="map-label map-label-btn" onClick={() => onStudy(s.subject)}>
                {s.subject} <span className="muted">({Math.round(s.readiness * 100)}%)</span>
                <span className="muted small"> · study →</span>
              </button>
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
