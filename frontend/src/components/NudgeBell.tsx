import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

const KEY = "studyengine.nudge";
const STREAK_NUDGE_KEY = "studyengine.streaknudge";
const STREAK_NUDGE_HOUR = 18;
const POLL_MS = 60_000;

/** Header bell: live "reviews waiting" badge + opt-in browser nudges.
 *
 * Local-first — no push server. While the tab is open it polls /stats and, if the
 * learner enabled it, fires one desktop notification per fresh batch of due
 * reviews (the open-loop pull back into the app). A CLI cron job covers nudges
 * while the app is closed (engine.cli.remind). */
export default function NudgeBell() {
  const [due, setDue] = useState(0);
  const [streak, setStreak] = useState(0);
  const [on, setOn] = useState(localStorage.getItem(KEY) === "1");
  const lastNotified = useRef(0);

  const notifyIfDue = useCallback((count: number, days: number) => {
    if (!on || count === 0 || Notification.permission !== "granted") return;
    if (count <= lastNotified.current) return;
    lastNotified.current = count;
    const tail = days ? ` Keep your ${days}-day streak alive 🔥` : "";
    new Notification("StudyEngine", { body: `${count} review(s) waiting.${tail}` });
  }, [on]);

  // Evening loss-aversion nudge: streak alive but nothing answered today — the
  // one notification worth interrupting for. Fires at most once per local day.
  const notifyStreakAtRisk = useCallback((days: number, answeredToday: number) => {
    if (!on || days === 0 || answeredToday > 0) return;
    if (Notification.permission !== "granted") return;
    const now = new Date();
    if (now.getHours() < STREAK_NUDGE_HOUR) return;
    const today = now.toISOString().slice(0, 10);
    if (localStorage.getItem(STREAK_NUDGE_KEY) === today) return;
    localStorage.setItem(STREAK_NUDGE_KEY, today);
    new Notification("StudyEngine", {
      body: `🔥 Your ${days}-day streak dies at midnight — one quick session saves it.`,
    });
  }, [on]);

  const poll = useCallback(() => {
    api.stats().then((p) => {
      setDue(p.due_count);
      setStreak(p.streak_days);
      notifyIfDue(p.due_count, p.streak_days);
      notifyStreakAtRisk(p.streak_days, p.answered_today);
    }).catch(() => {});
  }, [notifyIfDue, notifyStreakAtRisk]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, [poll]);

  const toggle = async () => {
    if (!on) {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return;
      setOn(true);
      localStorage.setItem(KEY, "1");
      lastNotified.current = 0;
      poll();
    } else {
      setOn(false);
      localStorage.setItem(KEY, "0");
    }
  };

  return (
    <button
      className={on ? "bell on" : "bell"}
      onClick={toggle}
      title={on ? "Reminders on — click to mute" : "Enable review reminders"}
    >
      {on ? "🔔" : "🔕"}
      {due > 0 && <span className="bell-badge">{due}</span>}
      {streak > 0 && <span className="bell-streak">🔥{streak}</span>}
    </button>
  );
}
