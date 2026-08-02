// Practice pace for Exam P: amber past 3 minutes (tighter than the real ~6 min/Q).
// Server mirror: EXAM_TIMER_TARGET_S in engine/config.py.
const TARGET_S = 180;

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

/**
 * Count-up question timer, turning amber past the pace target.
 *
 * Shows *active* time — the clock is driven by `useActiveElapsed`, which stops
 * while the tab is hidden, so the number here is the same one that gets graded
 * rather than wall clock since the question appeared.
 */
export default function QuestionTimer({ elapsedMs }: { elapsedMs: number }) {
  const elapsed = Math.max(0, Math.floor(elapsedMs / 1000));
  const over = elapsed >= TARGET_S;
  return (
    <span className={over ? "qtimer over" : "qtimer"} title="Exam P pace · target 3:00 of active time">
      ⏱ {fmt(elapsed)}
    </span>
  );
}
