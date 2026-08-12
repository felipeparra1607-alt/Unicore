import { BookOpenCheck, CalendarDays, ChevronLeft, ChevronRight, ListTodo } from "lucide-react";
import { useMemo, useState } from "react";
import type { AcademicTask, Assessment } from "../api";

const weekDays = ["L", "M", "X", "J", "V", "S", "D"];
const monthNames = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const keyFor = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const dateLabel = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", { day: "numeric", month: "long" });

type CalendarEvent = { kind: "assessment"; id: number; date: string; title: string; type: string; weight: number | null } | { kind: "task"; id: number; date: string; title: string; priority: number; status: string; progress: number };

export default function SubjectAcademicCalendar({ assessments, tasks, loading }: { assessments: Assessment[]; tasks: AcademicTask[]; loading: boolean }) {
  const events = useMemo<CalendarEvent[]>(() => [
    ...assessments.filter((item) => item.assessment_date).map((item) => ({ kind: "assessment" as const, id: item.id, date: item.assessment_date!, title: item.title, type: item.assessment_type, weight: item.weight_percentage })),
    ...tasks.filter((item) => item.due_date).map((item) => ({ kind: "task" as const, id: item.id, date: item.due_date!, title: item.title, priority: item.priority, status: item.status, progress: item.progress_percentage })),
  ], [assessments, tasks]);
  const grouped = useMemo(() => events.reduce((result, event) => { result.set(event.date, [...(result.get(event.date) ?? []), event]); return result; }, new Map<string, CalendarEvent[]>()), [events]);
  const firstEvent = [...events].sort((a, b) => a.date.localeCompare(b.date))[0];
  const [month, setMonth] = useState(() => firstEvent ? new Date(`${firstEvent.date}T00:00:00`) : new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(firstEvent?.date ?? null);
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (firstDay.getDay() + 6) % 7;
  const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: Math.ceil((offset + count) / 7) * 7 }, (_, index) => { const day = index - offset + 1; return day < 1 || day > count ? null : new Date(month.getFullYear(), month.getMonth(), day); });
  const selected = selectedDate ? grouped.get(selectedDate) ?? [] : [];

  return <section className="uc-subject-calendar"><header className="uc-section-heading"><div><p className="uc-eyebrow">Agenda académica</p><h2>Calendario de la asignatura</h2></div><div className="uc-calendar-legend"><span><BookOpenCheck size={13} /> Evaluación</span><span><ListTodo size={13} /> Tarea</span></div></header>{loading ? <p className="uc-calendar-state">Cargando agenda académica…</p> : <div className="uc-subject-calendar-layout"><div><div className="uc-calendar-month-head"><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Mes anterior"><ChevronLeft size={17} /></button><strong>{monthNames[month.getMonth()]} de {month.getFullYear()}</strong><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Mes siguiente"><ChevronRight size={17} /></button></div><div className="uc-calendar-grid uc-subject-calendar-grid">{weekDays.map((day) => <span key={day}>{day}</span>)}{cells.map((day, index) => { const key = day ? keyFor(day) : "empty"; const dayEvents = day ? grouped.get(key) ?? [] : []; return <button key={`${key}-${index}`} disabled={!day} className={`${dayEvents.length ? "has-events" : ""} ${key === selectedDate ? "is-selected" : ""}`} onClick={() => dayEvents.length && setSelectedDate(key)}>{day?.getDate()}{dayEvents.some((event) => event.kind === "assessment") && <i className="is-assessment" />} {dayEvents.some((event) => event.kind === "task") && <i className="is-task" />}</button>; })}</div></div><aside><p className="uc-eyebrow">{selectedDate ? dateLabel(selectedDate) : "Selecciona una fecha"}</p>{selected.length ? selected.map((event) => event.kind === "assessment" ? <article key={`assessment-${event.id}`}><BookOpenCheck size={15} /><div><strong>{event.title}</strong><span>Evaluación · {event.type}</span><small>{event.weight != null ? `${event.weight}% de la nota · ${dateLabel(event.date)}` : dateLabel(event.date)}</small></div></article> : <article key={`task-${event.id}`}><ListTodo size={15} /><div><strong>{event.title}</strong><span>Tarea · prioridad {event.priority}</span><small>{event.status} · {event.progress}% completada · {dateLabel(event.date)}</small></div></article>) : <p className="uc-calendar-empty">No hay evaluaciones ni tareas con fecha para este día.</p>}<p className="uc-calendar-count"><CalendarDays size={14} /> {events.length} evento{events.length === 1 ? "" : "s"} con fecha</p></aside></div>}</section>;
}
