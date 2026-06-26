import { useEffect, useState } from "react";

// Practice pace for Exam P: amber past 3 minutes (tighter than the real ~6 min/Q).
// Server mirror: EXAM_TIMER_TARGET_S in engine/config.py.
const TARGET_S = 180;

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

/** Count-up question timer; freezes on answer, turns amber past the pace target. */
export default function QuestionTimer({
  startedAt,
  frozen,
}: {
  startedAt: number;
  frozen: boolean;
}) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (frozen) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [frozen]);

  const elapsed = Math.max(0, Math.floor(((frozen ? now : Date.now()) - startedAt) / 1000));
  const over = elapsed >= TARGET_S;
  return (
    <span className={over ? "qtimer over" : "qtimer"} title="Exam P pace · target 3:00">
      ⏱ {fmt(elapsed)}
    </span>
  );
}
