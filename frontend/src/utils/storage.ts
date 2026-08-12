import { AIItem, AppData, DailyEntry, Goals, HistoryChapter, InternshipApplication } from "../types";
import { addDays, isoToday } from "./date";

const KEY = "life-tracker-data-v1";

const defaultGoals: Goals = {
  physical: "Acercarme a 75 kg lean midiendo peso, energia, entrenos y constancia.",
  languages: "Portugues y frances 30 min de lunes a sabado; domingo un video de cada idioma.",
  ai: "Construir base seria de IA: prompting, agentes, APIs, workflows, RAG y evaluacion.",
  history: "Terminar entre 5 y 8 capitulos con presentacion antes de septiembre.",
  internships: "Desde julio, trackear ofertas, solicitudes, respuestas y entrevistas.",
};

const entry = (daysAgo: number, overrides: Partial<DailyEntry>): DailyEntry => {
  const date = addDays(isoToday(), -daysAgo);
  return {
    id: crypto.randomUUID(),
    date,
    energy: 4,
    sleepHours: 7.5,
    weight: 78.2 - daysAgo * 0.05,
    gymCardio: true,
    boxing: false,
    physicalComment: "Sesion solida.",
    portugueseMinutes: 30,
    frenchMinutes: 30,
    sundayPortugueseVideo: false,
    sundayFrenchVideo: false,
    aiMinutes: 60,
    aiLearned: "Conceptos de agentes y evaluacion.",
    aiType: "curso",
    historyMinutes: 20,
    historyChapter: "3300-3000 a.C.",
    historyProgress: 35,
    historyPresentation: false,
    applicationsSent: 0,
    offersReviewed: 1,
    importantAction: true,
    lifeComment: "Revise opciones y ordene prioridades.",
    bestProgress: "Mantuve idiomas sin friccion.",
    mainBlocker: "Me falto un bloque mas largo de IA.",
    ...overrides,
  };
};

export const sampleData = (): AppData => ({
  entries: [
    entry(0, { boxing: true, aiMinutes: 75, energy: 4, bestProgress: "Buen entrenamiento y avance en IA." }),
    entry(1, { gymCardio: false, boxing: false, aiMinutes: 20, historyMinutes: 65, energy: 3, historyProgress: 48 }),
    entry(2, { portugueseMinutes: 35, frenchMinutes: 25, offersReviewed: 0, importantAction: false, energy: 3 }),
    entry(3, { boxing: true, aiMinutes: 90, applicationsSent: 1, offersReviewed: 3, energy: 5 }),
    entry(4, { historyMinutes: 70, historyPresentation: true, aiMinutes: 10, energy: 4 }),
    entry(5, { gymCardio: false, portugueseMinutes: 30, frenchMinutes: 30, aiMinutes: 45, energy: 3 }),
  ],
  chapters: [
    {
      id: crypto.randomUUID(),
      name: "Primeras ciudades y escritura",
      period: "3300-3000 a.C.",
      estimatedHours: 5,
      completedHours: 2.4,
      status: "en progreso",
      presentationDone: false,
      notes: "Conectar Mesopotamia, urbanizacion y administracion.",
    },
    {
      id: crypto.randomUUID(),
      name: "Revolucion agricola tardia",
      period: "9000-4000 a.C.",
      estimatedHours: 5,
      completedHours: 5,
      status: "terminado",
      presentationDone: true,
      notes: "Presentacion completada.",
      completedDate: addDays(isoToday(), -12),
    },
  ],
  aiItems: [
    {
      id: crypto.randomUUID(),
      title: "Curso base de agentes",
      lesson: "Arquitectura de herramientas",
      concept: "Planificacion y evaluacion",
      miniProject: "Mini asistente con checklist",
      category: "Agentes",
      mastery: 3,
      appliedToBusiness: true,
      date: isoToday(),
    },
  ],
  internships: [
    {
      id: crypto.randomUUID(),
      company: "Empresa ejemplo",
      role: "Practicas producto / IA",
      applicationDate: isoToday(),
      status: "guardada",
      link: "https://example.com",
      notes: "Revisar en julio.",
      nextFollowUp: addDays(isoToday(), 7),
    },
  ],
  goals: defaultGoals,
});

const read = (): AppData => {
  const raw = localStorage.getItem(KEY);
  if (!raw) {
    const data = sampleData();
    localStorage.setItem(KEY, JSON.stringify(data));
    return data;
  }
  return JSON.parse(raw) as AppData;
};

const write = (data: AppData) => localStorage.setItem(KEY, JSON.stringify(data));

export const getData = () => read();
export const saveData = (data: AppData) => write(data);
export const getEntries = () => read().entries;
export const saveEntry = (entry: DailyEntry) => {
  const data = read();
  data.entries = [...data.entries.filter((item) => item.date !== entry.date), entry].sort((a, b) => b.date.localeCompare(a.date));
  write(data);
};
export const updateEntry = saveEntry;
export const deleteEntry = (id: string) => {
  const data = read();
  data.entries = data.entries.filter((entry) => entry.id !== id);
  write(data);
};
export const getGoals = () => read().goals;
export const saveGoals = (goals: Goals) => {
  const data = read();
  data.goals = goals;
  write(data);
};
export const exportData = () => JSON.stringify(read(), null, 2);
export const importData = (json: string) => {
  const data = JSON.parse(json) as AppData;
  write(data);
  return data;
};
export const resetToSample = () => {
  const data = sampleData();
  write(data);
  return data;
};
export const clearAllData = () => {
  const data: AppData = { entries: [], chapters: [], aiItems: [], internships: [], goals: defaultGoals };
  write(data);
  return data;
};
export const upsertChapter = (chapter: HistoryChapter) => {
  const data = read();
  data.chapters = [chapter, ...data.chapters.filter((item) => item.id !== chapter.id)];
  write(data);
};
export const upsertAIItem = (item: AIItem) => {
  const data = read();
  data.aiItems = [item, ...data.aiItems.filter((current) => current.id !== item.id)];
  write(data);
};
export const upsertInternship = (item: InternshipApplication) => {
  const data = read();
  data.internships = [item, ...data.internships.filter((current) => current.id !== item.id)];
  write(data);
};
