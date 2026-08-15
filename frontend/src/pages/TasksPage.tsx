import {
  ArrowDown,
  ArrowUp,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  Minus,
  Play,
  Plus,
  RefreshCw,
  SlidersHorizontal,
  Upload,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeTaskFile,
  createTask,
  getDashboard,
  getCurriculum,
  getDecisionPlan,
  getTasks,
  updateTask,
  type DashboardData,
  type DecisionAction,
  type TasksData,
} from "../api";
import type { SectionId } from "../components/Layout";
import {
  allocatedMinutes,
  changeActionMinutes,
  composePlan,
  movePlanAction,
  type PlannerMode,
} from "../utils/planner";

const durations = [15, 30, 45, 60, 90];
const taskTypes = [
  ["assignment", "Entrega"],
  ["exam", "Examen"],
  ["reading", "Lectura"],
  ["project", "Proyecto"],
  ["presentation", "Presentación"],
  ["class_preparation", "Preparación de clase"],
  ["administrative", "Administrativa"],
  ["other", "Otra"],
] as const;
const acceptedExtensions = ".pdf,.docx,.pptx,.txt,.md";
type Scope = "active" | "overdue" | "today" | "upcoming" | "undated";
type CreateMode = "file" | "manual";
type FilePhase = "selecting" | "analyzing" | "preview" | "creating" | "error";
type TaskForm = {
  title: string;
  subject_id: string;
  task_type: string;
  priority: string;
  due_date: string;
  estimated_minutes: string;
  description: string;
  notes: string;
};

const emptyFileForm: TaskForm = {
  title: "",
  subject_id: "",
  task_type: "",
  priority: "",
  due_date: "",
  estimated_minutes: "",
  description: "",
  notes: "",
};
const manualForm: TaskForm = {
  ...emptyFileForm,
  task_type: "assignment",
  priority: "3",
};

function dueLabel(days: number | null) {
  if (days == null) return "Sin fecha";
  if (days < 0)
    return `Vencida hace ${Math.abs(days)} día${Math.abs(days) === 1 ? "" : "s"}`;
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
function decisionPriorityLabel(value: DecisionAction["priority"]) {
  return (
    { critical: "Crítica", high: "Alta", medium: "Media", low: "Baja" } as const
  )[value];
}

export default function TasksPage({
  onStartSession,
  focusedTaskId,
}: {
  onStartSession: () => void;
  focusedTaskId?: number | null;
}) {
  const [data, setData] = useState<TasksData | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [duration, setDuration] = useState(60);
  const [plannerMode, setPlannerMode] = useState<PlannerMode>("priority");
  const [planActions, setPlanActions] = useState<DecisionAction[]>([]);
  const [planError, setPlanError] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>("active");
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [mode, setMode] = useState<CreateMode>("file");
  const [phase, setPhase] = useState<FilePhase>("selecting");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileSubjectId, setFileSubjectId] = useState("");
  const [analysisMeta, setAnalysisMeta] = useState<{
    name: string;
    characterCount: number;
  } | null>(null);
  const [form, setForm] = useState<TaskForm>(emptyFileForm);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadTasks() {
    setLoading(true);
    setError(null);
    try {
      const [tasks, subjects] = await Promise.all([getTasks(), getDashboard()]);
      setData(tasks);
      setDashboard(subjects);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudieron cargar las tareas.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function changeDuration(minutes: number) {
    setDuration(minutes);
    setPlanning(true);
    setError(null);
    try {
      const next = await getDecisionPlan(minutes, 5);
      const ids = [
        ...new Set(
          next.actions.flatMap((action) =>
            action.subject_id == null ? [] : [action.subject_id],
          ),
        ),
      ];
      const curricula = (
        await Promise.allSettled(ids.map(getCurriculum))
      ).flatMap((result) =>
        result.status === "fulfilled" ? [result.value] : [],
      );
      setPlanActions(composePlan(next.actions, plannerMode, curricula));
      setPlanError(null);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo calcular el plan.",
      );
    } finally {
      setPlanning(false);
    }
  }

  function openCreate() {
    setShowCreate(true);
    setMode("file");
    setPhase("selecting");
    setSelectedFile(null);
    setFileSubjectId("");
    setAnalysisMeta(null);
    setForm(emptyFileForm);
    setFormError(null);
  }

  async function analyze() {
    if (!selectedFile) {
      setFormError("Selecciona un enunciado para analizar.");
      return;
    }
    setPhase("analyzing");
    setFormError(null);
    try {
      const result = await analyzeTaskFile(
        selectedFile,
        fileSubjectId ? Number(fileSubjectId) : null,
      );
      const proposal = result.proposal;
      const validType = taskTypes.some(
        ([value]) => value === proposal.task_type,
      );
      const requirements = Array.isArray(proposal.detected_requirements)
        ? proposal.detected_requirements.filter(
            (item) => typeof item === "string",
          )
        : [];
      const notes = [
        proposal.notes,
        requirements.length
          ? `Requisitos detectados:\n${requirements.map((item) => `• ${item}`).join("\n")}`
          : null,
      ]
        .filter(Boolean)
        .join("\n\n");
      setForm({
        title: proposal.title ?? "",
        subject_id:
          proposal.subject_id != null
            ? String(proposal.subject_id)
            : fileSubjectId,
        task_type: validType ? proposal.task_type! : "",
        priority:
          proposal.priority != null &&
          proposal.priority >= 1 &&
          proposal.priority <= 5
            ? String(proposal.priority)
            : "",
        due_date: proposal.due_date ?? "",
        estimated_minutes:
          proposal.estimated_minutes != null
            ? String(proposal.estimated_minutes)
            : "",
        description: proposal.description ?? "",
        notes,
      });
      setAnalysisMeta({
        name: result.file.name,
        characterCount: result.file.character_count,
      });
      setPhase("preview");
    } catch (caught) {
      setPhase("error");
      setFormError(
        caught instanceof Error
          ? caught.message
          : "No se pudo analizar el enunciado.",
      );
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) {
      setFormError("Escribe un título para la tarea.");
      return;
    }
    if (!form.task_type) {
      setFormError("Confirma el tipo de tarea.");
      return;
    }
    if (!form.priority) {
      setFormError("Confirma la prioridad.");
      return;
    }
    if (mode === "file" && !form.subject_id) {
      setFormError("Confirma a qué asignatura pertenece el enunciado.");
      return;
    }
    setSaving(true);
    setPhase("creating");
    setFormError(null);
    try {
      await createTask({
        title: form.title.trim(),
        subject_id: form.subject_id ? Number(form.subject_id) : null,
        task_type: form.task_type,
        priority: Number(form.priority),
        due_date: form.due_date || null,
        estimated_minutes: form.estimated_minutes
          ? Number(form.estimated_minutes)
          : null,
        description: form.description.trim() || null,
        notes: form.notes.trim() || null,
      });
      setShowCreate(false);
      setNotice("La tarea se ha creado y ya aparece en tu registro activo.");
      await loadTasks();
      window.setTimeout(() => setNotice(null), 3500);
    } catch (caught) {
      setPhase(mode === "file" ? "preview" : "selecting");
      setFormError(
        caught instanceof Error ? caught.message : "No se pudo crear la tarea.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function complete(taskId: number) {
    try {
      await updateTask(taskId, { status: "completed" });
      setNotice("Tarea completada.");
      await loadTasks();
      window.setTimeout(() => setNotice(null), 2500);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo completar la tarea.",
      );
    }
  }

  function removeFromCurrentSession(index: number) {
    setPlanActions((current) =>
      current.filter((_, actionIndex) => actionIndex !== index),
    );
    setPlanError(null);
  }

  useEffect(() => {
    void loadTasks();
  }, []);
  useEffect(() => {
    if (focusedTaskId == null || loading) return;
    window.setTimeout(() => document.getElementById(`task-${focusedTaskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
  }, [focusedTaskId, loading]);
  const tasks = useMemo(
    () =>
      (data?.tasks ?? []).filter(({ task }) =>
        scope === "overdue"
          ? task.is_overdue
          : scope === "today"
            ? task.days_until_due === 0
            : scope === "upcoming"
              ? task.days_until_due != null && task.days_until_due > 0
              : scope === "undated"
                ? task.due_date == null
                : true,
      ),
    [data, scope],
  );
  const counts = {
    overdue: data?.tasks.filter(({ task }) => task.is_overdue).length ?? 0,
    today:
      data?.tasks.filter(({ task }) => task.days_until_due === 0).length ?? 0,
    inProgress:
      data?.tasks.filter(({ task }) => task.status === "in_progress").length ??
      0,
  };

  if (loading && !data)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Tareas</p>
        <h1>Ordenando tu carga académica…</h1>
        <p>UniCore está leyendo fechas, progreso y prioridad.</p>
      </section>
    );
  if (error && !data)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Tareas</p>
        <h1>No se pudo cargar el trabajo pendiente.</h1>
        <p>{error}</p>
        <button className="uc-primary-action" onClick={() => void loadTasks()}>
          Reintentar <RefreshCw size={16} />
        </button>
      </section>
    );

  return (
    <div className="uc-page-shell uc-tasks-page">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">Ejecución académica</p>
          <h1>Tareas con contexto.</h1>
          <p className="uc-page-subtitle">
            Fechas, avance y prioridad real para separar lo urgente de lo que
            simplemente hace ruido.
          </p>
        </div>
        <div className="uc-page-actions">
          <button className="uc-primary-action" onClick={onStartSession}>
            <Play size={16} /> Empezar sesión
          </button>
          <button className="uc-new-subject" onClick={openCreate}>
            <Plus size={16} /> Nueva tarea
          </button>
          <div className="uc-date-chip">
            <CheckCircle2 size={16} />
            {data?.count ?? 0} activa{data?.count === 1 ? "" : "s"}
          </div>
        </div>
      </header>
      {notice && <div className="uc-inline-success">{notice}</div>}
      {error && <div className="uc-inline-error">{error}</div>}
      <section className="uc-task-summary">
        <div>
          <span>Vencidas</span>
          <strong className={counts.overdue ? "is-danger" : ""}>
            {counts.overdue}
          </strong>
          <small>requieren atención</small>
        </div>
        <div>
          <span>Para hoy</span>
          <strong>{counts.today}</strong>
          <small>con fecha actual</small>
        </div>
        <div>
          <span>En progreso</span>
          <strong>{counts.inProgress}</strong>
          <small>trabajo iniciado</small>
        </div>
      </section>

      {false && <section className="uc-planner-block">
        <div className="uc-planner-copy">
          <p className="uc-eyebrow">Plan de trabajo</p>
          <h2>Construye una sesión completa.</h2>
          <p>
            Parte del Decision Engine, agrupa repeticiones y conserva únicamente
            acciones académicas reales.
          </p>
          <div className="uc-duration-control" aria-label="Duración disponible">
            {durations.map((minutes) => (
              <button
                key={minutes}
                className={duration === minutes ? "is-active" : ""}
                onClick={() => void changeDuration(minutes)}
              >
                {minutes}
                <span>min</span>
              </button>
            ))}
          </div>
          <div className="uc-planner-mode">
            <button
              className={plannerMode === "priority" ? "is-active" : ""}
              onClick={() => {
                setPlannerMode("priority");
                setPlanActions(composePlan(planActions, "priority"));
              }}
            >
              Prioridad
            </button>
            <button
              className={plannerMode === "balanced" ? "is-active" : ""}
              onClick={() => {
                setPlannerMode("balanced");
                setPlanActions(composePlan(planActions, "balanced"));
              }}
            >
              Equilibrado
            </button>
          </div>
        </div>
        <div className="uc-planner-result">
          {planning ? (
            <div className="uc-empty-inline">Calculando el plan…</div>
          ) : planActions.length ? (
            <>
              {planActions.map((action, index) => (
                <article
                  className="uc-plan-row"
                  key={`${action.type}-${action.subject_id}-${action.source_id}-${index}`}
                >
                  <div className="uc-plan-order">
                    <button
                      disabled={index === 0}
                      onClick={() =>
                        setPlanActions(movePlanAction(planActions, index, -1))
                      }
                      aria-label="Subir actividad"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      disabled={index === planActions.length - 1}
                      onClick={() =>
                        setPlanActions(movePlanAction(planActions, index, 1))
                      }
                      aria-label="Bajar actividad"
                    >
                      <ArrowDown size={14} />
                    </button>
                  </div>
                  <div className="uc-plan-minutes">
                    <button
                      onClick={() => {
                        const result = changeActionMinutes(
                          planActions,
                          index,
                          -15,
                          duration,
                        );
                        setPlanActions(result.actions);
                        setPlanError(result.error);
                      }}
                      aria-label="Restar 15 minutos"
                    >
                      <Minus size={13} />
                    </button>
                    <strong>{action.allocated_minutes}</strong>
                    <span>min</span>
                    <button
                      onClick={() => {
                        const result = changeActionMinutes(
                          planActions,
                          index,
                          15,
                          duration,
                        );
                        setPlanActions(result.actions);
                        setPlanError(result.error);
                      }}
                      aria-label="Añadir 15 minutos"
                    >
                      <Plus size={13} />
                    </button>
                  </div>
                  <div className="uc-plan-action-copy">
                    <strong>{action.title}</strong>
                    <small>
                      {action.type === "task"
                        ? "Tarea activa"
                        : typeof action.metadata.unit_name === "string"
                          ? `${action.metadata.focus_topic_ids instanceof Array ? action.metadata.focus_topic_ids.length : ""} temas disponibles`
                          : "Repaso académico"}{" "}
                      · {action.subject_name ?? "UniCore"}
                    </small>
                    <p>{action.reasons.join(" ")}</p>
                  </div>
                  <div className="uc-plan-actions">
                    <button>Abrir</button>
                    <button
                      className="uc-plan-remove"
                      onClick={() => removeFromCurrentSession(index)}
                      aria-label={`Quitar ${action.title} de esta sesión`}
                      title="Quitar de esta sesión"
                    >
                      <X size={15} />
                    </button>
                  </div>
                </article>
              ))}
              {planError && (
                <div className="uc-inline-warning">{planError}</div>
              )}
              <footer>
                <div>
                  <strong>
                    {allocatedMinutes(planActions)} de {duration} minutos
                    asignados
                  </strong>
                  <span>
                    {Math.max(0, duration - allocatedMinutes(planActions))} min
                    disponibles.
                  </span>
                </div>
                <button
                  className="uc-primary-action"
                  onClick={() => undefined}
                >
                  <Play size={15} /> Iniciar bloque
                </button>
              </footer>
            </>
          ) : (
            <div className="uc-empty-inline">
              No hay acciones en esta sesión. Puedes volver a planificar para
              recuperarlas.
            </div>
          )}
        </div>
      </section>}

      <section className="uc-task-register">
        <div className="uc-task-register-head">
          <div>
            <p className="uc-eyebrow">Registro activo</p>
            <h2>Trabajo pendiente</h2>
          </div>
          <div className="uc-task-filters">
            <SlidersHorizontal size={14} />
            {(
              [
                ["active", "Todas"],
                ["overdue", "Vencidas"],
                ["today", "Hoy"],
                ["upcoming", "Próximas"],
                ["undated", "Sin fecha"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                className={scope === value ? "is-active" : ""}
                onClick={() => setScope(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {tasks.length === 0 ? (
          <div className="uc-task-empty">
            <strong>No hay tareas en esta vista.</strong>
            <span>
              {data?.count
                ? "Prueba otro filtro para revisar tu trabajo activo."
                : "Añade una tarea para empezar a planificar."}
            </span>
          </div>
        ) : (
          <div className="uc-task-list">
            {tasks.map(({ task }) => (
              <article
                id={`task-${task.id}`}
                className={`uc-task-row ${task.is_overdue ? "is-overdue" : ""} ${focusedTaskId === task.id ? "is-focused" : ""}`}
                key={task.id}
              >
                <div className="uc-task-priority">
                  <span>Prioridad</span>
                  <strong>{priorityLabel(task.priority)}</strong>
                </div>
                <div className="uc-task-main">
                  <div>
                    <strong>{task.title}</strong>
                    <span>
                      {task.subject_name ?? "Sin asignatura"} · {task.task_type}
                    </span>
                  </div>
                  {task.description && <p>{task.description}</p>}
                  <div className="uc-task-progress">
                    <div className="uc-progress-track">
                      <div
                        className="uc-progress-fill"
                        style={{ width: `${task.progress_percentage}%` }}
                      />
                    </div>
                    <span>{task.progress_percentage}%</span>
                  </div>
                </div>
                <div className="uc-task-meta">
                  <span className={task.is_overdue ? "is-danger" : ""}>
                    <CalendarDays size={14} />
                    {dueLabel(task.days_until_due)}
                  </span>
                  <span>
                    <Clock3 size={14} />
                    {task.remaining_minutes != null
                      ? `${task.remaining_minutes} min restantes`
                      : "Sin estimación"}
                  </span>
                  <button
                    className="uc-complete-task"
                    onClick={() => void complete(task.id)}
                  >
                    <Check size={13} /> Marcar completada
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {showCreate && (
        <div
          className="uc-form-backdrop"
          onMouseDown={() => !saving && setShowCreate(false)}
        >
          <form
            className="uc-form-modal uc-task-form uc-task-create-flow"
            onSubmit={submit}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="uc-eyebrow">Trabajo académico</p>
                <h2>Nueva tarea</h2>
              </div>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                aria-label="Cerrar formulario"
              >
                <X size={18} />
              </button>
            </header>
            <div className="uc-create-mode">
              <button
                type="button"
                className={mode === "file" ? "is-active" : ""}
                onClick={() => {
                  setMode("file");
                  setPhase("selecting");
                  setForm(emptyFileForm);
                  setFormError(null);
                }}
              >
                <Upload size={15} /> Subir enunciado
              </button>
              <button
                type="button"
                className={mode === "manual" ? "is-active" : ""}
                onClick={() => {
                  setMode("manual");
                  setPhase("selecting");
                  setForm(manualForm);
                  setFormError(null);
                }}
              >
                Introducir manualmente
              </button>
            </div>
            {mode === "file" && phase !== "preview" && phase !== "creating" ? (
              <div className="uc-file-step">
                <input
                  ref={fileInput}
                  className="sr-only"
                  type="file"
                  accept={acceptedExtensions}
                  onChange={(event) => {
                    setSelectedFile(event.target.files?.[0] ?? null);
                    setPhase("selecting");
                    setFormError(null);
                  }}
                />
                <button
                  type="button"
                  className="uc-file-drop"
                  onClick={() => fileInput.current?.click()}
                  disabled={phase === "analyzing"}
                >
                  <FileText size={25} />
                  <strong>
                    {selectedFile?.name ?? "Selecciona el enunciado"}
                  </strong>
                  <span>PDF, DOCX, PPTX, TXT o MD · máximo 8 MB</span>
                </button>
                <label>
                  Asignatura si ya la conoces
                  <span>Ayuda a resolver ambigüedades</span>
                  <select
                    value={fileSubjectId}
                    onChange={(event) => setFileSubjectId(event.target.value)}
                    disabled={phase === "analyzing"}
                  >
                    <option value="">Que UniCore intente detectarla</option>
                    {dashboard?.subjects.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.name}
                      </option>
                    ))}
                  </select>
                </label>
                {phase === "analyzing" && (
                  <div className="uc-analysis-state">
                    <i />
                    <div>
                      <strong>Analizando el enunciado…</strong>
                      <span>
                        Extrayendo texto y comprobando fechas, requisitos y
                        asignatura.
                      </span>
                    </div>
                  </div>
                )}
                {phase === "error" && formError && (
                  <p className="uc-form-error">{formError}</p>
                )}
                <button
                  type="button"
                  className="uc-primary-action"
                  onClick={() => void analyze()}
                  disabled={!selectedFile || phase === "analyzing"}
                >
                  {phase === "analyzing" ? "Analizando…" : "Analizar enunciado"}
                </button>
              </div>
            ) : (
              <>
                {mode === "file" && analysisMeta && (
                  <div className="uc-analysis-ready">
                    <CheckCircle2 size={17} />
                    <div>
                      <strong>Propuesta lista para revisar</strong>
                      <span>
                        {analysisMeta.name} ·{" "}
                        {analysisMeta.characterCount.toLocaleString("es-ES")}{" "}
                        caracteres extraídos
                      </span>
                    </div>
                  </div>
                )}
                <div className="uc-form-grid">
                  <label className="is-wide">
                    Título
                    <span>{form.title ? "Propuesto" : "No detectado"}</span>
                    <input
                      autoFocus
                      value={form.title}
                      onChange={(event) =>
                        setForm({ ...form, title: event.target.value })
                      }
                      placeholder="No detectado"
                    />
                  </label>
                  <label>
                    Asignatura
                    <span>
                      {form.subject_id
                        ? "Propuesta"
                        : "Confirma una asignatura"}
                    </span>
                    <select
                      value={form.subject_id}
                      onChange={(event) =>
                        setForm({ ...form, subject_id: event.target.value })
                      }
                    >
                      <option value="">No detectado</option>
                      {dashboard?.subjects.map((subject) => (
                        <option key={subject.id} value={subject.id}>
                          {subject.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tipo
                    <span>{form.task_type ? "Propuesto" : "No detectado"}</span>
                    <select
                      value={form.task_type}
                      onChange={(event) =>
                        setForm({ ...form, task_type: event.target.value })
                      }
                    >
                      <option value="">No detectado</option>
                      {taskTypes.map(([value, label]) => (
                        <option value={value} key={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Prioridad
                    <span>{form.priority ? "Propuesta" : "No detectado"}</span>
                    <select
                      value={form.priority}
                      onChange={(event) =>
                        setForm({ ...form, priority: event.target.value })
                      }
                    >
                      <option value="">No detectado</option>
                      {[1, 2, 3, 4, 5].map((value) => (
                        <option key={value} value={value}>
                          {value} · {priorityLabel(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Fecha límite
                    <span>{form.due_date ? "Propuesta" : "No detectado"}</span>
                    <input
                      type="date"
                      value={form.due_date}
                      onChange={(event) =>
                        setForm({ ...form, due_date: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Estimación
                    <span>
                      {form.estimated_minutes
                        ? "Minutos propuestos"
                        : "No detectado"}
                    </span>
                    <input
                      type="number"
                      min="1"
                      value={form.estimated_minutes}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          estimated_minutes: event.target.value,
                        })
                      }
                      placeholder="No detectado"
                    />
                  </label>
                  <label className="is-wide">
                    Descripción<span>Editable</span>
                    <textarea
                      rows={3}
                      value={form.description}
                      onChange={(event) =>
                        setForm({ ...form, description: event.target.value })
                      }
                      placeholder="No detectado"
                    />
                  </label>
                  <label className="is-wide">
                    Notas y requisitos<span>Editable</span>
                    <textarea
                      rows={4}
                      value={form.notes}
                      onChange={(event) =>
                        setForm({ ...form, notes: event.target.value })
                      }
                      placeholder="No detectado"
                    />
                  </label>
                </div>
                {formError && <p className="uc-form-error">{formError}</p>}
                <footer>
                  {mode === "file" && (
                    <button
                      type="button"
                      onClick={() => {
                        setPhase("selecting");
                        setFormError(null);
                      }}
                      disabled={saving}
                    >
                      Volver al archivo
                    </button>
                  )}
                  <button className="uc-primary-action" disabled={saving}>
                    {saving ? "Creando…" : "Crear tarea"}
                  </button>
                </footer>
              </>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
