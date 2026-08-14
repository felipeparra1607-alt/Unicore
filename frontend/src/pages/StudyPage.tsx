import { ArrowLeft, BookOpen, Brain, Check, ChevronDown, Clock3, FileText, Gauge, Layers3, RefreshCw, RotateCcw, ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createStudySession,
  decideFlashcardDraft,
  evaluateFlashcardAnswer,
  getDashboard,
  getKnowledge,
  getLeitner,
  getStudy,
  getSubjectDocuments,
  moveFlashcard,
  rateFlashcard,
  sendAgentMessage,
  startExplanation,
  startFlashcards,
  type AgentSource,
  type DashboardData,
  type Flashcard,
  type FlashcardDraft,
  type KnowledgeConcept,
  type LeitnerData,
  type StudyData,
  type SubjectDocumentsData,
  type TokenUsage,
  type WrittenEvaluation,
} from "../api";
import AcademicMarkdown from "../components/AcademicMarkdown";
import TokenUsageNote from "../components/TokenUsageNote";

type StudyLaunchContext = { subjectId: number; subjectName: string; documentId?: number; topic?: string } | null;
type StudyView = "explanation" | "flashcards" | "quiz" | "leitner";
type TutorMessage = { role: "user" | "assistant"; text: string; sources?: AgentSource[]; usage?: TokenUsage };
type AnswerMode = "mental" | "written" | "mixed";
type CognitiveLevel = "recall" | "understanding" | "application" | "analysis" | "mixed";
type SessionSummary = { mode: "explanation" | "flashcards"; minutes: number; cards: number; difficult: number; successful: number };

const levelCopy: Record<CognitiveLevel, string> = { recall: "Recall", understanding: "Understanding", application: "Application", analysis: "Analysis", mixed: "Mixed" };
const answerModeCopy: Record<AnswerMode, string> = { mental: "Mental", written: "Escrita", mixed: "Mixto" };
const activityNames: Record<string, string> = { explanation: "Explicación", flashcards: "Flashcards", quick_review: "Repaso rápido", quiz: "Quiz", summary: "Resumen", reading: "Lectura", practice: "Práctica" };
const shortDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
const rating = (value: number | null) => value == null ? "—" : `${value}/5`;

function studyQuery(value: string, subjectName: string, mode: "explanation" | "flashcards") {
  const clean = value.trim();
  if (!["", "toda la asignatura", "asignatura completa", "todo el contenido"].includes(clean.toLocaleLowerCase("es-ES"))) return clean;
  return `${mode === "explanation" ? "Explicación" : "Repaso"} general de ${subjectName}`;
}

export default function StudyPage({ launchContext }: { launchContext?: StudyLaunchContext }) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [data, setData] = useState<StudyData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(launchContext?.subjectId ?? null);
  const [documents, setDocuments] = useState<SubjectDocumentsData["documents"]>([]);
  const [concepts, setConcepts] = useState<KnowledgeConcept[]>([]);
  const [leitner, setLeitner] = useState<LeitnerData | null>(null);
  const [view, setView] = useState<StudyView>("explanation");
  const [evaluationOpen, setEvaluationOpen] = useState(true);
  const [documentId, setDocumentId] = useState<number | null>(launchContext?.documentId ?? null);
  const [topic, setTopic] = useState(launchContext?.topic ?? "");
  const [duration, setDuration] = useState(30);
  const [level, setLevel] = useState<CognitiveLevel>("mixed");
  const [answerMode, setAnswerMode] = useState<AnswerMode>("mental");
  const [cardCount, setCardCount] = useState(8);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<"explanation" | "flashcards" | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [clock, setClock] = useState(Date.now());
  const [sessionTopic, setSessionTopic] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [answering, setAnswering] = useState(false);
  const [drafts, setDrafts] = useState<FlashcardDraft[]>([]);
  const [draftIndex, setDraftIndex] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [cardIndex, setCardIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [writtenAnswer, setWrittenAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<WrittenEvaluation | null>(null);
  const [evaluationUsage, setEvaluationUsage] = useState<TokenUsage>();
  const [ratingCounts, setRatingCounts] = useState({ difficult: 0, successful: 0 });
  const [selectedBox, setSelectedBox] = useState<number>(1);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  async function loadSubject(id: number) {
    setSubjectId(id); setLoading(true); setError(null); setDocumentId(null);
    try {
      const [study, materialData, knowledge, boxes] = await Promise.all([getStudy(id), getSubjectDocuments(id), getKnowledge(id), getLeitner(id)]);
      setData(study); setDocuments(materialData.documents); setConcepts(knowledge.concepts); setLeitner(boxes);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); }
    finally { setLoading(false); }
  }

  async function load() {
    setLoading(true); setError(null);
    try {
      const nextDashboard = await getDashboard(); setDashboard(nextDashboard);
      const selected = nextDashboard.subjects.find((item) => item.id === (launchContext?.subjectId ?? subjectId)) ?? nextDashboard.subjects[0];
      if (selected) { setSubjectId(selected.id); await loadSubject(selected.id); if (launchContext?.documentId) setDocumentId(launchContext.documentId); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el estudio."); setLoading(false); }
  }

  useEffect(() => { void load(); }, [launchContext?.subjectId, launchContext?.documentId]);
  useEffect(() => { if (activeMode == null) return; const timer = window.setInterval(() => setClock(Date.now()), 15_000); return () => window.clearInterval(timer); }, [activeMode]);

  async function beginExplanation() {
    if (subjectId == null || starting) return;
    const requestedTopic = studyQuery(topic, data?.subject.name ?? "la asignatura", "explanation");
    setStarting(true); setError(null); setSummary(null);
    try {
      const result = await startExplanation({ subject_id: subjectId, topic: requestedTopic, document_id: documentId });
      setConversationId(result.conversation_id);
      setMessages([{ role: "assistant", text: result.explanation, sources: result.sources, usage: result.usage }]);
      setSessionTopic(requestedTopic); setStartedAt(Date.now()); setClock(Date.now()); setActiveMode("explanation");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo iniciar la explicación."); }
    finally { setStarting(false); }
  }

  async function beginFlashcards() {
    if (subjectId == null || starting) return;
    const requestedTopic = studyQuery(topic, data?.subject.name ?? "la asignatura", "flashcards");
    setStarting(true); setError(null); setSummary(null); setDrafts([]); setCards([]);
    try {
      const result = await startFlashcards({ subject_id: subjectId, topic: requestedTopic, document_id: documentId, item_count: cardCount, cognitive_level: level, answer_mode: answerMode });
      setSessionTopic(requestedTopic);
      if (result.drafts?.length) { setDrafts(result.drafts); setDraftIndex(0); setEvaluationUsage(result.usage); }
      else { setCards(result.cards); startCardSession(result.cards); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron preparar las flashcards."); }
    finally { setStarting(false); }
  }

  function startCardSession(nextCards: Flashcard[]) {
    if (!nextCards.length) { setError("No aceptaste ninguna tarjeta para esta sesión."); return; }
    setCards(nextCards); setDrafts([]); setCardIndex(0); setRevealed(false); setWrittenAnswer(""); setEvaluation(null);
    setRatingCounts({ difficult: 0, successful: 0 }); setStartedAt(Date.now()); setClock(Date.now()); setActiveMode("flashcards");
  }

  async function decideDraft(accept: boolean) {
    const draft = drafts[draftIndex]; if (!draft || starting) return;
    setStarting(true); setError(null);
    try {
      const result = await decideFlashcardDraft(draft.id, accept, accept ? undefined : rejectionReason || undefined);
      const accepted = result.card ? [...cards, result.card] : cards;
      setCards(accepted); setRejectionReason("");
      if (draftIndex === drafts.length - 1) startCardSession(accepted);
      else setDraftIndex((value) => value + 1);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo procesar la tarjeta."); }
    finally { setStarting(false); }
  }

  async function askTutor(event: FormEvent) {
    event.preventDefault(); if (!question.trim() || answering || !conversationId) return;
    const text = question.trim(); setQuestion(""); setMessages((items) => [...items, { role: "user", text }]); setAnswering(true); setError(null);
    try {
      const result = await sendAgentMessage(text, { conversationId, subjectId, documentId, contextType: documentId ? "document" : "subject" });
      if (!result.answer) throw new Error(result.error ?? "UniCore no devolvió una respuesta.");
      setMessages((items) => [...items, { role: "assistant", text: result.answer!, sources: result.sources, usage: result.usage }]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo continuar la tutoría."); }
    finally { setAnswering(false); }
  }

  async function finishSession(modeToSave: "explanation" | "flashcards", counts = ratingCounts) {
    if (subjectId == null || startedAt == null) { setActiveMode(null); return; }
    const minutes = Math.max(1, Math.ceil((Date.now() - startedAt) / 60_000));
    try {
      await createStudySession({ subject_id: subjectId, duration_minutes: minutes, activity_type: modeToSave, topic: sessionTopic, planned_minutes: duration, completed_plan: minutes >= duration, started_at: new Date(startedAt).toISOString(), completed_at: new Date().toISOString() });
      setSummary({ mode: modeToSave, minutes, cards: modeToSave === "flashcards" ? counts.difficult + counts.successful : 0, difficult: counts.difficult, successful: counts.successful });
      setActiveMode(null); setStartedAt(null); setData(await getStudy(subjectId)); setLeitner(await getLeitner(subjectId));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo registrar la sesión."); }
  }

  async function submitCardRating(nextRating: "difficult" | "good" | "easy") {
    const card = cards[cardIndex]; if (!card || !revealed || starting) return;
    setStarting(true); setError(null);
    try {
      await rateFlashcard(card.id, nextRating);
      const nextCounts = { difficult: ratingCounts.difficult + (nextRating === "difficult" ? 1 : 0), successful: ratingCounts.successful + (nextRating === "difficult" ? 0 : 1) };
      setRatingCounts(nextCounts);
      if (cardIndex === cards.length - 1) await finishSession("flashcards", nextCounts);
      else { setCardIndex((value) => value + 1); setRevealed(false); setWrittenAnswer(""); setEvaluation(null); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo guardar la valoración."); }
    finally { setStarting(false); }
  }

  async function evaluateWritten() {
    const card = cards[cardIndex]; if (!card || !writtenAnswer.trim() || starting) return;
    setStarting(true); setError(null);
    try { const result = await evaluateFlashcardAnswer(card.id, writtenAnswer); setEvaluation(result.evaluation); setEvaluationUsage(result.usage); setRevealed(true); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo evaluar la respuesta."); }
    finally { setStarting(false); }
  }

  async function advanceWritten() {
    if (!evaluation) return;
    const nextCounts = {
      difficult: ratingCounts.difficult + (evaluation.overall_score < 70 ? 1 : 0),
      successful: ratingCounts.successful + (evaluation.overall_score >= 70 ? 1 : 0),
    };
    setRatingCounts(nextCounts);
    if (cardIndex === cards.length - 1) await finishSession("flashcards", nextCounts);
    else { setCardIndex((value) => value + 1); setRevealed(false); setWrittenAnswer(""); setEvaluation(null); }
  }

  async function changeBox(card: Flashcard, targetBox?: number, earlier = false) {
    setStarting(true); setError(null);
    try { await moveFlashcard(card.id, targetBox, earlier); if (subjectId != null) setLeitner(await getLeitner(subjectId)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo mover la tarjeta."); }
    finally { setStarting(false); }
  }

  const elapsedMinutes = startedAt == null ? 0 : Math.max(1, Math.ceil((clock - startedAt) / 60_000));
  const currentCard = cards[cardIndex];
  const writtenTurn = answerMode === "written" || (answerMode === "mixed" && cardIndex % 2 === 1);
  const boxCards = leitner?.cards.filter((item) => item.leitner_box === selectedBox) ?? [];
  const masteredReviews = data?.reviews?.reviews.filter((review) => review.status === "mastered").length ?? 0;
  const activeSources = useMemo(() => messages.flatMap((item) => item.sources ?? []).filter((source, index, all) => all.findIndex((candidate) => candidate.document_id === source.document_id && candidate.source_number === source.source_number) === index), [messages]);

  if (loading && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Preparando tu centro de entrenamiento…</h1><p>Recuperando sesiones, materiales y memoria académica.</p></section>;
  if (error && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>No se pudo cargar el centro de estudio.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;
  if (!dashboard?.subjects.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Estudio</p><h1>Aún no hay asignaturas para estudiar.</h1><p>Crea una asignatura y añade material para comenzar.</p></section>;

  if (activeMode === "explanation") return <div className="uc-page-shell uc-live-study"><header><button className="uc-back-link" onClick={() => void finishSession("explanation")}><ArrowLeft size={15} /> Finalizar sesión</button><div><p className="uc-eyebrow">Aprendizaje · {elapsedMinutes} min</p><h1>{sessionTopic}</h1><p>{data?.subject.name}</p></div></header><div className="uc-tutor-layout"><section className="uc-tutor-thread">{messages.map((message, index) => <article key={index} className={`is-${message.role}`}><span>{message.role === "assistant" ? "UniCore Tutor" : "Tú"}</span>{message.role === "assistant" ? <AcademicMarkdown content={message.text} sources={message.sources} /> : <p>{message.text}</p>}{message.role === "assistant" && <TokenUsageNote usage={message.usage} sources={message.sources?.length ?? 0} />}</article>)}{answering && <article className="is-assistant is-loading"><span>UniCore Tutor</span><p>Preparando el siguiente paso…</p></article>}<form onSubmit={askTutor}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={2} placeholder="Pregunta una duda o pide un ejemplo…" /><button disabled={answering || !question.trim()}>Preguntar</button></form></section><aside className="uc-study-sources"><p className="uc-eyebrow">Fuentes utilizadas</p>{activeSources.length ? activeSources.map((source) => <a href={`http://127.0.0.1:8766/api/documents/${source.document_id}/file`} target="_blank" rel="noreferrer" key={`${source.document_id}-${source.source_number}`}><FileText size={14} /><span><strong>{source.document_title}</strong><small>{source.source_label ?? "Abrir material"}</small></span></a>) : <p>No hay fuentes visibles para esta respuesta.</p>}<small>Máximo de cuatro fragmentos por consulta.</small></aside></div>{error && <div className="uc-inline-error">{error}</div>}</div>;

  if (drafts.length) { const draft = drafts[draftIndex]; return <div className="uc-page-shell uc-flashcard-review"><button className="uc-back-link" onClick={() => { setDrafts([]); setCards([]); }}><ArrowLeft size={15} /> Volver a configuración</button><header><p className="uc-eyebrow">Control de calidad · {draftIndex + 1}/{drafts.length}</p><h1>Acepta solo las tarjetas que merecen entrar en tu memoria.</h1><TokenUsageNote usage={evaluationUsage} sources={draft.sources.length} /></header><article className="uc-flashcard-draft">{draft.probable_duplicate && <span className="uc-duplicate-warning">Posible duplicado</span>}<span>{levelCopy[draft.cognitive_level as CognitiveLevel] ?? draft.cognitive_level}</span><h2>{draft.question}</h2><div><span>Respuesta propuesta</span><p>{draft.correct_answer}</p></div></article><div className="uc-draft-actions"><button className="uc-reject-action" onClick={() => void decideDraft(false)} disabled={starting}><X size={15} /> Rechazar</button><select value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} aria-label="Motivo de rechazo"><option value="">Motivo opcional</option>{["Repetida", "Ya lo domino", "No entra en evaluación", "Mala pregunta", "Irrelevante", "Otra"].map((item) => <option key={item}>{item}</option>)}</select><button className="uc-primary-action" onClick={() => void decideDraft(true)} disabled={starting}><Check size={15} /> Aceptar</button></div>{error && <div className="uc-inline-error">{error}</div>}</div>; }

  if (activeMode === "flashcards" && currentCard) return <div className="uc-page-shell uc-live-study uc-flashcard-session"><header><button className="uc-back-link" onClick={() => void finishSession("flashcards")}><ArrowLeft size={15} /> Finalizar sesión</button><div><p className="uc-eyebrow">Evaluación · {answerModeCopy[answerMode]} · {elapsedMinutes} min</p><h1>{sessionTopic}</h1><p>{cardIndex + 1} / {cards.length} · Box {currentCard.leitner_box ?? 1}</p></div></header><div className="uc-flashcard-progress"><span style={{ width: `${((cardIndex + (revealed ? 1 : 0)) / cards.length) * 100}%` }} /></div><article className="uc-flashcard"><span>{levelCopy[currentCard.cognitive_level as CognitiveLevel] ?? "Mixed"}</span><h2>{currentCard.question}</h2>{writtenTurn ? <div className="uc-written-answer"><label>Tu respuesta<textarea rows={7} value={writtenAnswer} onChange={(event) => setWrittenAnswer(event.target.value)} disabled={Boolean(evaluation)} /></label>{!evaluation && <button onClick={() => void evaluateWritten()} disabled={starting || writtenAnswer.trim().length < 20}>{starting ? "Evaluando…" : "Evaluar respuesta"}</button>}</div> : revealed ? <div><span>Respuesta</span><p>{currentCard.correct_answer}</p></div> : <button onClick={() => setRevealed(true)}>Mostrar respuesta</button>}</article>{evaluation && <section className="uc-written-feedback"><header><div><p className="uc-eyebrow">Evaluación estricta</p><h2>{evaluation.overall_score.toFixed(0)}/100</h2></div><TokenUsageNote usage={evaluationUsage} /></header><div className="uc-evaluation-dimensions">{evaluation.dimensions.map((item) => <div key={item.name}><span>{item.name.replaceAll("_", " ")}</span><strong>{item.score}/100</strong><p>{item.feedback}</p></div>)}</div>{evaluation.errors.length > 0 && <div><h3>Errores concretos</h3><ul>{evaluation.errors.map((item) => <li key={item}>{item}</li>)}</ul></div>}{evaluation.improvements.length > 0 && <div><h3>Cómo mejorar</h3><ul>{evaluation.improvements.map((item) => <li key={item}>{item}</li>)}</ul></div>}{evaluation.example_improvement && <blockquote>{evaluation.example_improvement}</blockquote>}</section>}{revealed && (writtenTurn ? <button className="uc-primary-action uc-written-next" disabled={starting} onClick={() => void advanceWritten()}>{cardIndex === cards.length - 1 ? "Finalizar sesión" : "Siguiente tarjeta"}</button> : <div className="uc-flashcard-ratings"><button disabled={starting} onClick={() => void submitCardRating("difficult")}>Difícil</button><button disabled={starting} onClick={() => void submitCardRating("good")}>Bien</button><button disabled={starting} onClick={() => void submitCardRating("easy")}>Fácil</button></div>)}{error && <div className="uc-inline-error">{error}</div>}</div>;

  if (summary) return <div className="uc-page-shell uc-study-complete"><Check size={24} /><p className="uc-eyebrow">Sesión registrada</p><h1>{activityNames[summary.mode]} completada.</h1><div><span>Tiempo real <strong>{summary.minutes} min</strong></span>{summary.mode === "flashcards" && <><span>Tarjetas <strong>{summary.cards}</strong></span><span>Difíciles <strong>{summary.difficult}</strong></span><span>Bien / fácil <strong>{summary.successful}</strong></span></>}</div><button className="uc-primary-action" onClick={() => setSummary(null)}>Volver al centro de estudio</button></div>;

  return <div className="uc-page-shell uc-study-page-v11"><header className="uc-page-intro"><div><p className="uc-eyebrow">Adaptive Learning</p><h1>Estudia con intención.</h1><p className="uc-page-subtitle">Aprende con tus materiales y convierte la evaluación en memoria académica duradera.</p></div><label className="uc-subject-select"><span>Asignatura</span><select value={subjectId ?? ""} onChange={(event) => void loadSubject(Number(event.target.value))}>{dashboard.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label></header><div className="uc-study-workspace"><aside className="uc-study-subnav"><p>Aprendizaje</p><button className={view === "explanation" ? "is-active" : ""} onClick={() => setView("explanation")}><BookOpen size={15} /> Explicación</button><button className="uc-study-nav-group" onClick={() => setEvaluationOpen((value) => !value)}><span>Evaluación</span><ChevronDown size={14} className={evaluationOpen ? "is-open" : ""} /></button>{evaluationOpen && <div><button className={view === "flashcards" ? "is-active" : ""} onClick={() => setView("flashcards")}><Layers3 size={15} /> Flashcards</button><button className={view === "leitner" ? "is-active" : ""} onClick={() => setView("leitner")}><RotateCcw size={15} /> Leitner boxes</button><button className={view === "quiz" ? "is-active" : ""} onClick={() => setView("quiz")}><ShieldCheck size={15} /> Quiz</button></div>}</aside><main className="uc-study-main">{view === "explanation" && <StudyConfig title="Explicación fundamentada" description="El tutor recuperará solo los fragmentos relevantes y conservará la conversación." topic={topic} setTopic={setTopic} documentId={documentId} setDocumentId={setDocumentId} documents={documents} concepts={concepts} duration={duration} setDuration={setDuration}><button className="uc-primary-action" disabled={starting} onClick={() => void beginExplanation()}>{starting ? "Preparando…" : "Iniciar explicación"}</button></StudyConfig>}{view === "flashcards" && <StudyConfig title="Flashcards universitarias" description="Una llamada por lote. Tú decides qué tarjetas entran en Leitner." topic={topic} setTopic={setTopic} documentId={documentId} setDocumentId={setDocumentId} documents={documents} concepts={concepts} duration={duration} setDuration={setDuration}><div className="uc-flashcard-config"><label><span>Nivel</span><select value={level} onChange={(event) => setLevel(event.target.value as CognitiveLevel)}>{Object.entries(levelCopy).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label><span>Modo</span><select value={answerMode} onChange={(event) => setAnswerMode(event.target.value as AnswerMode)}>{Object.entries(answerModeCopy).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label><span>Tarjetas</span><select value={cardCount} onChange={(event) => setCardCount(Number(event.target.value))}>{[5, 6, 7, 8, 9, 10].map((value) => <option key={value}>{value}</option>)}</select></label></div><p className="uc-mixed-note">Mixed favorece aplicación y análisis: 10% recall · 20% understanding · 35% application · 35% analysis.</p><button className="uc-primary-action" disabled={starting} onClick={() => void beginFlashcards()}>{starting ? "Generando lote…" : "Preparar flashcards"}</button></StudyConfig>}{view === "leitner" && <section className="uc-leitner-view"><header><p className="uc-eyebrow">Spaced repetition</p><h2>Tu memoria por boxes</h2><p>El sistema recomienda el siguiente repaso; tú mantienes el control.</p></header><div className="uc-leitner-boxes">{leitner?.boxes.map((box) => <button key={box.box} className={selectedBox === box.box ? "is-active" : ""} onClick={() => setSelectedBox(box.box)}><span>Box {box.box}</span><strong>{box.count}</strong><small>{box.name} · {box.interval_days} día{box.interval_days === 1 ? "" : "s"}</small><em>{box.due_count} para hoy</em></button>)}</div><div className="uc-leitner-ledger"><div className="uc-leitner-head"><span>Pregunta</span><span>Nivel</span><span>Último repaso</span><span>Próximo</span><span>Mover</span></div>{boxCards.length ? boxCards.map((card) => <article key={card.id}><div><strong>{card.question}</strong><small>{card.subject_name} · {card.concept_name ?? card.topic}</small></div><span>{levelCopy[card.cognitive_level as CognitiveLevel] ?? card.cognitive_level}</span><span>{card.last_reviewed_at ? new Date(card.last_reviewed_at).toLocaleDateString("es-ES") : "Sin repaso"}</span><span>{card.next_review_at ? new Date(card.next_review_at).toLocaleDateString("es-ES") : "—"}</span><div><select value={card.leitner_box} disabled={starting} onChange={(event) => void changeBox(card, Number(event.target.value))}>{[1, 2, 3, 4, 5].map((box) => <option key={box} value={box}>Box {box}</option>)}</select><button disabled={starting} onClick={() => void changeBox(card, undefined, true)}>Repasar antes</button></div></article>) : <div className="uc-task-empty"><strong>Esta box está vacía.</strong><span>Las tarjetas aceptadas aparecerán aquí.</span></div>}</div></section>}{view === "quiz" && <section className="uc-quiz-config"><header><p className="uc-eyebrow">Evaluación · futuro próximo</p><h2>Configura un quiz</h2><p>La interfaz queda preparada; el motor completo no se activa todavía.</p></header><div><label><span>Asignatura</span><select value={subjectId ?? ""} disabled>{dashboard.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label><label><span>Tema o material</span><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Tema a evaluar" /></label><label><span>Nivel</span><select value={level} onChange={(event) => setLevel(event.target.value as CognitiveLevel)}>{Object.entries(levelCopy).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label><span>Preguntas</span><select defaultValue="10"><option>5</option><option>10</option><option>15</option></select></label><label><span>Duración</span><select defaultValue="20"><option value="10">10:00</option><option value="20">20:00</option><option value="30">30:00</option></select></label></div><button className="uc-primary-action" disabled>Iniciar Quiz · disponible próximamente</button></section>}</main></div>{error && <div className="uc-inline-error uc-study-error">{error}</div>}<section className="uc-study-metrics"><div><Clock3 size={16} /><span>Tiempo total</span><strong>{data?.summary.total_study_minutes ?? 0} min</strong></div><div><BookOpen size={16} /><span>Sesiones</span><strong>{data?.summary.study_session_count ?? 0}</strong></div><div><Brain size={16} /><span>Quiz medio</span><strong>{data?.summary.quiz_average_percentage != null ? `${data.summary.quiz_average_percentage.toFixed(0)}%` : "—"}</strong></div><div><RotateCcw size={16} /><span>Repasos pendientes</span><strong>{data?.reviews?.due_count ?? 0}</strong><small>{masteredReviews} dominados</small></div></section><section className="uc-study-history"><div className="uc-section-heading"><div><p className="uc-eyebrow">Actividad real</p><h2>Sesiones recientes</h2></div></div>{data?.recent_study_sessions.length ? <div className="uc-study-session-list">{data.recent_study_sessions.map((session) => <article key={session.id}><time>{shortDate(session.session_date)}</time><div><strong>{session.topic ?? activityNames[session.activity_type]}</strong><span>{activityNames[session.activity_type] ?? session.activity_type} · {session.duration_minutes} min</span></div><div className="uc-session-ratings"><span>Foco <strong>{rating(session.focus_rating)}</strong></span><span>Dificultad <strong>{rating(session.difficulty_rating)}</strong></span><span>Satisfacción <strong>{rating(session.satisfaction_rating)}</strong></span></div></article>)}</div> : <div className="uc-task-empty"><strong>No hay sesiones registradas.</strong><span>Cuando completes una aparecerá aquí.</span></div>}</section></div>;
}

function StudyConfig({ title, description, topic, setTopic, documentId, setDocumentId, documents, concepts, duration, setDuration, children }: { title: string; description: string; topic: string; setTopic: (value: string) => void; documentId: number | null; setDocumentId: (value: number | null) => void; documents: SubjectDocumentsData["documents"]; concepts: KnowledgeConcept[]; duration: number; setDuration: (value: number) => void; children: React.ReactNode }) {
  return <section className="uc-study-config-v11"><header><p className="uc-eyebrow">Preparar sesión</p><h2>{title}</h2><p>{description}</p></header><div className="uc-study-fields"><label className="is-wide"><span>Tema o pregunta</span><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Déjalo vacío para una visión general" /></label><label><span>Material</span><select value={documentId ?? ""} onChange={(event) => setDocumentId(event.target.value ? Number(event.target.value) : null)}><option value="">Toda la asignatura</option>{documents.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label><span>Concepto</span><select value="" onChange={(event) => event.target.value && setTopic(event.target.value)}><option value="">{concepts.length ? "Seleccionar concepto" : "Sin conceptos registrados"}</option>{concepts.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select></label><label><span>Objetivo de tiempo</span><select value={duration} onChange={(event) => setDuration(Number(event.target.value))}>{[15, 30, 45, 60, 90].map((value) => <option key={value} value={value}>{value} minutos</option>)}</select></label></div><footer>{children}</footer></section>;
}
