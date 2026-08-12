import { CalendarDays, CheckCircle2, Clock3, RefreshCw, SlidersHorizontal, Target } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDecisionPlan, getTasks, type DecisionPlan, type TasksData } from "../api";

const durations = [15, 30, 45, 60, 90];
type Scope = "active" | "overdue" | "today" | "upcoming" | "undated";

function dueLabel(days: number | null) {
  if (days == null) return "Sin fecha";
  if (days < 0) return `Vencida hace ${Math.abs(days)} día${Math.abs(days) === 1 ? "" : "s"}`;
  if (days === 0) return "Hoy";
  if (days === 1) return "Mañana";
  return `En ${days} días`;
}

function priorityLabel(value: number) {
  if (value >= 5) return "Crítica";
  if (value >= 4) return "Alta";
  if (value >= 3) return "Media";
  return "Baja";
}

export default function TasksPage() {
  const [data, setData] = useState<TasksData | null>(null);
  const [plan, setPlan] = useState<DecisionPlan | null>(null);
  const [duration, setDuration] = useState(() => Number(window.localStorage.getItem("unicore-plan-duration")) || 60);
  const [scope, setScope] = useState<Scope>("active");
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadTasks() {
    setLoading(true); setError(null);
    try { const [tasks, nextPlan] = await Promise.all([getTasks(), getDecisionPlan(duration, 5)]); setData(tasks); setPlan(nextPlan); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron cargar las tareas."); }
    finally { setLoading(false); }
  }

  async function changeDuration(minutes: number) {
    setDuration(minutes); setPlanning(true); setError(null);
    try { setPlan(await getDecisionPlan(minutes, 5)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo calcular el plan."); }
    finally { setPlanning(false); }
  }

  useEffect(() => { void loadTasks(); }, []);
  const tasks = useMemo(() => (data?.tasks ?? []).filter(({ task }) => {
    if (scope === "overdue") return task.is_overdue;
    if (scope === "today") return task.days_until_due === 0;
    if (scope === "upcoming") return task.days_until_due != null && task.days_until_due > 0;
    if (scope === "undated") return task.due_date == null;
    return true;
  }), [data, scope]);
  const counts = useMemo(() => ({
    overdue: data?.tasks.filter(({ task }) => task.is_overdue).length ?? 0,
    today: data?.tasks.filter(({ task }) => task.days_until_due === 0).length ?? 0,
    inProgress: data?.tasks.filter(({ task }) => task.status === "in_progress").length ?? 0,
  }), [data]);

  if (loading) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Tareas</p><h1>Ordenando tu carga académica…</h1><p>UniCore está leyendo fechas, progreso y prioridad.</p></section>;
  if (error && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Tareas</p><h1>No se pudo conectar con UniCore.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void loadTasks()}>Reintentar <RefreshCw size={16} /></button></section>;

  return <div className="uc-page-shell uc-tasks-page">
    <header className="uc-page-intro"><div><p className="uc-eyebrow">Ejecución académica</p><h1>Tareas con contexto.</h1><p className="uc-page-subtitle">Fechas, avance y prioridad real para separar lo urgente de lo que simplemente hace ruido.</p></div><div className="uc-date-chip"><CheckCircle2 size={16} />{data?.count ?? 0} tarea{data?.count === 1 ? "" : "s"} activa{data?.count === 1 ? "" : "s"}</div></header>
    <section className="uc-task-summary"><div><span>Vencidas</span><strong className={counts.overdue ? "is-danger" : ""}>{counts.overdue}</strong><small>requieren revisión</small></div><div><span>Para hoy</span><strong>{counts.today}</strong><small>con fecha actual</small></div><div><span>En progreso</span><strong>{counts.inProgress}</strong><small>trabajo iniciado</small></div></section>
    <section className="uc-planner-block"><div className="uc-planner-copy"><p className="uc-eyebrow">Decision Engine</p><h2>Planifica tu tiempo</h2><p>Elige cuánto tiempo tienes. UniCore recalcula qué acciones caben y por qué merecen atención.</p></div><div className="uc-duration-control" aria-label="Duración disponible">{durations.map((minutes) => <button key={minutes} className={duration === minutes ? "is-active" : ""} onClick={() => void changeDuration(minutes)}>{minutes}<span>min</span></button>)}</div><div className="uc-planner-result">{planning ? <div className="uc-empty-inline">Calculando un plan real…</div> : plan?.actions.length ? plan.actions.map((action, index) => <article key={`${action.type}-${action.source_id}`}><span className="uc-action-index">{String(index + 1).padStart(2, "0")}</span><div><strong>{action.title}</strong><p>{action.reasons.join(" ")}</p><small>{action.subject_name ?? "UniCore"} · {action.allocated_minutes} min · prioridad {action.priority}</small></div><div className="uc-plan-score"><Target size={15} />{action.score.toFixed(0)}</div></article>) : <div className="uc-empty-inline">No hay acciones prioritarias para este bloque.</div>}</div></section>
    <section className="uc-task-register"><div className="uc-task-register-head"><div><p className="uc-eyebrow">Registro activo</p><h2>Trabajo pendiente</h2></div><div className="uc-task-filters"><SlidersHorizontal size={14} />{([['active','Todas'],['overdue','Vencidas'],['today','Hoy'],['upcoming','Próximas'],['undated','Sin fecha']] as const).map(([value, label]) => <button key={value} className={scope === value ? "is-active" : ""} onClick={() => setScope(value)}>{label}</button>)}</div></div>
      {tasks.length === 0 ? <div className="uc-task-empty"><strong>No hay tareas en esta vista.</strong><span>{data?.count ? "Prueba otro filtro para revisar tu trabajo activo." : "Cuando existan tareas activas aparecerán aquí."}</span></div> : <div className="uc-task-list">{tasks.map(({ task, planning: taskPlanning }) => <article className={`uc-task-row ${task.is_overdue ? "is-overdue" : ""}`} key={task.id}><div className="uc-task-priority"><span>{priorityLabel(task.priority)}</span><strong>{taskPlanning.planning_score.toFixed(0)}</strong></div><div className="uc-task-main"><div><strong>{task.title}</strong><span>{task.subject_name ?? "Sin asignatura"} · {task.task_type}</span></div>{task.description && <p>{task.description}</p>}<div className="uc-task-progress"><div className="uc-progress-track"><div className="uc-progress-fill" style={{ width: `${task.progress_percentage}%` }} /></div><span>{task.progress_percentage}%</span></div></div><div className="uc-task-meta"><span className={task.is_overdue ? "is-danger" : ""}><CalendarDays size={14} />{dueLabel(task.days_until_due)}</span><span><Clock3 size={14} />{task.remaining_minutes != null ? `${task.remaining_minutes} min restantes` : "Sin estimación"}</span><small>{task.status === "in_progress" ? "En progreso" : "Pendiente"}</small></div></article>)}</div>}
      <p className="uc-data-limit">Esta primera versión muestra tareas activas. Las completadas y las operaciones de edición permanecen limitadas porque no hay una función HTTP reutilizable segura para ellas.</p>
    </section>
  </div>;
}
