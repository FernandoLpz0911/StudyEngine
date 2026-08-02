import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Time actually spent working on the current question.
 *
 * Wall clock from serve to answer is not that: leaving a tab open overnight once
 * logged a single answer at 43 hours, which FSRS reads as an agonisingly slow
 * recall and punishes with a shortened interval. This accumulates only while the
 * page is visible and the window focused.
 *
 * Deliberately *not* idle-on-no-input. An Exam P question is minutes of thinking
 * with a pen and no keyboard, and pausing through that would under-count exactly
 * the questions that take the most work.
 */

// Ticks longer than this are a suspended laptop or a throttled background timer,
// not thinking time, so only the tick itself is dropped and counting resumes.
const MAX_TICK_MS = 2000;
const TICK_MS = 250;

export function useActiveElapsed(frozen: boolean): {
  elapsedMs: number;
  read: () => number;
  reset: () => void;
} {
  const accumulated = useRef(0);
  const lastTick = useRef(Date.now());
  const [, forceRender] = useState(0);

  const engaged = () =>
    typeof document === "undefined" ||
    (document.visibilityState === "visible" && document.hasFocus());

  const settle = useCallback(() => {
    const now = Date.now();
    const delta = now - lastTick.current;
    lastTick.current = now;
    if (engaged() && delta > 0 && delta < MAX_TICK_MS) {
      accumulated.current += delta;
    }
  }, []);

  // Fold in whatever has elapsed before the page goes away, and restart the clock
  // when it comes back so the gap between is never counted.
  useEffect(() => {
    const onChange = () => settle();
    document.addEventListener("visibilitychange", onChange);
    window.addEventListener("blur", onChange);
    window.addEventListener("focus", onChange);
    return () => {
      document.removeEventListener("visibilitychange", onChange);
      window.removeEventListener("blur", onChange);
      window.removeEventListener("focus", onChange);
    };
  }, [settle]);

  useEffect(() => {
    if (frozen) return;
    lastTick.current = Date.now();
    const id = setInterval(() => {
      settle();
      forceRender((n) => n + 1);
    }, TICK_MS);
    return () => clearInterval(id);
  }, [frozen, settle]);

  const read = useCallback(() => {
    settle();
    return Math.round(accumulated.current);
  }, [settle]);

  const reset = useCallback(() => {
    accumulated.current = 0;
    lastTick.current = Date.now();
  }, []);

  return { elapsedMs: Math.round(accumulated.current), read, reset };
}
