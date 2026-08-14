import { ArrowLeft, BookOpen, Brain, Check, Clock3, FileText, Gauge, RefreshCw, RotateCcw } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createStudySession,
  getDashboard,
  getKnowledge,
  getStudy,
  getSubjectDocuments,
  rateFlashcard,
  sendAgentMessage,
  startExplanation,
  startFlashcards,
  type AgentSource,
  type DashboardData,
  type Flashcard,
  type KnowledgeConcept,
  type StudyData,
  type SubjectDocumentsData,
} from "../api";

type StudyLaunchContext = { subjectId: number; subjectName: string; documentId?: number; topic?: string } | null;
type TutorMessage = { role: "user" | "assistant"; text: string; sources?: AgentSource[] };
type SessionSummary = { mode: "explanation" | "flashcards"; minutes: number; cards: number; difficult: number; successful: number };

const modeNames = { explanation: "Explicación", flashcards: "Flashcards" } as const;
const activityNames: Record<string, string> = { explanation: "Explicación", flashcards: "Flashcards", quick_review: "Repaso rápido", quiz: "Quiz", summary: "Resumen", reading: "Lectura", practice: "Práctica" };
function shortDate(value: string) { return new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", { day: "2-digit", month: "short" }); }
function rating(value: number | null) { return value == null ? "—" : `${value}/5`; }
function studyQuery(value: string, subjectName: string, studyMode: keyof typeof modeNames) {
  const clean = value.trim();
  const generalValues = new Set(["", "toda la asignatura", "asignatura completa", "todo el contenido"]);
  if (!generalValues.has(clean.toLocaleLowerCase("es-ES"))) return clean;
  return `${studyMode === "explanation" ? "Explicación" : "Repaso"} general de ${subjectName}`;
}

export default function StudyPage({ launchContext }: { launchContext?: StudyLaunchContext }) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [data, setData] = useState<StudyData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(launchContext?.subjectId ?? null);
  const [documents, setDocuments] = useState<SubjectDocumentsData["documents"]>([]);
  const [concepts, setConcepts] = useState<KnowledgeConcept[]>([]);
  const [documentId, setDocumentId] = useState<number | null>(launchContext?.documentId ?? null);
  const [topic, setTopic] = useState(launchContext?.topic ?? "");
  const [sessionTopic, setSessionTopic] = useState("");
  const [mode, setMode] = useState<keyof typeof modeNames>("explanation");
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<keyof typeof modeNames | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [clock, setClock] = useState(Date.now());
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [answering, setAnswering] = useState(false);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [cardIndex, setCardIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [ratingCounts, setRatingCounts] = useState({ difficult: 0, successful: 0 });
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  async function loadSubject(id: number) {
    setSubjectId(id); setLoading(true); setError(null); setDocumentId(null);
    try {
      const [study, materialData, knowledge] = await Promise.all([getStudy(id), getSubjectDocuments(id), getKnowledge(id)]);
      setData(study); setDocuments(materialData.documents); setConcepts(knowledge.concepts);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); }
    finally { setLoading(false); }
  }

  async function load() {
    setLoading(true); setError(null);
    try {
      const nextDashboard = await getDashboard();
      setDashboard(nextDashboard);
      const selected = nextDashboard.subjects.find((item) => item.id === (launchContext?.subjectId ?? subjectId)) ?? nextDashboard.subjects[0];
      if (selected) {
        const [study, materialData, knowledge] = await Promise.all([getStudy(selected.id), getSubjectDocuments(selected.id), getKnowledge(selected.id)]);
        setSubjectId(selected.id); setData(study); setDocuments(materialData.documents); setConcepts(knowledge.concepts);
        if (launchContext?.documentId) setDocumentId(launchContext.documentId);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [launchContext?.subjectId, launchContext?.documentId]);
  useEffect(() => { if (activeMode == null) return; const timer = window.setInterval(() => setClock(Date.now()), 15_000); return () => window.clearInterval(timer); }, [activeMode]);

  async function beginSession() {
    if (subjectId == null || starting) return;
    const requestedTopic = studyQuery(topic, data?.subject.name ?? "la asignatura", mode);
    setStarting(true); setError(null); setSummary(null);
    try {
      if (mode === "explanation") {
        const result = await startExplanation({ subject_id: subjectId, topic: requestedTopic, document_id: documentId });
        setConversationId(result.conversation_id);
        setMessages([{ role: "assistant", text: result.explanation, sources: result.sources }]);
      } else {
        const result = await startFlashcards({ subject_id: subjectId, topic: requestedTopic, document_id: documentId, item_count: 8 });
        setCards(result.cards); setCardIndex(0); setRevealed(false); setRatingCounts({ difficult: 0, successful: 0 });
      }
      setSessionTopic(requestedTopic);
      setStartedAt(Date.now()); setClock(Date.now()); setActiveMode(mode);
    } catch (caught) { setError(caught instanceof Error ? caught.message : `No se pudo iniciar ${modeNames[mode].toLowerCase()}.`); }
    finally { setStarting(false); }
  }

  async function askTutor(event: FormEvent) {
    event.preventDefault();
    const clean = question.trim();
    if (!clean || !conversationId || subjectId == null || answering) return;
    setMessages((current) => [...current, { role: "user", text: clean }]); setQuestion(""); setAnswering(true); setError(null);
    try {
      const result = await sendAgentMessage(clean, {
        conversationId, subjectId, documentId,
        contextType: documentId != null ? "document" : "subject",
        workContext: { action: "Tutoría explicativa progresiva", subject: data?.subject.name, duration_minutes: duration },
      });
      if (result.answer) setMessages((current) => [...current, { role: "assistant", text: result.answer!, sources: result.sources }]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo continuar la explicación."); }
    finally { setAnswering(false); }
  }

  async function finishSession(modeToSave: keyof typeof modeNames, stats = ratingCounts) {
    if (subjectId == null || startedAt == null) return;
    const minutes = Math.max(1, Math.round((Date.now() - startedAt) / 60_000));
    try {
      await createStudySession({
        subject_id: subjectId, duration_minutes: minutes, activity_type: modeToSave,
        topic: sessionTopic, planned_minutes: duration, completed_plan: minutes >= duration,
        started_at: new Date(startedAt).toISOString(), completed_at: new Date().toISOString(),
      });
      setSummary({ mode: modeToSave, minutes, cards: modeToSave === "flashcards" ? stats.difficult + stats.successful : 0, difficult: stats.difficult, successful: stats.successful });
      setActiveMode(null); setStartedAt(null);
      const refreshed = await getStudy(subjectId); setData(refreshed);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo registrar la sesión."); }
  }

  async function submitCardRating(nextRating: "difficult" | "good" | "easy") {
    const card = cards[cardIndex]; if (!card || !revealed || starting) return;
    setStarting(true); setError(null);
    try {
      await rateFlashcard(card.id, nextRating);
      const nextCounts = {
        difficult: ratingCounts.difficult + (nextRating === "difficult" ? 1 : 0),
        successful: ratingCounts.successful + (nextRating === "difficult" ? 0 : 1),
      };
      setRatingCounts(nextCounts);
      if (cardIndex === cards.length - 1) await finishSession("flashcards", nextCounts);
      else { setCardIndex((value) => value + 1); setRevealed(false); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo guardar la valoración."); }
    finally { setStarting(false); }
  }

  const elapsedMinutes = startedAt == null ? 0 : Math.max(1, Math.ceil((clock - startedAt) / 60_000));
  const activeSources = useMemo(() => messages.flatMap((item) => item.sources ?? []).filter((source, index, all) => all.findIndex((candidate) => candidate.document_id === source.document_id && candidate.source_number === source.source_number) === index), [messages]);
  const sessions = data?.recent_study_sessions ?? [];
  const attempts = data?.recent_attempts ?? [];
  const reviews = data?.reviews;
  const masteredReviews = reviews?.reviews.filter((review) => review.status === "mastered").length ?? 0;
  const currentCard = cards[cardIndex];

  if (loading && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Preparando tu centro de entrenamiento…</h1><p>Recuperando sesiones, materiales y conceptos reales.</p></section>;
  if (error && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>No se pudo cargar el centro de estudio.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;
  if (!dashboard?.subjects.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Aún no hay asignaturas para estudiar.</h1><p>Crea tu primera asignatura y añade material para iniciar una explicación o generar flashcards.</p></section>;

  if (activeMode === "explanation") return <div className="uc-page-shell uc-live-study"><header><button className="uc-back-link" onClick={() => void finishSession("explanation")}><ArrowLeft size={15} /> Finalizar sesión</button><div><p className="uc-eyebrow">Explicación · {elapsedMinutes} min</p><h1>{sessionTopic}</h1><p>{data?.subject.name}{documentId ? ` · ${documents.find((item) => item.id === documentId)?.title ?? "Material seleccionado"}` : ""}</p></div></header><div className="uc-tutor-layout"><section className="uc-tutor-thread">{messages.map((message, index) => <article key={index} className={`is-${message.role}`}><span>{message.role === "assistant" ? "UniCore Tutor" : "Tú"}</span><p>{message.text}</p></article>)}{answering && <article className="is-assistant is-loading"><span>UniCore Tutor</span><p>Preparando el siguiente paso…</p></article>}<form onSubmit={askTutor}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={2} placeholder="Pregunta una duda, pide una versión más sencilla o solicita un ejemplo…" /><button disabled={answering || !question.trim()}>Preguntar</button></form><div className="uc-tutor-suggestions">{["No entiendo esto", "Explícamelo más sencillo", "Ponme un ejemplo"].map((text) => <button key={text} onClick={() => setQuestion(text)}>{text}</button>)}</div></section><aside className="uc-study-sources"><p className="uc-eyebrow">Material utilizado</p>{activeSources.length ? activeSources.map((source) => <div key={`${source.document_id}-${source.source_number}`}><FileText size={14} /><span><strong>{source.document_title}</strong>{source.source_label && <small>{source.source_label}</small>}</span></div>) : <p>La explicación continuará con la memoria de esta sesión. No hay fuentes adicionales visibles.</p>}<small>RAG limitado a 4 fragmentos por consulta.</small></aside></div>{error && <div className="uc-inline-error">{error}</div>}</div>;

  if (activeMode === "flashcards" && currentCard) return <div className="uc-page-shell uc-live-study uc-flashcard-session"><header><button className="uc-back-link" onClick={() => void finishSession("flashcards")}><ArrowLeft size={15} /> Finalizar sesión</button><div><p className="uc-eyebrow">Flashcards · {elapsedMinutes} min</p><h1>{sessionTopic}</h1><p>{cardIndex + 1} / {cards.length}</p></div></header><div className="uc-flashcard-progress"><span style={{ width: `${((cardIndex + (revealed ? 1 : 0)) / cards.length) * 100}%` }} /></div><article className="uc-flashcard"><span>Pregunta</span><h2>{currentCard.question}</h2>{revealed ? <div><span>Respuesta</span><p>{currentCard.correct_answer}</p></div> : <button onClick={() => setRevealed(true)}>Mostrar respuesta</button>}</article>{revealed && <div className="uc-flashcard-ratings"><button disabled={starting} onClick={() => void submitCardRating("difficult")}>Difícil</button><button disabled={starting} onClick={() => void submitCardRating("good")}>Bien</button><button disabled={starting} onClick={() => void submitCardRating("easy")}>Fácil</button></div>}<p className="uc-flashcard-note">Tu valoración actualiza el intervalo de repaso existente.</p>{error && <div className="uc-inline-error">{error}</div>}</div>;

  if (summary) return <div className="uc-page-shell uc-study-complete"><Check size={24} /><p className="uc-eyebrow">Sesión registrada</p><h1>{modeNames[summary.mode]} completada.</h1><div><span>Tiempo real <strong>{summary.minutes} min</strong></span>{summary.mode === "flashcards" && <><span>Tarjetas <strong>{summary.cards}</strong></span><span>Difíciles <strong>{summary.difficult}</strong></span><span>Bien / fácil <strong>{summary.successful}</strong></span></>}</div><button className="uc-primary-action" onClick={() => setSummary(null)}>Volver al centro de estudio</button></div>;

  return <div className="uc-page-shell uc-study-page"><header className="uc-page-intro"><div><p className="uc-eyebrow">Centro de entrenamiento</p><h1>Estudia con intención.</h1><p className="uc-page-subtitle">Explicaciones progresivas y flashcards fundamentadas en tu propio material.</p></div><label className="uc-subject-select"><span>Asignatura</span><select value={subjectId ?? ""} onChange={(event) => void loadSubject(Number(event.target.value))}>{dashboard.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label></header>
    <section className="uc-study-launch"><div className="uc-study-launch-copy"><p className="uc-eyebrow">Estudiar ahora</p><h2>Configura el próximo bloque</h2><p>Elige solo el contexto que necesitas. UniCore recuperará un máximo de cuatro fragmentos relevantes.</p></div><div className="uc-study-config"><label><span>Tema o pregunta</span><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Tema concreto o déjalo vacío para una visión general" /></label><div><label><span>Material opcional</span><select value={documentId ?? ""} onChange={(event) => setDocumentId(event.target.value ? Number(event.target.value) : null)}><option value="">Toda la asignatura</option>{documents.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label><span>Concepto opcional</span><select value="" onChange={(event) => event.target.value && setTopic(event.target.value)}><option value="">{concepts.length ? "Seleccionar concepto" : "Sin conceptos registrados"}</option>{concepts.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select></label></div></div><div className="uc-study-start"><div className="uc-study-modes" role="group" aria-label="Modo de estudio">{Object.entries(modeNames).map(([key, label]) => <button key={key} className={mode === key ? "is-active" : ""} onClick={() => setMode(key as keyof typeof modeNames)}>{label}</button>)}</div><label><span>Objetivo de tiempo</span><select value={duration} onChange={(event) => setDuration(Number(event.target.value))}>{[15, 30, 45, 60, 90].map((value) => <option key={value} value={value}>{value} minutos</option>)}</select></label><button className="uc-primary-action" disabled={starting} onClick={() => void beginSession()}>{starting ? "Preparando…" : `Iniciar ${modeNames[mode].toLowerCase()}`}</button></div></section>{error && <div className="uc-inline-error uc-study-error">{error}</div>}
    <section className="uc-study-metrics"><div><Clock3 size={16} /><span>Tiempo total</span><strong>{data?.summary.total_study_minutes ?? 0} min</strong></div><div><BookOpen size={16} /><span>Sesiones</span><strong>{data?.summary.study_session_count ?? 0}</strong></div><div><Brain size={16} /><span>Quiz medio</span><strong>{data?.summary.quiz_average_percentage != null ? `${data.summary.quiz_average_percentage.toFixed(0)}%` : "—"}</strong></div><div><RotateCcw size={16} /><span>Repasos pendientes</span><strong>{reviews?.due_count ?? 0}</strong></div></section>
    <section className="uc-study-history"><div className="uc-section-heading"><div><p className="uc-eyebrow">Actividad real</p><h2>Sesiones recientes</h2></div><span>{sessions.length} visibles</span></div>{sessions.length ? <div className="uc-study-session-list">{sessions.map((session) => <article key={session.id}><time>{shortDate(session.session_date)}</time><div><strong>{session.topic ?? activityNames[session.activity_type] ?? session.activity_type}</strong><span>{activityNames[session.activity_type] ?? session.activity_type} · {session.duration_minutes} min</span></div><div className="uc-session-ratings"><span>Foco <strong>{rating(session.focus_rating)}</strong></span><span>Dificultad <strong>{rating(session.difficulty_rating)}</strong></span><span>Satisfacción <strong>{rating(session.satisfaction_rating)}</strong></span></div></article>)}</div> : <div className="uc-task-empty"><strong>No hay sesiones registradas.</strong><span>Cuando completes una sesión aparecerá aquí.</span></div>}</section>
    <section className="uc-practice-memory"><header><p className="uc-eyebrow">Práctica y memoria</p><h2>Comprueba y consolida lo aprendido</h2></header><div className="uc-practice-layout"><article className="uc-quiz-practice"><div className="uc-practice-summary"><span>Quizzes</span><strong>{data?.summary.quiz_attempt_count ?? 0}</strong><small>{data?.summary.quiz_average_percentage != null ? `${data.summary.quiz_average_percentage.toFixed(0)}% de media` : "Sin media disponible"}</small></div><div>{attempts.length ? attempts.slice(0, 6).map((attempt) => <div className="uc-practice-row" key={attempt.id}><span><strong>{attempt.topic}</strong><small>{activityNames[attempt.study_mode] ?? attempt.study_mode}</small></span><strong>{attempt.score_percentage != null ? `${attempt.score_percentage.toFixed(0)}%` : "Pendiente"}</strong></div>) : <div className="uc-empty-inline">Sin intentos de quiz.</div>}</div></article><article className="uc-review-memory"><div className="uc-practice-summary"><span>Repasos</span><strong>{reviews?.due_count ?? 0}</strong><small>{masteredReviews} dominados</small></div><div>{reviews?.reviews.length ? reviews.reviews.slice(0, 6).map((review) => <div className="uc-practice-row" key={review.id}><Gauge size={14} /><span><strong>{review.topic}</strong><small>{review.status} · prioridad {review.priority}</small></span></div>) : <div className="uc-empty-inline">No hay repasos programados.</div>}</div></article></div></section>
  </div>;
}
