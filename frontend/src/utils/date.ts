export const isoToday = () => new Date().toISOString().slice(0, 10);

export const formatHumanDate = (iso: string) =>
  new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long" }).format(new Date(`${iso}T12:00:00`));

export const isSunday = (iso: string) => new Date(`${iso}T12:00:00`).getDay() === 0;

export const startOfWeek = (date = new Date()) => {
  const d = new Date(date);
  const day = d.getDay() || 7;
  d.setDate(d.getDate() - day + 1);
  d.setHours(0, 0, 0, 0);
  return d;
};

export const toIso = (date: Date) => date.toISOString().slice(0, 10);

export const weekDays = (base = new Date()) => {
  const start = startOfWeek(base);
  return Array.from({ length: 7 }, (_, index) => {
    const d = new Date(start);
    d.setDate(start.getDate() + index);
    return toIso(d);
  });
};

export const sameWeek = (iso: string, base = new Date()) => weekDays(base).includes(iso);

export const addDays = (iso: string, days: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return toIso(d);
};
