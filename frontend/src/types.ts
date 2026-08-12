export type AreaKey = "physical" | "languages" | "ai" | "history" | "life";

export type AIType = "curso" | "practica" | "lectura" | "proyecto" | "investigacion";
export type ChapterStatus = "pendiente" | "en progreso" | "terminado";
export type InternshipStatus = "guardada" | "aplicada" | "respuesta" | "entrevista" | "rechazada" | "oferta";
export type AICategory =
  | "Prompting"
  | "Agentes"
  | "APIs"
  | "Workflows"
  | "Automatizaciones"
  | "RAG"
  | "Evaluacion"
  | "Herramientas"
  | "Fundamentos"
  | "Otros";

export interface DailyEntry {
  id: string;
  date: string;
  energy: number;
  sleepHours: number;
  weight?: number;
  gymCardio: boolean;
  boxing: boolean;
  physicalComment: string;
  portugueseMinutes: number;
  frenchMinutes: number;
  sundayPortugueseVideo: boolean;
  sundayFrenchVideo: boolean;
  aiMinutes: number;
  aiLearned: string;
  aiType: AIType;
  historyMinutes: number;
  historyChapter: string;
  historyProgress: number;
  historyPresentation: boolean;
  applicationsSent: number;
  offersReviewed: number;
  importantAction: boolean;
  lifeComment: string;
  bestProgress: string;
  mainBlocker: string;
}

export interface HistoryChapter {
  id: string;
  name: string;
  period: string;
  estimatedHours: number;
  completedHours: number;
  status: ChapterStatus;
  presentationDone: boolean;
  notes: string;
  completedDate?: string;
}

export interface AIItem {
  id: string;
  title: string;
  lesson: string;
  concept: string;
  miniProject: string;
  category: AICategory;
  mastery: number;
  appliedToBusiness: boolean;
  date: string;
}

export interface InternshipApplication {
  id: string;
  company: string;
  role: string;
  applicationDate: string;
  status: InternshipStatus;
  link: string;
  notes: string;
  nextFollowUp?: string;
}

export interface Goals {
  physical: string;
  languages: string;
  ai: string;
  history: string;
  internships: string;
}

export interface AppData {
  entries: DailyEntry[];
  chapters: HistoryChapter[];
  aiItems: AIItem[];
  internships: InternshipApplication[];
  goals: Goals;
}
