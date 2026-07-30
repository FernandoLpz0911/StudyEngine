import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { GateStatus } from "../types";
import StudyView from "./StudyView";

/**
 * The gate's own chrome around the ordinary study loop.
 *
 * Deliberately shows the *correct* count rather than the daily-goal ring: the
 * gate is paid in work done, not attempts made, and the two numbers diverge
 * (ADR-0005). Showing the ring here would tell the learner they are finished
 * while the gate is still shut.
 */
const POLL_MS = 4000;

function Bail({ status, onBailed }: { status: GateStatus; onBailed: () => void }) {
  const [arming, setArming] = useState(false);
  const [busy, setBusy] = useState(false);
  const spent = status.bails_ration - status.bails_left;

  if (status.bails_left <= 0) {
    return (
      <span className="gate-bail-out" title="All bails spent in the last 30 days">
        no bails left ({spent}/{status.bails_ration} used)
      </span>
    );
  }
  if (!arming) {
    return (
      <button className="gate-bail" onClick={() => setArming(true)}>
        emergency bail · {status.bails_left} of {status.bails_ration} left
      </button>
    );
  }
  return (
    <span className="gate-bail-confirm">
      Spend one of {status.bails_left}?
      <button
        className="gate-bail danger"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api.gateBail();
            onBailed();
          } finally {
            setBusy(false);
          }
        }}
      >
        yes, open it
      </button>
      <button className="gate-bail" onClick={() => setArming(false)}>
        no, keep going
      </button>
    </span>
  );
}

export default function GateView() {
  const [status, setStatus] = useState<GateStatus | null>(null);

  const refresh = useCallback(() => {
    api.gate().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  if (!status) return <div className="gate-loading">…</div>;

  const pct = Math.min(100, Math.round((100 * status.correct) / status.quota));

  return (
    <div className="gate">
      <header className="gate-head">
        <div className="gate-title">
          <strong>StudyGate</strong>
          <span className="muted">
            {status.remaining} more correct to unlock this machine
          </span>
          <span className={status.coverage_on_track ? "gate-pace muted" : "gate-pace behind"}>
            mastered {status.concepts_mastered}/{status.concepts_total} · seen{" "}
            {status.concepts_seen}/{status.concepts_total} ·{" "}
            {status.coverage_on_track ? "coverage on track" : "behind on coverage"}
          </span>
        </div>
        <div className="gate-progress">
          <div className="gate-count">
            {status.correct} / {status.quota} correct
          </div>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
        {status.days_left !== null && (
          <div className="gate-countdown">
            <strong>{status.days_left}</strong>
            <span className="muted">days to Exam P</span>
          </div>
        )}
      </header>

      <main className="gate-body">
        <StudyView initialScope={status.subject} lockScope />
      </main>

      <footer className="gate-foot">
        <span className="muted small">
          Wrong answers don't count, but the concept comes back — keep going.
        </span>
        <Bail status={status} onBailed={refresh} />
      </footer>
    </div>
  );
}
