/** Client for the StudyEngine FastAPI backend (proxied at /api by Vite). */
import type {
  AnswerResult,
  Me,
  NextItem,
  Profile,
  Progress,
  Subject,
  SubjectProgress,
} from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`GET ${path} → ${resp.status}`);
  return resp.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`POST ${path} → ${resp.status}`);
  return resp.json() as Promise<T>;
}

export const api = {
  subjects: () => get<Subject[]>("/subjects"),
  startSession: (scope: string) =>
    post<{ session_id: number; scope: string; dkt_active: boolean }>("/session", { scope }),
  next: (sessionId: number) => get<NextItem>(`/session/${sessionId}/next`),
  answer: (sessionId: number, itemId: number, answer: string, elapsedMs: number) =>
    post<AnswerResult>("/answer", {
      session_id: sessionId,
      item_id: itemId,
      answer,
      elapsed_ms: elapsedMs,
    }),
  mnemonic: (conceptId: string, text: string) =>
    post<{ ok: boolean }>("/mnemonic", { concept_id: conceptId, text }),
  stats: () => get<Profile>("/stats"),
  me: () => get<Me>("/me"),
  progress: () => get<Progress>("/progress"),
  subjectProgress: (subject: string) => get<SubjectProgress>(`/progress/${subject}`),
};
