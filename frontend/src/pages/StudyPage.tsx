import { BookOpen, Brain, Clock3, Gauge, RefreshCw, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { getDashboard, getStudy, type DashboardData, type StudyData } from "../api";

const modeNames: Record<string, string> = { explanation: "Explicación", flashcards: "Flashcards", quick_review: "Repaso rápido", quiz: "Quiz", summary: "Resumen" };
const activityNames: Record<string, string> = { explanation: "Explicación", flashcards: "Flashcards", quick_review: "Repaso rápido", quiz: "Quiz", summary: "Resumen", reading: "Lectura", practice: "Práctica" };

function shortDate(value: string) { return new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", { day: "2-digit", month: "short" }); }
function rating(value: number | null) { return value == null ? "—" : `${value}/5`; }

export default function StudyPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [data, setData] = useState<StudyData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [mode, setMode] = useState("explanation");
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadSubject(id: number) {
    setSubjectId(id); setLoading(true); setError(null);
    try { setData(await getStudy(id)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); }
    finally { setLoading(false); }
  }

  async function load() {
    setLoading(true); setError(null);
    try { const nextDashboard = await getDashboard(); setDashboard(nextDashboard); const first = nextDashboard.subjects[0]; if (first) { setSubjectId(first.id); setData(await getStudy(first.id)); } }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  if (loading && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Preparando tu centro de entrenamiento…</h1><p>Recuperando sesiones, quizzes y repasos reales.</p></section>;
  if (error && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>No se pudo conectar con UniCore.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;
  if (!dashboard?.subjects.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Aún no hay asignaturas para estudiar.</h1><p>El centro de estudio se activará cuando exista una asignatura registrada.</p></section>;

  const sessions = data?.recent_study_sessions ?? []; const attempts = data?.recent_attempts ?? []; const reviews = data?.reviews;
  return <div className="uc-page-shell uc-study-page">
    <header className="uc-page-intro"><div><p className="uc-eyebrow">Centro de entrenamiento</p><h1>Estudia con intención.</h1><p className="uc-page-subtitle">Sesiones, calidad de foco y práctica recuperada directamente de tu actividad académica.</p></div><label className="uc-subject-select"><span>Asignatura</span><select value={subjectId ?? ""} onChange={(event) => void loadSubject(Number(event.target.value))}>{dashboard.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label></header>
    <section className="uc-study-launch"><div className="uc-study-launch-copy"><Sparkles size={18} /><p className="uc-eyebrow">Quiero estudiar ahora</p><h2>Configura el próximo bloque</h2><p>Los modos son capacidades reales del motor de estudio. El inicio desde web se habilitará cuando exista una función pública reutilizable fuera del registro MCP.</p></div><div className="uc-study-modes" role="group" aria-label="Modo de estudio">{(data?.available_study_modes ?? []).map((item) => <button key={item} className={mode === item ? "is-active" : ""} onClick={() => setMode(item)}>{modeNames[item] ?? item}</button>)}</div><div className="uc-study-duration"><label htmlFor="study-duration">Duración</label><select id="study-duration" value={duration} onChange={(event) => setDuration(Number(event.target.value))}>{[15,30,45,60,90].map((value) => <option key={value} value={value}>{value} minutos</option>)}</select><button disabled title="Pendiente de una interfaz HTTP segura">Iniciar {modeNames[mode]?.toLowerCase()} · {duration} min</button></div></section>
    <section className="uc-study-metrics"><div><Clock3 size={16} /><span>Tiempo total</span><strong>{data?.summary.total_study_minutes ?? 0} min</strong></div><div><BookOpen size={16} /><span>Sesiones</span><strong>{data?.summary.study_session_count ?? 0}</strong></div><div><Brain size={16} /><span>Quiz medio</span><strong>{data?.summary.quiz_average_percentage != null ? `${data.summary.quiz_average_percentage.toFixed(0)}%` : "—"}</strong></div><div><RotateCcw size={16} /><span>Repasos vencidos</span><strong>{reviews?.due_count ?? 0}</strong></div></section>
    <section className="uc-study-grid"><div className="uc-study-history"><div className="uc-section-heading"><div><p className="uc-eyebrow">Historial real</p><h2>Sesiones recientes</h2></div><span>{sessions.length} visibles</span></div>{sessions.length ? <div className="uc-study-session-list">{sessions.map((session) => <article key={session.id}><time>{shortDate(session.session_date)}</time><div><strong>{session.topic ?? activityNames[session.activity_type] ?? session.activity_type}</strong><span>{activityNames[session.activity_type] ?? session.activity_type} · {session.duration_minutes} min</span></div><div className="uc-session-ratings"><span>Foco <strong>{rating(session.focus_rating)}</strong></span><span>Dificultad <strong>{rating(session.difficulty_rating)}</strong></span><span>Satisfacción <strong>{rating(session.satisfaction_rating)}</strong></span></div></article>)}</div> : <div className="uc-task-empty"><strong>No hay sesiones registradas.</strong><span>Cuando completes una sesión aparecerá aquí.</span></div>}</div>
      <aside className="uc-study-side"><section><p className="uc-eyebrow">Quizzes</p><h2>Práctica reciente</h2>{attempts.length ? attempts.slice(0, 6).map((attempt) => <article key={attempt.id}><div><strong>{attempt.topic}</strong><span>{modeNames[attempt.study_mode] ?? attempt.study_mode}</span></div><strong>{attempt.score_percentage != null ? `${attempt.score_percentage.toFixed(0)}%` : "Pendiente"}</strong></article>) : <div className="uc-empty-inline">Sin intentos de quiz.</div>}</section><section><p className="uc-eyebrow">Repaso</p><h2>Cola de consolidación</h2>{reviews?.reviews.length ? reviews.reviews.slice(0, 5).map((review) => <article key={review.id}><Gauge size={14} /><div><strong>{review.topic}</strong><span>{review.status} · prioridad {review.priority}</span></div></article>) : <div className="uc-empty-inline">No hay repasos programados.</div>}</section></aside></section>
  </div>;
}
