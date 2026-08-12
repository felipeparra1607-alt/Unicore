import { AreaKey, DailyEntry, HistoryChapter } from "../types";
import { addDays, isSunday, sameWeek, weekDays } from "./date";

export const areaLabels: Record<AreaKey, string> = {
  physical: "Fisico",
  languages: "Idiomas",
  ai: "IA",
  history: "Historia",
  life: "Practicas / vida",
};

export const areaDone = (entry: DailyEntry): Record<AreaKey, boolean> => {
  const physical = entry.gymCardio || entry.boxing;
  const languages = isSunday(entry.date)
    ? entry.sundayPortugueseVideo && entry.sundayFrenchVideo
    : entry.portugueseMinutes >= 30 && entry.frenchMinutes >= 30;
  const learning = entry.aiMinutes >= 45 || entry.historyMinutes >= 45;
  return {
    physical,
    languages,
    ai: learning && entry.aiMinutes >= entry.historyMinutes,
    history: learning && entry.historyMinutes > entry.aiMinutes,
    life: entry.applicationsSent > 0 || entry.offersReviewed > 0 || entry.importantAction,
  };
};

export const calculateDailyPoints = (entry: DailyEntry) => {
  const done = areaDone(entry);
  const reflection = Boolean(entry.bestProgress.trim() || entry.mainBlocker.trim());
  return Number(done.physical) + Number(done.languages) + Number(entry.aiMinutes >= 45 || entry.historyMinutes >= 45) + Number(done.life) + Number(reflection);
};

export const weeklyEntries = (entries: DailyEntry[], base = new Date()) =>
  entries.filter((entry) => sameWeek(entry.date, base)).sort((a, b) => a.date.localeCompare(b.date));

export const calculateWeeklyPoints = (entries: DailyEntry[], base = new Date()) =>
  weeklyEntries(entries, base).reduce((sum, entry) => sum + calculateDailyPoints(entry), 0);

export const weeklyLevel = (points: number) => {
  if (points <= 17) return "semana floja";
  if (points <= 24) return "aceptable";
  if (points <= 30) return "buena";
  return "muy fuerte";
};

export const areaCompletion = (entries: DailyEntry[], base = new Date()) => {
  const week = weeklyEntries(entries, base);
  const totals: Record<AreaKey, number> = { physical: 0, languages: 0, ai: 0, history: 0, life: 0 };
  week.forEach((entry) => {
    const done = areaDone(entry);
    Object.keys(done).forEach((key) => {
      totals[key as AreaKey] += Number(done[key as AreaKey]);
    });
  });
  const denominator = Math.max(week.length, 1);
  return Object.fromEntries(Object.entries(totals).map(([key, value]) => [key, Math.round((value / denominator) * 100)])) as Record<AreaKey, number>;
};

export const strongestArea = (entries: DailyEntry[], base = new Date()) => {
  const completion = areaCompletion(entries, base);
  return (Object.keys(completion) as AreaKey[]).sort((a, b) => completion[b] - completion[a])[0];
};

export const weakestArea = (entries: DailyEntry[], base = new Date()) => {
  const completion = areaCompletion(entries, base);
  return (Object.keys(completion) as AreaKey[]).sort((a, b) => completion[a] - completion[b])[0];
};

export const averageEnergy = (entries: DailyEntry[], base = new Date()) => {
  const week = weeklyEntries(entries, base);
  if (!week.length) return 0;
  return Number((week.reduce((sum, entry) => sum + entry.energy, 0) / week.length).toFixed(1));
};

export const calculateStreak = (entries: DailyEntry[]) => {
  const dates = new Set(entries.map((entry) => entry.date));
  let cursor = new Date();
  let streak = 0;
  while (dates.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
};

export const minutesByArea = (entries: DailyEntry[], base = new Date()) => {
  const week = weeklyEntries(entries, base);
  return [
    { name: "Portugues", minutes: week.reduce((sum, entry) => sum + entry.portugueseMinutes, 0) },
    { name: "Frances", minutes: week.reduce((sum, entry) => sum + entry.frenchMinutes, 0) },
    { name: "IA", minutes: week.reduce((sum, entry) => sum + entry.aiMinutes, 0) },
    { name: "Historia", minutes: week.reduce((sum, entry) => sum + entry.historyMinutes, 0) },
  ];
};

export const weeklyEvolution = (entries: DailyEntry[]) => {
  const sorted = [...entries].sort((a, b) => a.date.localeCompare(b.date));
  const buckets = new Map<string, number>();
  sorted.forEach((entry) => {
    const d = new Date(`${entry.date}T12:00:00`);
    const monday = weekDays(d)[0];
    buckets.set(monday, (buckets.get(monday) || 0) + calculateDailyPoints(entry));
  });
  return Array.from(buckets.entries()).map(([week, points]) => ({ week, points }));
};

export const detectPattern = (entries: DailyEntry[], base = new Date()) => {
  const week = weeklyEntries(entries, base);
  const lowEnergy = averageEnergy(entries, base) < 3;
  const openTasks = week.filter((entry) => !areaDone(entry).life).length >= 3;
  const goodHabits = week.filter((entry) => areaDone(entry).physical && areaDone(entry).languages).length >= 3;
  if (lowEnergy) return "La energia media fue baja: conviene ajustar descanso o carga.";
  if (goodHabits && openTasks) return "Cumples habitos cerrados, pero las tareas abiertas se quedan atras.";
  if (week.length < 4) return "Faltan registros para detectar un patron fiable.";
  return "La semana fue bastante estable: el patron principal es mantener bloques repetibles.";
};

export const historyStalled = (chapters: HistoryChapter[]) =>
  chapters.every((chapter) => chapter.status !== "terminado") && chapters.reduce((sum, chapter) => sum + chapter.completedHours, 0) < 2;

export const generateWeeklySummary = (entries: DailyEntry[], chapters: HistoryChapter[] = [], base = new Date()) => {
  const completion = areaCompletion(entries, base);
  const strong = strongestArea(entries, base);
  const weak = weakestArea(entries, base);
  const energy = averageEnergy(entries, base);
  const points = calculateWeeklyPoints(entries, base);
  const highlights = (Object.keys(completion) as AreaKey[]).filter((key) => completion[key] >= 80).map((key) => areaLabels[key]);
  const weakText = completion.ai < 50 ? "IA fue un area claramente descuidada." : `${areaLabels[weak]} necesita mas atencion.`;
  const historyText = historyStalled(chapters) ? " Historia se esta quedando parada: reserva un bloque real para avanzar capitulo." : "";
  const energyText = energy && energy < 3 ? " Tu energia fue baja, asi que baja la carga o protege mejor el descanso." : "";
  const action = completion.ai < 50
    ? "Bloquea 3 sesiones de 90 minutos para IA."
    : completion.life < 50
      ? "Define 2 acciones concretas de practicas/proyectos antes del miercoles."
      : "Mantén la estructura y sube un poco el area mas debil.";
  return {
    standout: highlights.length ? `Destacaste en ${highlights.join(" e ")}.` : `Tu mejor area fue ${areaLabels[strong]}.`,
    neglected: weakText,
    pattern: detectPattern(entries, base),
    improve: `${areaLabels[weak]} es la palanca principal de mejora esta semana.`,
    action,
    priority: areaLabels[weak],
    coachText: `Semana ${weeklyLevel(points)} con ${points}/35 puntos. ${highlights.length ? `Vas fuerte en ${highlights.join(" e ")}.` : `Lo mas solido fue ${areaLabels[strong]}.`} ${weakText}${historyText}${energyText} La proxima semana: ${action}`,
  };
};

export const emptyEntryForDate = (date: string): DailyEntry => ({
  id: crypto.randomUUID(),
  date,
  energy: 3,
  sleepHours: 7,
  gymCardio: false,
  boxing: false,
  physicalComment: "",
  portugueseMinutes: 0,
  frenchMinutes: 0,
  sundayPortugueseVideo: false,
  sundayFrenchVideo: false,
  aiMinutes: 0,
  aiLearned: "",
  aiType: "curso",
  historyMinutes: 0,
  historyChapter: "",
  historyProgress: 0,
  historyPresentation: false,
  applicationsSent: 0,
  offersReviewed: 0,
  importantAction: false,
  lifeComment: "",
  bestProgress: "",
  mainBlocker: "",
});

export const duplicateForToday = (entry: DailyEntry, date: string): DailyEntry => ({
  ...entry,
  id: crypto.randomUUID(),
  date,
  bestProgress: "",
  mainBlocker: "",
});

export const chartWeekRows = (entries: DailyEntry[], base = new Date()) =>
  weekDays(base).map((date) => {
    const entry = entries.find((item) => item.date === date);
    return {
      date: date.slice(5),
      points: entry ? calculateDailyPoints(entry) : 0,
      energy: entry?.energy || 0,
    };
  });

export const recentWeightRows = (entries: DailyEntry[]) =>
  entries
    .filter((entry) => typeof entry.weight === "number")
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-30)
    .map((entry) => ({ date: entry.date.slice(5), weight: entry.weight }));

export const nextDateAfter = (iso: string) => addDays(iso, 1);
