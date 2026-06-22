export interface Subject {
  key: string;
  title: string;
  blurb: string;
}

export interface NextItem {
  done: boolean;
  item_id?: number;
  concept_id?: string;
  concept_name?: string;
  subject?: string;
  reason?: string;
  mode?: string;
  question?: string;
  choices?: string[];
  note?: string | null;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_answer: string;
  grade: number;
  label: string;
  steps: string[];
  reward: string;
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
  concepts: ConceptRow[];
}

export interface Progress {
  combined_readiness: number;
  subjects: SubjectProgress[];
  dkt: { active: boolean; answered: number; gate: number };
}
