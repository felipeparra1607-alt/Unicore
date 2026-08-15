import {
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileText,
  MessageCircle,
  Pause,
  Play,
  RefreshCw,
  Square,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import AcademicMarkdown from "../components/AcademicMarkdown";
import {
  createStudySession,
  getCurriculum,
  getConversation,
  getDocumentContent,
  getDocumentFileUrl,
  getSubjectDocuments,
  getSubjectProfessor,
  getTasks,
  sendAgentMessage,
  type AcademicTask,
  type AgentSource,
  type DocumentContent,
  type CurriculumData,
  type CurriculumTopic,
  type ProfessorData,
  type SubjectDocumentsData,
} from "../api";
import {
  WORK_SESSION_STORAGE_KEY,
  type StoredWorkSession,
} from "../workSession";

type Message = {
  role: "user" | "agent";
  text: string;
  sources?: AgentSource[];
};
type ContextState = {
  professor: ProfessorData | null;
  documents: SubjectDocumentsData | null;
  task: AcademicTask | null;
  curriculum: CurriculumData | null;
};
const progressMessages = [
  "Revisando el contexto…",
  "Consultando materiales relacionados…",
  "Preparando una respuesta académica…",
];
const formatTimer = (milliseconds: number) => {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
};
const metadataIds = (value: unknown) =>
  Array.isArray(value)
    ? value.filter((id): id is number => typeof id === "number")
    : [];

export default function WorkSessionPage({
  session,
  onChange,
  onClose,
}: {
  session: StoredWorkSession;
  onChange: (session: StoredWorkSession) => void;
  onClose: () => void;
}) {
  const action =
    session.actions[Math.min(session.activeIndex, session.actions.length - 1)];
  const [remainingMs, setRemainingMs] = useState(session.remainingMs);
  const [actionRemainingMs, setActionRemainingMs] = useState(
    session.actionRemainingMs,
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>(
    session.conversationId,
  );
  const [activeDocument, setActiveDocument] = useState<DocumentContent | null>(
    null,
  );
  const [documentLoading, setDocumentLoading] = useState(false);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [context, setContext] = useState<ContextState>({
    professor: null,
    documents: null,
    task: null,
    curriculum: null,
  });
  const [activeTopicId, setActiveTopicId] = useState<number | null>(null);
  const [contextLoading, setContextLoading] = useState(
    Boolean(action?.subject_id),
  );
  const [finishOpen, setFinishOpen] = useState(false);
  const [ratings, setRatings] = useState({
    focus: "",
    difficulty: "",
    satisfaction: "",
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<{
    persisted: boolean;
    minutes: number;
  } | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const advancedIndex = useRef<number | null>(null);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  useEffect(() => {
    const update = () => {
      const total =
        session.running && session.deadline != null
          ? Math.max(0, session.deadline - Date.now())
          : session.remainingMs;
      const current =
        session.running && session.actionDeadline != null
          ? Math.max(0, session.actionDeadline - Date.now())
          : session.actionRemainingMs;
      setRemainingMs(total);
      setActionRemainingMs(current);
      if (total === 0 && session.running)
        onChange({
          ...session,
          running: false,
          deadline: null,
          actionDeadline: null,
          remainingMs: 0,
          actionRemainingMs: 0,
        });
    };
    update();
    if (!session.running) return;
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [session, onChange]);

  useEffect(() => {
    if (!action || action.subject_id == null) {
      setContext({
        professor: null,
        documents: null,
        task: null,
        curriculum: null,
      });
      setContextLoading(false);
      return;
    }
    let alive = true;
    setContextLoading(true);
    setActiveDocument(null);
    Promise.allSettled([
      getSubjectProfessor(action.subject_id),
      getSubjectDocuments(action.subject_id),
      getTasks(action.subject_id),
      getCurriculum(action.subject_id),
    ]).then(([professor, documents, tasks, curriculum]) => {
      if (!alive) return;
      setContext({
        professor: professor.status === "fulfilled" ? professor.value : null,
        documents: documents.status === "fulfilled" ? documents.value : null,
        task:
          tasks.status === "fulfilled"
            ? (tasks.value.tasks.find(
                ({ task }) => task.id === action.source_id,
              )?.task ?? null)
            : null,
        curriculum: curriculum.status === "fulfilled" ? curriculum.value : null,
      });
      setContextLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [action?.source_id, action?.subject_id]);

  useEffect(() => {
    if (!session.conversationId) return;
    getConversation(session.conversationId)
      .then(({ conversation }) =>
        setMessages(
          conversation.messages.map((item) => ({
            role: item.role === "assistant" ? "agent" : "user",
            text: item.content,
            sources: item.sources,
          })),
        ),
      )
      .catch(() => setConversationId(undefined));
  }, [session.conversationId]);
  useEffect(() => {
    if (!submitting) return;
    const timer = window.setInterval(
      () => setProgressIndex((value) => (value + 1) % progressMessages.length),
      1400,
    );
    return () => window.clearInterval(timer);
  }, [submitting]);
  useEffect(() => {
    if (drawerOpen && streamRef.current)
      streamRef.current.scrollTo({
        top: streamRef.current.scrollHeight,
        behavior: "smooth",
      });
  }, [messages, submitting, drawerOpen]);

  function pause() {
    const total =
      session.deadline == null
        ? remainingMs
        : Math.max(0, session.deadline - Date.now());
    const current =
      session.actionDeadline == null
        ? actionRemainingMs
        : Math.max(0, session.actionDeadline - Date.now());
    onChange({
      ...session,
      running: false,
      deadline: null,
      actionDeadline: null,
      remainingMs: total,
      actionRemainingMs: current,
    });
  }
  function resume() {
    onChange({
      ...session,
      running: true,
      deadline: Date.now() + remainingMs,
      actionDeadline: Date.now() + actionRemainingMs,
      remainingMs,
      actionRemainingMs,
    });
  }
  function nextAction() {
    if (session.activeIndex >= session.actions.length - 1) {
      pause();
      setFinishOpen(true);
      return;
    }
    const nextIndex = session.activeIndex + 1;
    const nextMs = Math.min(
      remainingMs,
      session.actions[nextIndex].allocated_minutes * 60_000,
    );
    onChange({
      ...session,
      activeIndex: nextIndex,
      actionRemainingMs: nextMs,
      actionDeadline: session.running ? Date.now() + nextMs : null,
      remainingMs,
      deadline: session.running ? Date.now() + remainingMs : null,
      activeDocumentId: null,
    });
  }
  useEffect(() => {
    if (
      !session.running ||
      actionRemainingMs > 0 ||
      remainingMs <= 0 ||
      session.activeIndex >= session.actions.length - 1 ||
      advancedIndex.current === session.activeIndex
    )
      return;
    advancedIndex.current = session.activeIndex;
    nextAction();
  }, [actionRemainingMs, remainingMs, session.activeIndex, session.running]);

  async function askAgent(text: string) {
    const clean = text.trim();
    if (!clean || submitting || !action) return;
    setMessages((current) => [...current, { role: "user", text: clean }]);
    setInput("");
    setSubmitting(true);
    setAgentError(null);
    setProgressIndex(0);
    try {
      const response = await sendAgentMessage(clean, {
        conversationId,
        subjectId: action.subject_id,
        documentId: activeDocument?.document.id ?? null,
        contextType: "work_session",
        workContext: {
          action: action.title,
          subject: action.subject_name,
          duration_minutes: action.allocated_minutes,
          due_date: context.task?.due_date ?? action.metadata.due_date ?? null,
          progress_percentage:
            context.task?.progress_percentage ??
            action.metadata.progress_percentage ??
            null,
          task_description: context.task?.description ?? null,
          task_notes: context.task?.notes ?? null,
        },
      });
      setConversationId(response.conversation_id);
      onChange({
        ...session,
        conversationId: response.conversation_id,
        activeDocumentId: activeDocument?.document.id ?? null,
      });
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text:
            response.answer ??
            "UniCore terminó la consulta sin una respuesta visible.",
          sources: response.sources,
        },
      ]);
    } catch (caught) {
      setAgentError(
        caught instanceof Error
          ? caught.message
          : "No se pudo consultar UniCore Agent.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function openDocument(documentId: number) {
    setDocumentLoading(true);
    setAgentError(null);
    try {
      const result = await getDocumentContent(documentId);
      setActiveDocument(result);
      onChange({ ...session, activeDocumentId: documentId, conversationId });
    } catch (caught) {
      setAgentError(
        caught instanceof Error
          ? caught.message
          : "No se pudo abrir el material.",
      );
    } finally {
      setDocumentLoading(false);
    }
  }

  async function finish() {
    const elapsed = Math.max(
      0,
      session.durationMinutes - Math.round(remainingMs / 60_000),
    );
    setSaving(true);
    setSaveError(null);
    try {
      const allocated = Math.max(
        1,
        session.actions.reduce((sum, item) => sum + item.allocated_minutes, 0),
      );
      const records = session.actions
        .flatMap((item) =>
          item.subject_id == null
            ? []
            : [
                {
                  item,
                  minutes: Math.max(
                    0,
                    Math.round((elapsed * item.allocated_minutes) / allocated),
                  ),
                },
              ],
        )
        .filter(({ minutes }) => minutes > 0);
      await Promise.all(
        records.map(({ item, minutes }) =>
          createStudySession({
            subject_id: item.subject_id!,
            duration_minutes: minutes,
            activity_type:
              item.type === "review"
                ? "quick_review"
                : item.type === "knowledge"
                  ? "explanation"
                  : item.type === "task"
                    ? "project"
                    : "other",
            session_date: new Date().toISOString().slice(0, 10),
            topic: item.title,
            planned_minutes: item.allocated_minutes,
            completed_plan: remainingMs === 0,
            focus_rating: ratings.focus ? Number(ratings.focus) : null,
            difficulty_rating: ratings.difficulty
              ? Number(ratings.difficulty)
              : null,
            satisfaction_rating: ratings.satisfaction
              ? Number(ratings.satisfaction)
              : null,
            started_at: session.startedAt,
            completed_at: new Date().toISOString(),
          }),
        ),
      );
      setCompleted({ persisted: records.length > 0, minutes: elapsed });
      window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
    } catch (caught) {
      setSaveError(
        caught instanceof Error
          ? caught.message
          : "No se pudo registrar el bloque.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!action)
    return (
      <section className="uc-page-shell uc-state-page">
        <h1>El plan está vacío.</h1>
        <button onClick={onClose}>Volver</button>
      </section>
    );
  if (completed)
    return (
      <section className="uc-page-shell uc-work-complete">
        <CheckCircle2 size={30} />
        <p className="uc-eyebrow">Bloque finalizado</p>
        <h1>Sesión completada</h1>
        <strong>{completed.minutes} min de trabajo real</strong>
        <p>
          {completed.persisted
            ? "La actividad se ha registrado por asignatura."
            : "El bloque no tuvo minutos o asignaturas registrables."}
        </p>
        <button className="uc-primary-action" onClick={onClose}>
          Volver a Inicio
        </button>
      </section>
    );

  const professorItems = context.professor?.preferences ?? [];
  const rubricItems = context.professor?.rubric_criteria ?? [];
  const normalizedTitle = action.title.toLocaleLowerCase();
  const unitId =
    typeof action.metadata.unit_id === "number"
      ? action.metadata.unit_id
      : null;
  const activeUnit =
    context.curriculum?.units.find((unit) => unit.id === unitId) ??
    context.curriculum?.units.find((unit) =>
      normalizedTitle.includes(unit.name.toLocaleLowerCase()),
    ) ??
    null;
  const curriculumTopics = activeUnit?.topics ?? [];
  const hasStudyHistory = curriculumTopics.some(
    (topic) => topic.status !== "not_studied",
  );
  const statusOrder: Record<CurriculumTopic["status"], number> = {
    learning: 0,
    consolidating: 1,
    not_studied: 2,
    mastered: 3,
  };
  const topics = hasStudyHistory
    ? [...curriculumTopics].sort(
        (left, right) =>
          statusOrder[left.status] - statusOrder[right.status],
      )
    : curriculumTopics;
  const activeTopic: CurriculumTopic | null =
    topics.find((topic) => topic.id === activeTopicId) ?? null;
  const ids = metadataIds(action.metadata.document_ids);
  const curriculumDocumentIds = [
    ...new Set(
      topics.flatMap((topic) =>
        [
          ...topic.sources,
          ...topic.subtopics.flatMap((subtopic) => subtopic.sources),
        ].map((source) => source.document_id),
      ),
    ),
  ];
  const relatedDocumentIds = ids.length ? ids : curriculumDocumentIds;
  const documents = (context.documents?.documents ?? []).filter((document) =>
    relatedDocumentIds.includes(document.id),
  );
  const topicStatus = {
    not_studied: "No estudiado",
    learning: "Necesita atención",
    consolidating: "Consolidando",
    mastered: "Dominado",
  } as const;
  const dueDate =
    context.task?.due_date ??
    (typeof action.metadata.due_date === "string"
      ? action.metadata.due_date
      : null);
  const progress =
    context.task?.progress_percentage ??
    (typeof action.metadata.progress_percentage === "number"
      ? action.metadata.progress_percentage
      : null);
  const examples =
    activeDocument?.content
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(
        (line) =>
          /\b(ejemplo|example|caso|case)\b/i.test(line) && line.length > 20,
      )
      .slice(0, 3) ?? [];

  return (
    <div className={`uc-page-shell uc-work-page ${drawerOpen ? "is-agent-open" : ""}`}>
      <header className="uc-work-header">
        <div>
          <p className="uc-eyebrow">
            Actividad {session.activeIndex + 1} de {session.actions.length} ·{" "}
            {action.subject_name ?? "Trabajo académico"}
          </p>
          <h1>{action.title}</h1>
        </div>
        <div className="uc-work-timers">
          <div>
            <span>Actividad</span>
            <strong>{formatTimer(actionRemainingMs)}</strong>
          </div>
          <div>
            <span>Sesión</span>
            <strong>{formatTimer(remainingMs)}</strong>
          </div>
        </div>
        <div className="uc-work-controls">
          {session.running ? (
            <button onClick={pause}>
              <Pause size={15} /> Pausar
            </button>
          ) : (
            <button onClick={resume} disabled={remainingMs === 0}>
              <Play size={15} /> Reanudar
            </button>
          )}
          <button
            className="uc-work-agent-cta"
            onClick={() => setDrawerOpen(true)}
          >
            <MessageCircle size={15} /> ✦ Preguntar a UniCore
          </button>
          <button
            className="is-finish"
            onClick={() => {
              pause();
              setFinishOpen(true);
            }}
          >
            <Square size={14} /> Finalizar
          </button>
        </div>
      </header>
      <div className="uc-work-progress">
        <span
          style={{
            width: `${((session.activeIndex + 1) / session.actions.length) * 100}%`,
          }}
        />
      </div>
      <main className="uc-work-context-main">
        <header>
          <div>
            <p className="uc-eyebrow">Contexto de trabajo</p>
            <h2>Lo necesario para avanzar ahora</h2>
          </div>
          {session.activeIndex < session.actions.length - 1 && (
            <button onClick={nextAction}>
              Siguiente actividad <ArrowRight size={15} />
            </button>
          )}
        </header>
        {contextLoading ? (
          <p className="uc-work-context-loading">
            Leyendo el contexto académico…
          </p>
        ) : (
          <>
            {activeUnit && (
              <section className="uc-work-curriculum">
                <header>
                  <div>
                    <p className="uc-eyebrow">{activeUnit.name}</p>
                    <h2>Temas para repasar</h2>
                  </div>
                  <span>{topics.length} temas</span>
                </header>
                <ol>
                  {topics.map((topic, index) => (
                    <li
                      key={topic.id}
                      className={activeTopicId === topic.id ? "is-active" : ""}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{topic.name}</strong>
                        <small>{topicStatus[topic.status]}</small>
                      </div>
                      <button onClick={() => setActiveTopicId(topic.id)}>
                        Abrir tema
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            )}
            {activeTopic && (
              <section className="uc-work-topic-detail">
                <header>
                  <div>
                    <p className="uc-eyebrow">Tema activo</p>
                    <h2>{activeTopic.name}</h2>
                  </div>
                  <button onClick={() => setActiveTopicId(null)}>Cerrar</button>
                </header>
                <div className="uc-work-topic-grid">
                  <div>
                    <h3>Conceptos clave</h3>
                    {activeTopic.subtopics.length ? (
                      <ul>
                        {activeTopic.subtopics.map((item) => (
                          <li key={item.id}>{item.name}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>No hay subtemas separados en el Curriculum.</p>
                    )}
                  </div>
                  <div>
                    <h3>Estado de dominio</h3>
                    <strong>{topicStatus[activeTopic.status]}</strong>
                    <p>
                      Basado únicamente en evidencias académicas registradas.
                    </p>
                  </div>
                </div>
                {activeTopic.sources.length > 0 && (
                  <div className="uc-work-topic-sources">
                    <h3>Fuentes</h3>
                    {activeTopic.sources.map((source) => (
                      <button
                        key={`${source.document_id}-${source.source_label}`}
                        onClick={() => void openDocument(source.document_id)}
                      >
                        <FileText size={14} /> {source.title} ·{" "}
                        {source.source_label ?? "material asociado"}
                      </button>
                    ))}
                  </div>
                )}
                {activeTopic.also_seen_in.length > 0 && (
                  <div>
                    <h3>Conexiones reales</h3>
                    {activeTopic.also_seen_in.map((item) => (
                      <p key={`${item.subject_id}-${item.concept_name}`}>
                        {item.concept_name} · {item.subject_name}
                      </p>
                    ))}
                  </div>
                )}
              </section>
            )}
            <div className="uc-work-context-ledger">
              {(dueDate || progress != null || context.task?.description) && (
                <section>
                  <h3>Requisitos y estado</h3>
                  {dueDate && (
                    <div>
                      <span>Fecha límite</span>
                      <strong>
                        {new Date(`${dueDate}T00:00:00`).toLocaleDateString(
                          "es-ES",
                          { day: "numeric", month: "long" },
                        )}
                      </strong>
                    </div>
                  )}
                  {progress != null && (
                    <div>
                      <span>Progreso</span>
                      <strong>{progress}%</strong>
                    </div>
                  )}
                  {context.task?.description && (
                    <p>{context.task.description}</p>
                  )}
                  {context.task?.notes && <p>{context.task.notes}</p>}
                </section>
              )}
              {(professorItems.length > 0 || rubricItems.length > 0) && (
                <section>
                  <h3>Criterios relevantes</h3>
                  <ol>
                    {[...professorItems]
                      .sort((a, b) => b.importance - a.importance)
                      .slice(0, 4)
                      .map((item) => (
                        <li key={`p-${item.id}`}>
                          <strong>{item.preference}</strong>
                        </li>
                      ))}
                    {[...rubricItems].slice(0, 4).map((item) => (
                      <li key={`r-${item.id}`}>
                        <strong>{item.title}</strong>
                        {item.description && <span>{item.description}</span>}
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {documents.length > 0 && (
                <section className="uc-work-materials">
                  <h3>Material relacionado</h3>
                  {documents.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => void openDocument(item.id)}
                      disabled={documentLoading}
                    >
                      <FileText size={15} />
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.file_type?.toUpperCase() ?? "Documento"}
                        </small>
                      </span>
                    </button>
                  ))}
                </section>
              )}
              {!context.task &&
                !activeUnit &&
                professorItems.length === 0 &&
                rubricItems.length === 0 &&
                documents.length === 0 && (
                  <p className="uc-work-context-loading">
                    No hay contexto adicional relacionado con esta acción.
                    UniCore no mostrará materiales ni conexiones sin una
                    relación HTTP verificable.
                  </p>
                )}
            </div>
          </>
        )}
        {activeDocument && (
          <section className="uc-work-document">
            <header>
              <div>
                <span>Documento activo</span>
                <strong>{activeDocument.document.title}</strong>
              </div>
              <button
                onClick={() => setActiveDocument(null)}
                aria-label="Cerrar documento"
              >
                <X size={15} />
              </button>
            </header>
            <pre>{activeDocument.content}</pre>
            <div>
              <a
                href={getDocumentFileUrl(activeDocument.document.id)}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={14} /> Abrir original
              </a>
              <button
                onClick={() => {
                  setDrawerOpen(true);
                  setInput("Ayúdame a trabajar con este material: ");
                }}
              >
                <MessageCircle size={14} /> Preguntar al Agent
              </button>
            </div>
          </section>
        )}
        {examples.length > 0 && (
          <section className="uc-work-examples">
            <header>
              <p className="uc-eyebrow">Ejemplos detectados</p>
              <h3>Casos presentes en el material</h3>
            </header>
            {examples.map((example, index) => (
              <blockquote key={index}>
                {example}
                <cite>{activeDocument?.document.title}</cite>
              </blockquote>
            ))}
          </section>
        )}
        <section className="uc-work-future">
          <span>Recursos externos</span>
          <strong>Próximamente</strong>
          <p>
            Enlaces y referencias externas se incorporarán cuando exista una
            fuente HTTP verificable.
          </p>
        </section>
      </main>

      {drawerOpen && (
        <>
          <button
            className="uc-work-drawer-overlay"
            onClick={() => setDrawerOpen(false)}
            aria-label="Cerrar Agent"
          />
          <aside className="uc-work-agent-drawer">
            <header>
              <div>
                <p className="uc-eyebrow">UniCore Agent</p>
                <h2>Ayuda contextual</h2>
              </div>
              <button onClick={() => setDrawerOpen(false)} aria-label="Cerrar">
                <X size={18} />
              </button>
            </header>
            <p className="uc-agent-drawer-note">
              Pregunta a UniCore cuando necesites ayuda con este bloque.
            </p>
            <div ref={streamRef} className="uc-work-message-stream">
              {messages.length === 0 && (
                <div className="uc-work-agent-neutral">
                  <strong>Asistencia disponible.</strong>
                  <p>
                    Pregunta sobre la actividad, un criterio o el material
                    abierto.
                  </p>
                </div>
              )}
              {messages.map((message, index) => (
                <article
                  key={index}
                  className={`uc-message is-${message.role}`}
                >
                  <span>{message.role === "user" ? "Tú" : "UniCore"}</span>
                  {message.role === "agent" ? (
                    <AcademicMarkdown
                      content={message.text}
                      sources={message.sources}
                    />
                  ) : (
                    <p>{message.text}</p>
                  )}
                </article>
              ))}
              {submitting && (
                <article className="uc-message is-agent is-working">
                  <span>UniCore</span>
                  <p>{progressMessages[progressIndex]}</p>
                </article>
              )}
              {agentError && (
                <div className="uc-agent-error">
                  <span>{agentError}</span>
                  <button onClick={() => setAgentError(null)}>
                    <RefreshCw size={14} />
                  </button>
                </div>
              )}
            </div>
            <form
              className="uc-agent-composer"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                void askAgent(input);
              }}
            >
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={
                  activeDocument
                    ? `Pregunta sobre ${activeDocument.document.title}…`
                    : "Pregunta sobre esta actividad…"
                }
                rows={3}
                disabled={submitting}
              />
              <button
                disabled={submitting || !input.trim()}
                aria-label="Enviar"
              >
                <ArrowUp size={17} />
              </button>
            </form>
          </aside>
        </>
      )}
      {finishOpen && (
        <div
          className="uc-form-backdrop"
          onMouseDown={() => !saving && setFinishOpen(false)}
        >
          <section
            className="uc-form-modal uc-work-finish-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="uc-eyebrow">Cerrar bloque</p>
                <h2>Registra cómo ha ido.</h2>
              </div>
              <button onClick={() => setFinishOpen(false)} aria-label="Cerrar">
                <X size={18} />
              </button>
            </header>
            <p>
              Las valoraciones son opcionales. Los minutos se repartirán entre
              las acciones académicas del plan.
            </p>
            <div className="uc-work-ratings">
              {(
                [
                  ["focus", "Foco"],
                  ["difficulty", "Dificultad"],
                  ["satisfaction", "Satisfacción"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <select
                    value={ratings[key]}
                    onChange={(event) =>
                      setRatings({ ...ratings, [key]: event.target.value })
                    }
                  >
                    <option value="">Sin valorar</option>
                    {[1, 2, 3, 4, 5].map((value) => (
                      <option key={value} value={value}>
                        {value} / 5
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            {saveError && <p className="uc-form-error">{saveError}</p>}
            <footer>
              <button
                onClick={() => {
                  window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
                  onClose();
                }}
                disabled={saving}
              >
                Salir sin registrar
              </button>
              <button onClick={() => setFinishOpen(false)} disabled={saving}>
                Seguir trabajando
              </button>
              <button
                className="uc-primary-action"
                onClick={() => void finish()}
                disabled={saving}
              >
                {saving ? "Registrando…" : "Finalizar"} <Clock3 size={15} />
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
