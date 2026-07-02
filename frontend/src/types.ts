export interface Subject {
  key: string;
  title: string;
  blurb: string;
}

export interface Profile {
  xp: number;
  level: number;
  xp_into_level: number;
  xp_for_next: number;
  streak_days: number;
  studied_today: boolean;
  answered_today: number;
  daily_goal: number;
  due_count: number;
  freezes: number;
}

export interface Achievement {
  id: string;
  name: string;
  desc: string;
  earned: boolean;
  progress: number;
  progress_text: string;
}

export interface Setting {
  key: string;
  value: number;
  default: number;
  description: string;
}

export interface UserCard {
  id: string;
  subject: string;
  question: string;
  answer: string;
  distractors: string[];
}

export interface Bests {
  fastest_ms: number | null;
  best_day: number;
  longest_run: number;
}

export interface Leech {
  id: string;
  name: string;
  subject: string;
  lapses: number;
}

export interface Me extends Profile {
  achievements: Achievement[];
  bests: Bests;
  leeches: Leech[];
  heatmap: string[];
}

export interface SessionSummary extends Profile {
  answered: number;
  correct: number;
  accuracy: number;
  best_streak: number;
  xp_gained: number;
}

export interface NextItem {
  done: boolean;
  item_id?: number;
  concept_id?: string;
  concept_name?: string;
  subject?: string;
  reason?: string;
  mode?: string;
  input_mode?: "typed" | "choices";
  question?: string;
  choices?: string[];
  note?: string | null;
  theory?: string | null;
  cold?: boolean;
  leech?: boolean;
  lapses?: number;
  summary?: SessionSummary;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_answer: string;
  grade: number;
  label: string;
  steps: string[];
  reward: string;
  streak: number;
  combo: string;
  xp_gained: number;
  next_review_days: number | null;
  theory?: string | null;
  why_wrong?: string;
  fatigued?: boolean;
  ask_mnemonic: boolean;
}

export interface ConceptRow {
  id: string;
  name: string;
  mode: string;
  mastery: number;
  displayed: number;
  reps: number;
  due: boolean;
}

export interface SubjectProgress {
  subject: string;
  domain: string | null;
  readiness: number;
  n_concepts: number;
  seen: number;
  mastered: number;
  due: number;
  answered: number;
  accuracy: number;
  exam_date: string | null;
  days_left: number | null;
  pace_new_per_day: number | null;
  concepts: ConceptRow[];
}

export interface Progress {
  combined_readiness: number;
  subjects: SubjectProgress[];
  dkt: { active: boolean; answered: number; gate: number };
  fsrs_fit: { fitted: boolean; reviews: number; gate: number };
}
