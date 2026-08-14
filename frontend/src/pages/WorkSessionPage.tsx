import { ArrowUp, CheckCircle2, Clock3, Pause, Play, RefreshCw, Square, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  createStudySession,
  getKnowledge,
  getSubjectDocuments,
  getSubjectProfessor,
  getTasks,
  sendAgentMessage,
  type AcademicTask,
  type KnowledgeData,
  type ProfessorData,
  type SubjectDocumentsData,
} from "../api";
import { WORK_SESSION_STORAGE_KEY, type StoredWorkSession } from "../workSession";

type Message = { role: "user" | "agent"; text: string };
type ContextState = {
  professor: ProfessorData | null;
  documents: SubjectDocumentsData | null;
  knowledge: KnowledgeData | null;
  task: AcademicTask | null;
};

const progressMessages = ["Revisando el contexto de la tarea…", "Consultando tus materiales…", "Analizando los criterios de la asignatura…"];

function formatTimer(milliseconds: number) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function readText(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

export default function WorkSessionPage({
  session,
  onChange,
  onClose,
}: {
  session: StoredWorkSession;
  onChange: (session: StoredWorkSession) => void;
  onClose: () => void;
}) {
  const [remainingMs, setRemainingMs] = useState(session.remainingMs);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [context, setContext] = useState<ContextState>({ professor: null, documents: null, knowledge: null, task: null });
  const [contextLoading, setContextLoading] = useState(Boolean(session.action.subject_id));
  const [finishOpen, setFinishOpen] = useState(false);
  const [ratings, setRatings] = useState({ focus: "", difficulty: "", satisfaction: "" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<{ persisted: boolean; minutes: number } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const initializedAgent = useRef(false);

  useEffect(() => {
    const moveToStart = () => {
      window.scrollTo({ top: 0, behavior: "auto" });
    };
    moveToStart();
    const frame = window.requestAnimationFrame(moveToStart);
    const timer = window.setTimeout(moveToStart, 50);
    return () => { window.cancelAnimationFrame(frame); window.clearTimeout(timer); };
  }, []);

  useEffect(() => {
    const update = () => {
      const next = session.running && session.deadline != null
        ? Math.max(0, session.deadline - Date.now())
        : session.remainingMs;
      setRemainingMs(next);
      if (next === 0 && session.running) {
        onChange({ ...session, running: false, deadline: null, remainingMs: 0 });
      }
    };
    update();
    if (!session.running) return;
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [session, onChange]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  useEffect(() => {
    const subjectId = session.action.subject_id;
    if (subjectId == null) { setContextLoading(false); return; }
    let active = true;
    Promise.allSettled([
      getSubjectProfessor(subjectId),
      getSubjectDocuments(subjectId),
      getKnowledge(subjectId),
      getTasks(subjectId),
    ]).then(([professor, documents, knowledge, tasks]) => {
      if (!active) return;
      setContext({
        professor: professor.status === "fulfilled" ? professor.value : null,
        documents: documents.status === "fulfilled" ? documents.value : null,
        knowledge: knowledge.status === "fulfilled" ? knowledge.value : null,
        task: tasks.status === "fulfilled"
          ? tasks.value.tasks.find(({ task }) => task.id === session.action.source_id)?.task ?? null
          : null,
      });
      setContextLoading(false);
    });
    return () => { active = false; };
  }, [session.action.source_id, session.action.subject_id]);

  const agentContext = useMemo(() => {
    const metadata = session.action.metadata;
    const professorFacts = context.professor
      ? {
          professors: context.professor.professors.map((item) => item.name),
          preferences: context.professor.preferences.map((item) => item.preference),
          rubric: context.professor.rubric_criteria.map((item) => item.title),
        }
      : null;
    return {
      action: session.action.title,
      subject: session.action.subject_name,
      duration_minutes: session.durationMinutes,
      recommendation_reasons: session.action.reasons,
      due_date: context.task?.due_date ?? metadata.due_date ?? null,
      progress_percentage: context.task?.progress_percentage ?? metadata.progress_percentage ?? null,
      task_description: context.task?.description ?? null,
      task_notes: context.task?.notes ?? null,
      professor_context: professorFacts,
      related_documents: context.documents?.documents.slice(0, 6).map((item) => item.title) ?? [],
      priority_concepts: context.knowledge?.priority_concepts.slice(0, 5).map((item) => ({ name: item.name, status: item.status, mastery: item.mastery_percentage })) ?? [],
    };
  }, [context, session.action, session.durationMinutes]);

  async function askAgent(text: string, visible = true) {
    const clean = text.trim();
    if (!clean || submitting) return;
    if (visible) setMessages((current) => [...current, { role: "user", text: clean }]);
    setInput("");
    setSubmitting(true);
    setAgentError(null);
    setProgressIndex(0);
    try {
      const response = await sendAgentMessage(clean, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, {
        role: "agent",
        text: response.answer ?? "UniCore terminó la consulta sin una respuesta visible.",
      }]);
    } catch (caught) {
      setAgentError(caught instanceof Error ? caught.message : "No se pudo consultar UniCore Agent.");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (contextLoading || initializedAgent.current) return;
    initializedAgent.current = true;
    const prompt = [
      "Estoy comenzando este bloque de trabajo académico. Ya tienes el contexto siguiente:",
      JSON.stringify(agentContext),
      "Dame una orientación inicial breve y práctica para ejecutar esta acción ahora. Usa solo los datos disponibles; si falta información, dilo. No realices escrituras.",
    ].join("\n\n");
    void askAgent(prompt, false);
  }, [agentContext, contextLoading]);

  useEffect(() => {
    if (!submitting) return;
    const timer = window.setInterval(() => setProgressIndex((value) => (value + 1) % progressMessages.length), 1400);
    return () => window.clearInterval(timer);
  }, [submitting]);

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
  }, [messages, submitting]);

  function pause() {
    const nextRemaining = session.deadline == null ? remainingMs : Math.max(0, session.deadline - Date.now());
    onChange({ ...session, running: false, deadline: null, remainingMs: nextRemaining });
  }

  function resume() {
    onChange({ ...session, running: true, deadline: Date.now() + remainingMs, remainingMs });
  }

  async function finish() {
    const elapsedMs = session.durationMinutes * 60_000 - remainingMs;
    const actualMinutes = Math.max(0, Math.round(elapsedMs / 60_000));
    setSaving(true);
    setSaveError(null);
    try {
      if (session.action.subject_id != null && elapsedMs >= 60_000) {
        await createStudySession({
          subject_id: session.action.subject_id,
          duration_minutes: Math.max(1, actualMinutes),
          activity_type: session.action.type === "review" ? "quick_review" : session.action.type === "assessment" ? "other" : session.action.type === "knowledge" ? "explanation" : "project",
          session_date: new Date().toISOString().slice(0, 10),
          topic: session.action.title,
          planned_minutes: session.durationMinutes,
          completed_plan: remainingMs === 0,
          focus_rating: ratings.focus ? Number(ratings.focus) : null,
          difficulty_rating: ratings.difficulty ? Number(ratings.difficulty) : null,
          satisfaction_rating: ratings.satisfaction ? Number(ratings.satisfaction) : null,
          started_at: session.startedAt,
          completed_at: new Date().toISOString(),
        });
        setCompleted({ persisted: true, minutes: Math.max(1, actualMinutes) });
      } else {
        setCompleted({ persisted: false, minutes: actualMinutes });
      }
      window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : "No se pudo registrar el bloque.");
    } finally {
      setSaving(false);
    }
  }

  function discard() {
    window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
    onClose();
  }

  function submit(event: FormEvent) { event.preventDefault(); void askAgent(input); }

  const professorItems = context.professor?.preferences ?? [];
  const rubricItems = context.professor?.rubric_criteria ?? [];
  const documents = context.documents?.documents ?? [];
  const concepts = context.knowledge?.priority_concepts ?? [];
  const dueDate = context.task?.due_date ?? readText(session.action.metadata.due_date);
  const progress = context.task?.progress_percentage ?? (typeof session.action.metadata.progress_percentage === "number" ? session.action.metadata.progress_percentage : null);

  if (completed) {
    return <section className="uc-page-shell uc-work-complete">
      <CheckCircle2 size={30} />
      <p className="uc-eyebrow">Bloque finalizado</p>
      <h1>{session.action.title}</h1>
      <strong>{completed.minutes} min de trabajo real</strong>
      <p>{completed.persisted ? "La sesión se ha registrado en tu actividad académica." : "El bloque duró menos de un minuto o no tenía asignatura; no se registró como sesión de estudio."}</p>
      <button className="uc-primary-action" onClick={onClose}>Volver a Inicio</button>
    </section>;
  }

  return <div className="uc-page-shell uc-work-page">
    <header className="uc-work-header">
      <div><p className="uc-eyebrow">Trabajando ahora · {session.action.subject_name ?? "Trabajo académico"}</p><h1>{session.action.title}</h1></div>
      <div className="uc-work-timer" aria-live="polite"><span>Tiempo restante</span><strong>{formatTimer(remainingMs)}</strong></div>
      <div className="uc-work-controls">
        {session.running ? <button onClick={pause}><Pause size={15} /> Pausar</button> : <button onClick={resume} disabled={remainingMs === 0}><Play size={15} /> Reanudar</button>}
        <button className="is-finish" onClick={() => { pause(); setFinishOpen(true); }}><Square size={14} /> Finalizar bloque</button>
      </div>
    </header>

    <section className="uc-work-layout">
      <div className="uc-work-agent">
        <div className="uc-work-agent-heading"><div><p className="uc-eyebrow">UniCore Agent</p><h2>Asistencia para este bloque</h2></div><span>Modo seguro · sin escrituras</span></div>
        <div ref={streamRef} className="uc-work-message-stream">
          {messages.map((message, index) => <article key={index} className={`uc-message is-${message.role}`}><span>{message.role === "user" ? "Tú" : "UniCore"}</span><p>{message.text}</p></article>)}
          {submitting && <article className="uc-message is-agent is-working"><span>UniCore</span><p>{progressMessages[progressIndex]}</p><i /><i /><i /></article>}
          {agentError && <div className="uc-agent-error"><span>{agentError}</span><button onClick={() => setAgentError(null)} aria-label="Cerrar error"><RefreshCw size={14} /></button></div>}
          <div ref={endRef} />
        </div>
        <form className="uc-agent-composer" onSubmit={submit}><textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Pregunta sobre esta tarea…" rows={2} disabled={submitting} /><button disabled={submitting || !input.trim()} aria-label="Enviar"><ArrowUp size={17} /></button><small>UniCore conserva el contexto de este bloque durante la conversación.</small></form>
      </div>

      <aside className="uc-work-context">
        <p className="uc-eyebrow">Ten en cuenta</p>
        {contextLoading ? <p className="uc-work-context-loading">Leyendo el contexto académico…</p> : <>
          {(dueDate || progress != null || context.task?.description) && <section><h2>La tarea</h2>{dueDate && <div><span>Fecha límite</span><strong>{new Date(`${dueDate}T00:00:00`).toLocaleDateString("es-ES", { day: "numeric", month: "long" })}</strong></div>}{progress != null && <div><span>Progreso</span><strong>{progress}%</strong></div>}{context.task?.description && <p>{context.task.description}</p>}{context.task?.notes && <p>{context.task.notes}</p>}</section>}
          {(professorItems.length > 0 || rubricItems.length > 0) && <section><h2>Profesor y criterios</h2>{rubricItems.slice(0, 4).map((item) => <div key={`r-${item.id}`}><strong>{item.title}</strong><span>{item.weight_percentage != null ? `${item.weight_percentage}%` : item.description ?? "Criterio registrado"}</span></div>)}{professorItems.slice(0, 4).map((item) => <div key={`p-${item.id}`}><strong>{item.preference}</strong><span>Importancia {item.importance}/5</span></div>)}</section>}
          {documents.length > 0 && <section><h2>Materiales relacionados</h2>{documents.slice(0, 5).map((item) => <div key={item.id}><strong>{item.title}</strong><span>{item.has_extracted_text ? "Texto disponible" : "Documento registrado"}</span></div>)}</section>}
          {concepts.length > 0 && <section><h2>Conceptos que requieren atención</h2>{concepts.slice(0, 4).map((item) => <div key={item.id}><strong>{item.name}</strong><span>{item.mastery_percentage != null ? `${item.mastery_percentage.toFixed(0)}% de dominio` : "Sin evaluación suficiente"}</span></div>)}</section>}
          {!context.task && professorItems.length === 0 && rubricItems.length === 0 && documents.length === 0 && concepts.length === 0 && <p className="uc-work-context-loading">No hay contexto adicional registrado para esta acción. El Agent seguirá usando la recomendación actual.</p>}
        </>}
      </aside>
    </section>

    {finishOpen && <div className="uc-form-backdrop" onMouseDown={() => !saving && setFinishOpen(false)}><section className="uc-form-modal uc-work-finish-modal" onMouseDown={(event) => event.stopPropagation()}><header><div><p className="uc-eyebrow">Cerrar bloque</p><h2>Registra cómo ha ido.</h2></div><button onClick={() => setFinishOpen(false)} aria-label="Cerrar"><X size={18} /></button></header><p>Las valoraciones son opcionales. Se guardarán con los minutos reales si el bloque ha durado al menos un minuto.</p><div className="uc-work-ratings">{([['focus','Foco'],['difficulty','Dificultad'],['satisfaction','Satisfacción']] as const).map(([key, label]) => <label key={key}>{label}<select value={ratings[key]} onChange={(event) => setRatings({ ...ratings, [key]: event.target.value })}><option value="">Sin valorar</option>{[1,2,3,4,5].map((value) => <option key={value} value={value}>{value} / 5</option>)}</select></label>)}</div>{saveError && <p className="uc-form-error">{saveError}</p>}<footer><button className="uc-discard-work" onClick={discard} disabled={saving}>Salir sin registrar</button><button onClick={() => setFinishOpen(false)} disabled={saving}>Seguir trabajando</button><button className="uc-primary-action" onClick={() => void finish()} disabled={saving}>{saving ? "Registrando…" : "Finalizar"} <Clock3 size={15} /></button></footer></section></div>}
  </div>;
}
