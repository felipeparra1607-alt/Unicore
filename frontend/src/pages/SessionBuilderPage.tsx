import { ArrowLeft, ArrowRight, Minus, Play, Plus, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getCurriculum, getDashboard, getDecisionPlan, getTasks, type DecisionAction, type DashboardData, type TasksData } from "../api";
import { allocatedMinutes, changeActionMinutes, composePlan } from "../utils/planner";

type BuilderMode = "landing" | "manual" | "recommended";
const durations = [15, 30, 45, 60, 90];
const priority = (value: number): DecisionAction["priority"] => value >= 5 ? "critical" : value >= 4 ? "high" : value >= 3 ? "medium" : "low";

export default function SessionBuilderPage({ initialMode = "landing", onBack, onStart }: { initialMode?: BuilderMode; onBack: () => void; onStart: (actions: DecisionAction[], duration: number) => void }) {
  const [mode, setMode] = useState<BuilderMode>(initialMode);
  const [duration, setDuration] = useState(60);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tasks, setTasks] = useState<TasksData | null>(null);
  const [actions, setActions] = useState<DecisionAction[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [manualCandidates, setManualCandidates] = useState<DecisionAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDashboard(), getTasks()]).then(([subjects, taskData]) => { setDashboard(subjects); setTasks(taskData); }).catch((caught) => setError(caught instanceof Error ? caught.message : "No se pudo preparar la sesión."));
  }, []);

  useEffect(() => {
    if (mode !== "manual" || !dashboard || !tasks) return;
    Promise.allSettled(dashboard.subjects.map((subject) => getCurriculum(subject.id))).then((results) => {
      const taskActions: DecisionAction[] = tasks.tasks.map(({ task, planning }) => ({ type: "task", source_id: task.id, subject_id: task.subject_id, subject_name: task.subject_name, title: task.title, score: planning.planning_score, priority: priority(task.priority), suggested_minutes: task.remaining_minutes ?? task.estimated_minutes ?? 30, allocated_minutes: 15, reasons: planning.reasons ?? ["Tarea activa"], action: "work_on_task", metadata: { due_date: task.due_date, progress_percentage: task.progress_percentage } }));
      const unitActions: DecisionAction[] = results.flatMap((result, index) => result.status === "fulfilled" ? result.value.units.map((unit) => ({ type: "review" as const, source_id: unit.id, subject_id: result.value.subject.id, subject_name: result.value.subject.name, title: `Repasar ${unit.name}`, score: 0, priority: "medium" as const, suggested_minutes: 30, allocated_minutes: 15, reasons: ["Repaso de unidad"], action: "review_unit", metadata: { unit_id: unit.id, unit_name: unit.name, focus_topic_ids: unit.topics.map((topic) => topic.id), document_ids: [...new Set(unit.topics.flatMap((topic) => topic.sources.map((source) => source.document_id)))] } })) : []);
      setManualCandidates([...taskActions, ...unitActions]);
    });
  }, [mode, dashboard, tasks]);

  async function recommend(minutes = duration) {
    setLoading(true); setError(null);
    try {
      const plan = await getDecisionPlan(minutes, 5);
      const ids = [...new Set(plan.actions.flatMap((action) => action.subject_id == null ? [] : [action.subject_id]))];
      const curricula = (await Promise.allSettled(ids.map(getCurriculum))).flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
      setActions(composePlan(plan.actions, "priority", curricula));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo calcular la recomendación."); }
    finally { setLoading(false); }
  }

  useEffect(() => { if (mode === "recommended") void recommend(); }, [mode]);
  const selected = useMemo(() => mode === "manual" ? manualCandidates.filter((item) => selectedKeys.has(`${item.type}:${item.source_id}`)) : actions, [mode, manualCandidates, selectedKeys, actions]);
  function updateMinutes(index: number, delta: number) {
    const result = changeActionMinutes(selected, index, delta, duration);
    if (result.error) { setError(result.error); return; }
    if (mode === "recommended") setActions(result.actions);
    else setManualCandidates((current) => current.map((candidate) => result.actions.find((item) => item.type === candidate.type && item.source_id === candidate.source_id) ?? candidate));
  }
  function toggleManual(key: string) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else {
        if ((next.size + 1) * 15 > duration) { setError(`En ${duration} minutos caben como máximo ${Math.floor(duration / 15)} actividades.`); return current; }
        next.add(key);
      }
      setError(null);
      const keys = [...next];
      const base = keys.length ? Math.floor(duration / keys.length / 15) * 15 : 15;
      setManualCandidates((candidates) => candidates.map((candidate) => keys.includes(`${candidate.type}:${candidate.source_id}`) ? { ...candidate, allocated_minutes: Math.max(15, base) } : candidate));
      return next;
    });
  }

  if (mode === "landing") return <div className="uc-page-shell uc-session-builder"><button className="uc-back-link" onClick={onBack}><ArrowLeft size={15} /> Volver a Tareas</button><header><p className="uc-eyebrow">Session Builder</p><h1>¿Cómo quieres construir esta sesión?</h1><p>Elige manualmente el trabajo o deja que UniCore ordene las prioridades reales.</p></header><div className="uc-builder-choices"><button onClick={() => setMode("manual")}><span>01</span><strong>Crear manualmente</strong><p>Combina tareas activas y repasos por unidad.</p><ArrowRight size={18} /></button><button onClick={() => setMode("recommended")}><span>02</span><strong>Usar recomendación</strong><p>Parte del Decision Engine y ajusta el resultado.</p><Sparkles size={18} /></button></div></div>;

  return <div className="uc-page-shell uc-session-builder"><button className="uc-back-link" onClick={() => setMode("landing")}><ArrowLeft size={15} /> Cambiar método</button><header><p className="uc-eyebrow">{mode === "manual" ? "Selección manual" : "Recomendación académica"}</p><h1>Construye el bloque.</h1><p>{mode === "manual" ? "Selecciona tareas y unidades completas; los temas quedan dentro de su unidad." : "Ajusta la duración y el reparto antes de entrar en modo foco."}</p></header><div className="uc-duration-control">{durations.map((minutes) => <button key={minutes} className={duration === minutes ? "is-active" : ""} onClick={() => { setDuration(minutes); if (mode === "recommended") void recommend(minutes); }}>{minutes}<span>min</span></button>)}</div>{error && <div className="uc-inline-error">{error}</div>}
    {mode === "manual" && <section className="uc-builder-catalog"><h2>Trabajo disponible</h2>{manualCandidates.map((action) => { const key = `${action.type}:${action.source_id}`; return <label key={key}><input type="checkbox" checked={selectedKeys.has(key)} onChange={() => toggleManual(key)} /><span><strong>{action.title}</strong><small>{action.type === "task" ? "Tarea" : "Repaso de unidad"} · {action.subject_name ?? "Sin asignatura"}</small></span></label>; })}</section>}
    <section className="uc-builder-plan"><header><h2>Plan de la sesión</h2><span>{allocatedMinutes(selected)} / {duration} min</span></header>{loading ? <p>Calculando una recomendación…</p> : selected.length === 0 ? <p className="uc-empty-inline">Selecciona al menos una actividad.</p> : selected.map((action, index) => <article key={`${action.type}-${action.source_id}`}><div><strong>{action.title}</strong><small>{action.subject_name ?? "UniCore"} · {action.type === "task" ? "Tarea" : "Unidad"}</small></div><div className="uc-plan-minutes"><button onClick={() => updateMinutes(index, -15)}><Minus size={13} /></button><strong>{action.allocated_minutes}</strong><span>min</span><button onClick={() => updateMinutes(index, 15)}><Plus size={13} /></button></div></article>)}<footer><span>{Math.max(0, duration - allocatedMinutes(selected))} min disponibles</span><button className="uc-primary-action" disabled={!selected.length || allocatedMinutes(selected) > duration} onClick={() => onStart(selected, duration)}><Play size={15} /> Iniciar sesión</button></footer></section>
  </div>;
}
