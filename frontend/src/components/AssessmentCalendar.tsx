import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { Assessment } from "../api";

const weekDays = ["L", "M", "X", "J", "V", "S", "D"];
const monthNames = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const humanDate = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });

export default function AssessmentCalendar({ assessments, loading, onClose }: { assessments: Assessment[]; loading: boolean; onClose: () => void }) {
  const upcoming = useMemo(() => assessments.filter((item) => item.assessment_date && item.status !== "completed" && item.assessment_date >= dateKey(new Date())).sort((a, b) => (a.assessment_date ?? "").localeCompare(b.assessment_date ?? "")), [assessments]);
  const [month, setMonth] = useState(() => new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(upcoming[0]?.assessment_date ?? null);
  const eventsByDate = useMemo(() => upcoming.reduce((groups, item) => {
    const date = item.assessment_date!;
    groups.set(date, [...(groups.get(date) ?? []), item]);
    return groups;
  }, new Map<string, Assessment[]>()), [upcoming]);
  const selected = selectedDate ? eventsByDate.get(selectedDate) ?? [] : [];
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const cells = Array.from({ length: Math.ceil((offset + new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()) / 7) * 7 }, (_, index) => {
    const day = index - offset + 1;
    return day < 1 || day > new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate() ? null : new Date(month.getFullYear(), month.getMonth(), day);
  });

  return <div className="uc-calendar-backdrop" role="presentation" onMouseDown={onClose}><section className="uc-calendar-modal" role="dialog" aria-modal="true" aria-label="Calendario de evaluaciones" onMouseDown={(event) => event.stopPropagation()}><header><div><p className="uc-eyebrow">Planificación académica</p><h2>Calendario de evaluaciones</h2></div><button onClick={onClose} aria-label="Cerrar calendario"><X size={18} /></button></header>{loading ? <p className="uc-calendar-state">Cargando evaluaciones…</p> : <div className="uc-calendar-layout"><div><div className="uc-calendar-month-head"><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Mes anterior"><ChevronLeft size={17} /></button><strong>{monthNames[month.getMonth()]} de {month.getFullYear()}</strong><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Mes siguiente"><ChevronRight size={17} /></button></div><div className="uc-calendar-grid">{weekDays.map((day) => <span key={day}>{day}</span>)}{cells.map((day, index) => { const key = day ? dateKey(day) : "empty"; const hasEvents = day && eventsByDate.has(key); return <button key={`${key}-${index}`} disabled={!day} className={`${hasEvents ? "has-events" : ""} ${key === selectedDate ? "is-selected" : ""}`} onClick={() => hasEvents && setSelectedDate(key)}>{day?.getDate()}{hasEvents && <i />}</button>; })}</div></div><aside><p className="uc-eyebrow">{selectedDate ? humanDate(selectedDate) : "Selecciona una fecha"}</p>{selected.length ? selected.map((item) => <article key={item.id}><strong>{item.title}</strong><span>{item.subject_name ?? "Asignatura"} · {item.assessment_type}</span><small>{item.weight_percentage != null ? `${item.weight_percentage}% de la nota` : "Peso no registrado"}</small></article>) : <p className="uc-calendar-empty">Elige un día marcado para ver sus evaluaciones.</p>}<div className="uc-upcoming-list"><p className="uc-eyebrow">Próximas evaluaciones</p>{upcoming.length ? upcoming.slice(0, 5).map((item) => <button key={item.id} onClick={() => { setSelectedDate(item.assessment_date); setMonth(new Date(`${item.assessment_date}T00:00:00`)); }}><span>{humanDate(item.assessment_date!)}</span><strong>{item.title}</strong><small>{item.subject_name ?? "Asignatura"}</small></button>) : <p className="uc-calendar-empty">No hay evaluaciones próximas registradas.</p>}</div></aside></div>}</section></div>;
}
