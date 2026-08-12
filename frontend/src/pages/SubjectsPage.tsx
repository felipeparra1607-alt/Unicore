import { ArrowRight, BookOpen, CalendarDays, ChevronRight, Clock3, RefreshCw, Target, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDashboard, type DashboardData, type DashboardSubject } from "../api";

function formatDate(value: string | null | undefined) {
  if (!value) return "Sin fecha";
  return new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

function subjectState(subject: DashboardSubject) {
  if (subject.pending_task_count > 0) return { label: `${subject.pending_task_count} tarea${subject.pending_task_count === 1 ? "" : "s"} pendiente${subject.pending_task_count === 1 ? "" : "s"}`, tone: "attention" };
  if (subject.grade.required_average_on_remaining != null && subject.grade.required_average_on_remaining > 8) return { label: "Exige atención", tone: "risk" };
  return { label: "En curso", tone: "steady" };
}

export default function SubjectsPage({ onSelect }: { onSelect: (subjectId: number) => void }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [readinessBySubject, setReadinessBySubject] = useState<Record<number, number | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const dashboard = await getDashboard();
      setData(dashboard);
      const readiness = await Promise.all(dashboard.subjects.map(async (subject) => {
        try {
          const detail = await getDashboard(subject.id);
          return [subject.id, detail.next_boss?.readiness_percentage ?? null] as const;
        } catch {
          return [subject.id, null] as const;
        }
      }));
      setReadinessBySubject(Object.fromEntries(readiness));
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron cargar las asignaturas."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  const subjects = useMemo(() => data?.subjects ?? [], [data]);
  const totalMinutes = subjects.reduce((sum, subject) => sum + subject.study_minutes, 0);
  const totalXp = subjects.reduce((sum, subject) => sum + subject.xp, 0);

  if (loading) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Asignaturas</p><h1>Cargando tu espacio académico…</h1><p>Estamos reuniendo tus notas, actividad y prioridades reales.</p></section>;
  if (error || !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Asignaturas</p><h1>No se pudo cargar el estado académico.</h1><p>{error ?? "La API local no devolvió datos."}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;
  if (subjects.length === 0) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Asignaturas</p><h1>Aún no hay asignaturas registradas.</h1><p>Cuando el backend tenga asignaturas, su rendimiento, progreso y prioridades aparecerán aquí.</p></section>;

  return <div className="uc-page-shell uc-subjects-page">
    <header className="uc-page-intro">
      <div><p className="uc-eyebrow">Espacio académico</p><h1>Asignaturas en perspectiva.</h1><p className="uc-page-subtitle">Una lectura comparativa de notas, preparación y carga de trabajo para decidir dónde poner tu atención.</p></div>
      <div className="uc-date-chip"><BookOpen size={16} />{subjects.length} asignatura{subjects.length === 1 ? "" : "s"} activa{subjects.length === 1 ? "" : "s"}</div>
    </header>
    <section className="uc-subjects-summary" aria-label="Resumen de asignaturas">
      <div><span>Tiempo registrado</span><strong>{totalMinutes} min</strong><small>en todas las asignaturas</small></div>
      <div><span>XP académico</span><strong>{totalXp} XP</strong><small>progreso acumulado</small></div>
      <div><span>Próximas evaluaciones</span><strong>{subjects.filter((subject) => subject.next_assessment).length}</strong><small>con fecha disponible</small></div>
    </section>
    <section className="uc-subject-ledger">
      <div className="uc-subject-ledger-head"><div><p className="uc-eyebrow">Registro académico</p><h2>Estado por asignatura</h2></div><span>Selecciona una fila para ver el detalle</span></div>
      <div className="uc-subject-ledger-columns"><span>Asignatura y estado</span><span>Nota / objetivo</span><span>Preparación</span><span>Próxima evaluación</span><span>Actividad</span><span /></div>
      {subjects.map((subject) => {
        const state = subjectState(subject); const readiness = readinessBySubject[subject.id];
        return <button className="uc-subject-ledger-row" key={subject.id} onClick={() => onSelect(subject.id)}>
          <span className="uc-subject-name"><strong>{subject.name}</strong><small className={`uc-subject-status ${state.tone}`}>{state.label}</small></span>
          <span className="uc-subject-grade"><strong>{subject.grade.current_grade_out_of_10 != null ? subject.grade.current_grade_out_of_10.toFixed(1) : "—"}</strong><small>{subject.grade.target_grade != null ? `objetivo ${subject.grade.target_grade.toFixed(1)}` : "sin objetivo"}</small></span>
          <span className="uc-subject-readiness">{readiness != null ? <><span className="uc-progress-track table-track"><span className="uc-progress-fill" style={{ width: `${readiness}%` }} /></span><small>{readiness.toFixed(0)}% disponible</small></> : <small>Sin Boss Battle</small>}</span>
          <span className="uc-subject-exam"><CalendarDays size={15} /><span><strong>{subject.next_assessment?.title ?? "Sin evaluación próxima"}</strong><small>{formatDate(subject.next_assessment?.date)}</small></span></span>
          <span className="uc-subject-activity"><span><Clock3 size={14} /> {subject.study_minutes} min</span><span><Target size={14} /> {subject.quiz_average_percentage != null ? `${subject.quiz_average_percentage.toFixed(0)}% quiz` : "sin quiz"}</span><span><Trophy size={14} /> {subject.xp} XP</span></span>
          <ChevronRight size={18} className="uc-subject-chevron" />
        </button>;
      })}
    </section>
    <p className="uc-subjects-note">La preparación se muestra cuando existe una Boss Battle activa. Los detalles de materiales, evaluaciones completas y Knowledge Map se integrarán cuando estén disponibles por HTTP.</p>
  </div>;
}
