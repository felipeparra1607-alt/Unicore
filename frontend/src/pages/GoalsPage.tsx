import { Check, Clock3, RefreshCw, Save, Target, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getDashboard, setGradeGoal, type DashboardData, type DashboardSubject } from "../api";
import { getWeeklyStudyGoal, saveWeeklyStudyGoal } from "../utils/studyGoal";

type GoalSubject = { subject: DashboardSubject; detail: DashboardData };
const clamp = (value: number) => Math.max(0, Math.min(100, value));

export default function GoalsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [subjects, setSubjects] = useState<GoalSubject[]>([]);
  const [weeklyGoal, setWeeklyGoal] = useState<number | null>(getWeeklyStudyGoal);
  const [weeklyInput, setWeeklyInput] = useState(String(getWeeklyStudyGoal() ?? 120));
  const [editingWeekly, setEditingWeekly] = useState(false);
  const [editingGrade, setEditingGrade] = useState<number | null>(null);
  const [gradeInput, setGradeInput] = useState("");
  const [panelOpen, setPanelOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const global = await getDashboard();
      const details = await Promise.all(global.subjects.map(async (subject) => ({ subject, detail: await getDashboard(subject.id) })));
      setDashboard(global); setSubjects(details);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron cargar los objetivos."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  function submitWeekly(event: FormEvent) {
    event.preventDefault(); const value = Number(weeklyInput);
    if (!Number.isFinite(value) || value < 30 || value > 10000) { setError("El objetivo semanal debe estar entre 30 y 10.000 minutos."); return; }
    saveWeeklyStudyGoal(value); setWeeklyGoal(value); setEditingWeekly(false); setError(null); setNotice("Objetivo semanal guardado.");
  }

  async function submitGrade(subjectId: number) {
    const value = Number(gradeInput);
    if (!Number.isFinite(value) || value < 0 || value > 10) { setError("La nota objetivo debe estar entre 0 y 10."); return; }
    setSaving(true); setError(null);
    try { await setGradeGoal(subjectId, value); setEditingGrade(null); setNotice("Objetivo de nota actualizado."); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo guardar el objetivo."); }
    finally { setSaving(false); }
  }

  const averages = useMemo(() => {
    const current = subjects.map(({ subject }) => subject.grade.current_grade_out_of_10).filter((value): value is number => value != null);
    const target = subjects.map(({ subject }) => subject.grade.target_grade).filter((value): value is number => value != null);
    return { current: current.length ? current.reduce((sum, value) => sum + value, 0) / current.length : null, target: target.length ? target.reduce((sum, value) => sum + value, 0) / target.length : null };
  }, [subjects]);
  const readiness = useMemo(() => {
    const values = subjects.map(({ detail }) => detail.next_boss?.readiness_percentage).filter((value): value is number => value != null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  }, [subjects]);

  if (loading) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Objetivos</p><h1>Preparando tu progreso…</h1></section>;
  if (error && !dashboard) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Objetivos</p><h1>No se pudieron cargar tus objetivos.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;

  const studied = dashboard?.metrics.study_minutes_last_7_days ?? 0;
  const weeklyPercent = weeklyGoal ? clamp(studied / weeklyGoal * 100) : 0;
  const remaining = weeklyGoal ? Math.max(0, weeklyGoal - studied) : null;
  const gap = averages.current != null && averages.target != null ? averages.target - averages.current : null;

  return <div className="uc-page-shell uc-goals-page-v2"><header className="uc-page-intro"><div><p className="uc-eyebrow">Dirección académica</p><h1>Objetivos con contexto.</h1><p className="uc-page-subtitle">Rendimiento, preparación y constancia en una lectura continua, no en un formulario.</p></div><button className="uc-primary-action" onClick={() => setPanelOpen(true)}><Target size={15} /> Objetivos por asignatura</button></header>{notice && <div className="uc-inline-success">{notice}</div>}{error && <div className="uc-inline-error">{error}</div>}<section className="uc-goal-performance"><header><p className="uc-eyebrow">Rendimiento</p><span>{subjects.length} asignaturas</span></header><div className="uc-goal-grade-strip"><div><span>Media actual</span><strong>{averages.current?.toFixed(1) ?? "—"}</strong></div><div><span>Objetivo</span><strong>{averages.target?.toFixed(1) ?? "—"}</strong></div><div><span>Diferencia</span><strong className={gap != null && gap > 0 ? "is-gap" : ""}>{gap == null ? "—" : `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}`}</strong></div></div><div className="uc-grade-axis"><span className="is-current" style={{ left: `${clamp((averages.current ?? 0) * 10)}%` }} /><span className="is-target" style={{ left: `${clamp((averages.target ?? 0) * 10)}%` }} /></div><p>La media usa únicamente asignaturas con nota registrada; el objetivo usa GradeGoal real.</p></section><div className="uc-goal-secondary"><section className="uc-goal-readiness"><div><p className="uc-eyebrow">Preparación</p><h2>{readiness != null ? `${readiness.toFixed(0)}%` : "Sin estimación"}</h2><p>{readiness != null ? "Media de preparación de las próximas evaluaciones activas." : "Aparecerá cuando exista una Boss Battle con evidencia suficiente."}</p></div><div className="uc-readiness-line"><span style={{ width: `${readiness ?? 0}%` }} /></div></section><section className="uc-goal-consistency"><div><p className="uc-eyebrow">Constancia</p><h2>{studied} <small>min / 7 días</small></h2><p>{weeklyGoal ? remaining === 0 ? "Objetivo semanal alcanzado." : `Faltan ${remaining} minutos para ${weeklyGoal}.` : "Define un ritmo semanal."}</p></div><div className="uc-progress-track"><div className="uc-progress-fill blue" style={{ width: `${weeklyPercent}%` }} /></div>{editingWeekly ? <form onSubmit={submitWeekly}><input type="number" min="30" max="10000" value={weeklyInput} onChange={(event) => setWeeklyInput(event.target.value)} /><span>min / semana</span><button><Save size={13} /> Guardar</button></form> : <button className="uc-text-action" onClick={() => setEditingWeekly(true)}>{weeklyGoal ? "Editar objetivo semanal" : "Definir objetivo semanal"}</button>}</section></div><p className="uc-goals-note"><Clock3 size={13} /> El objetivo semanal es una preferencia local; notas y preparación proceden de datos académicos persistidos.</p>{panelOpen && <div className="uc-goal-drawer-layer"><button className="uc-overlay" aria-label="Cerrar" onClick={() => setPanelOpen(false)} /><aside className="uc-goal-drawer uc-goal-drawer-v2"><header><div><p className="uc-eyebrow">Objetivos por asignatura</p><h2>Rendimiento necesario</h2></div><button onClick={() => setPanelOpen(false)} aria-label="Cerrar"><X size={18} /></button></header><div className="uc-goal-subject-list">{subjects.map(({ subject, detail }) => { const current = subject.grade.current_grade_out_of_10; const target = subject.grade.target_grade; const evaluated = subject.grade.evaluated_weight_percentage; const required = subject.grade.required_average_on_remaining; return <article key={subject.id}><header><div><strong>{subject.name}</strong><small>{evaluated != null ? `${evaluated.toFixed(0)}% evaluado` : "Sin evaluaciones ponderadas"}</small></div>{editingGrade === subject.id ? <span className="uc-inline-grade-edit"><input autoFocus type="number" min="0" max="10" step="0.1" value={gradeInput} onChange={(event) => setGradeInput(event.target.value)} /><button disabled={saving} onClick={() => void submitGrade(subject.id)}><Check size={13} /></button></span> : <button className="uc-text-action" onClick={() => { setEditingGrade(subject.id); setGradeInput(String(target ?? "")); }}>Editar objetivo</button>}</header><div className="uc-subject-goal-values"><span>Actual <strong>{current?.toFixed(1) ?? "—"}</strong></span><span>Objetivo <strong>{target?.toFixed(1) ?? "—"}</strong></span></div><div className="uc-subject-grade-line"><span className="is-current" style={{ left: `${clamp((current ?? 0) * 10)}%` }} /><span className="is-target" style={{ left: `${clamp((target ?? 0) * 10)}%` }} /></div><footer><span>Necesitas en lo restante</span><strong>{required?.toFixed(1) ?? "—"}</strong>{detail.next_boss?.readiness_percentage != null && <small>Preparación {detail.next_boss.readiness_percentage.toFixed(0)}%</small>}</footer></article>; })}</div></aside></div>}</div>;
}
