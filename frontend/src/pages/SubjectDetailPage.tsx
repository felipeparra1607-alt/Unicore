import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  RefreshCw,
  ShieldAlert,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  getAssessments,
  getDashboard,
  getDecisionPlan,
  getSubjectProfessor,
  getTasks,
  type AcademicTask,
  type Assessment,
  type DashboardData,
  type DecisionAction,
  type DecisionPlan,
  type ProfessorData,
} from "../api";
import SubjectAcademicCalendar from "../components/SubjectAcademicCalendar";
import MaterialLibrary from "../components/MaterialLibrary";
import ProfessorAssignmentPanel from "../components/ProfessorAssignmentPanel";
import { ReadinessChart, StudyMinutesChart } from "../components/Charts";
import Card from "../components/Card";
import type { SectionId } from "../components/Layout";

function formatDate(value: string | null | undefined) {
  return value
    ? new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", {
        day: "numeric",
        month: "long",
      })
    : "Sin fecha programada";
}
function percent(value: number | null | undefined) {
  return value == null ? "—" : `${value.toFixed(0)}%`;
}
export default function SubjectDetailPage({
  subjectId,
  onBack,
  onNavigate,
  onStartStudy,
}: {
  subjectId: number;
  onBack: () => void;
  onNavigate: (section: SectionId) => void;
  onStartStudy: (subjectName: string) => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [plan, setPlan] = useState<DecisionPlan | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [tasks, setTasks] = useState<AcademicTask[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [professor, setProfessor] = useState<ProfessorData | null>(null);
  const [professorError, setProfessorError] = useState<string | null>(null);
  const [professorOpen, setProfessorOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const calendar = useRef<HTMLElement>(null);
  async function load() {
    setLoading(true);
    setError(null);
    setProfessorError(null);
    setCalendarLoading(true);
    try {
      const [dashboard, decision, assessmentData, taskData] = await Promise.all(
        [
          getDashboard(subjectId),
          getDecisionPlan(60, 3, subjectId),
          getAssessments(),
          getTasks(subjectId),
        ],
      );
      setData(dashboard);
      setPlan(decision);
      setAssessments(
        assessmentData.assessments.filter(
          (item) => item.subject_id === subjectId,
        ),
      );
      setTasks(taskData.tasks.map((item) => item.task));
      try {
        setProfessor(await getSubjectProfessor(subjectId));
      } catch (caught) {
        setProfessor(null);
        setProfessorError(
          caught instanceof Error
            ? caught.message
            : "No se pudo cargar el contexto del profesor.",
        );
      }
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo cargar la asignatura.",
      );
    } finally {
      setLoading(false);
      setCalendarLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [subjectId]);
  const openAction = (action: DecisionAction) => {
    if (action.type === "assessment") {
      calendar.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    onNavigate(
      action.type === "task"
        ? "tasks"
        : action.type === "knowledge"
          ? "knowledge"
          : "study",
    );
  };
  if (loading)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Asignatura</p>
        <h1>Cargando el detalle académico…</h1>
        <p>
          Calculando nota, preparación y recomendaciones de esta asignatura.
        </p>
      </section>
    );
  if (error || !data)
    return (
      <section className="uc-page-shell uc-state-page">
        <button className="uc-back-link" onClick={onBack}>
          <ArrowLeft size={16} /> Todas las asignaturas
        </button>
        <p className="uc-eyebrow">Asignatura</p>
        <h1>No se pudo cargar el detalle.</h1>
        <p>{error ?? "No se recibieron datos académicos."}</p>
        <button className="uc-primary-action" onClick={() => void load()}>
          Reintentar <RefreshCw size={16} />
        </button>
      </section>
    );
  const subject = data.subjects[0];
  if (!subject)
    return (
      <section className="uc-page-shell uc-state-page">
        <button className="uc-back-link" onClick={onBack}>
          <ArrowLeft size={16} /> Todas las asignaturas
        </button>
        <p className="uc-eyebrow">Asignatura</p>
        <h1>Esta asignatura ya no está disponible.</h1>
        <p>Vuelve a la lista para consultar el estado académico actualizado.</p>
      </section>
    );
  const grade = subject.grade;
  const risk = data.academic_risk;
  const actions = plan?.actions ?? [];
  return (
    <div className="uc-page-shell uc-subject-detail">
      <button className="uc-back-link" onClick={onBack}>
        <ArrowLeft size={16} /> Todas las asignaturas
      </button>
      <header className="uc-page-intro uc-subject-detail-intro">
        <div>
          <p className="uc-eyebrow">Asignatura · estado individual</p>
          <h1>{subject.name}</h1>
          <p className="uc-page-subtitle">
            Lectura de rendimiento, actividad y prioridades calculada
            exclusivamente con tu información académica registrada.
          </p>
        </div>
        <div className="uc-subject-header-actions">
          <button className="uc-language-chip" onClick={() => setProfessorOpen(true)}>
            Idioma · {professor?.subject.academic_language ?? "Sin configurar"}
          </button>
          <button
            className="uc-primary-action"
            onClick={() => onStartStudy(subject.name)}
          >
            <BookOpen size={15} /> Estudiar esta asignatura
          </button>
          <button
            className="uc-date-chip uc-button-chip"
            onClick={() =>
              calendar.current?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              })
            }
          >
            <CalendarDays size={16} />
            {data.next_assessment
              ? `${formatDate(data.next_assessment.date)} · ${data.next_assessment.title}`
              : "Ver calendario académico"}
          </button>
        </div>
      </header>
      <section className="uc-subject-hero-grid uc-subject-grade-only">
        <article className="uc-subject-grade-block">
          <p className="uc-eyebrow">Situación de nota</p>
          <div className="uc-subject-grade-main">
            <strong>
              {grade.current_grade_out_of_10 != null
                ? grade.current_grade_out_of_10.toFixed(1)
                : "—"}
            </strong>
            <span>sobre 10</span>
          </div>
          <div className="uc-subject-grade-meta">
            <span>
              Objetivo{" "}
              <strong>
                {grade.target_grade != null
                  ? grade.target_grade.toFixed(1)
                  : "—"}
              </strong>
            </span>
            <span>
              Evaluado{" "}
              <strong>{grade.evaluated_weight_percentage.toFixed(0)}%</strong>
            </span>
          </div>
          <div className="uc-progress-track">
            <div
              className="uc-progress-fill blue"
              style={{
                width: `${Math.min(100, grade.evaluated_weight_percentage)}%`,
              }}
            />
          </div>
          <p>
            {grade.required_average_on_remaining != null
              ? `Necesitas una media de ${grade.required_average_on_remaining.toFixed(1)} en lo restante para alcanzar tu objetivo.`
              : "No hay suficiente información para calcular la media necesaria."}
          </p>
        </article>
      </section>
      <section className="uc-kpis uc-subject-kpis">
        <div className="uc-kpi">
          <span>Estudio</span>
          <strong>{data.metrics.study_minutes_last_7_days} min</strong>
          <small>últimos 7 días</small>
        </div>
        <div className="uc-kpi">
          <span>Quiz medio</span>
          <strong>{percent(data.metrics.quiz_average_percentage)}</strong>
          <small>{data.metrics.quiz_attempt_count} intento(s)</small>
        </div>
        <div className="uc-kpi">
          <span>Tareas activas</span>
          <strong>{data.metrics.pending_task_count}</strong>
          <small>{data.metrics.overdue_task_count} vencida(s)</small>
        </div>
        <div className="uc-kpi">
          <span>Repasos</span>
          <strong>{data.metrics.due_review_count}</strong>
          <small>pendientes hoy</small>
        </div>
      </section>
      <section className="uc-dashboard-grid uc-dashboard-grid-charts">
        <StudyMinutesChart
          activity={data.daily_activity}
          totalMinutes={data.metrics.study_minutes_last_7_days}
        />
        <ReadinessChart boss={data.next_boss} />
      </section>
      <section className="uc-subject-detail-grid">
        <Card title="Próximas acciones" className="uc-subject-actions">
          <div className="uc-action-list">
            {actions.length ? (
              actions.map((action, index) => (
                <button
                  className="uc-action-row uc-action-button"
                  key={`${action.type}-${action.source_id}`}
                  onClick={() => openAction(action)}
                >
                  <div className="uc-action-index">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div className="uc-action-main">
                    <strong>{action.title}</strong>
                    <span>
                      {action.allocated_minutes} min · prioridad{" "}
                      {action.priority} · {action.reasons.join(" ")}
                    </span>
                  </div>
                  <ArrowRight size={16} />
                </button>
              ))
            ) : (
              <div className="uc-empty-inline">
                No hay recomendaciones prioritarias para los próximos 60
                minutos.
              </div>
            )}
          </div>
        </Card>
        <Card
          eyebrow="Riesgo académico"
          title="Señal actual"
          className="uc-risk-panel"
        >
          {risk ? (
            <>
              <div className="uc-risk-score">
                <ShieldAlert size={18} />
                <strong>{risk.risk_level ?? "Sin clasificar"}</strong>
                {risk.risk_score != null && (
                  <span>{risk.risk_score.toFixed(0)}/100</span>
                )}
              </div>
              <p>
                {risk.summary ??
                  "El riesgo se calcula con las evidencias académicas disponibles."}
              </p>
              {risk.reasons?.length ? (
                <ul>
                  {risk.reasons.slice(0, 3).map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <div className="uc-empty-inline">
              Aún no hay una señal de riesgo disponible para esta asignatura.
            </div>
          )}
        </Card>
      </section>
      <section className="uc-subject-context-compact">
        <button onClick={() => setProfessorOpen(true)}>
          <UserRound size={18} />
          <span>
            <small>Profesor</small>
            <strong>
              {professor?.professors[0]?.name ?? "Sin profesor asignado"}
            </strong>
            <em>
              {(professor?.preferences.length ?? 0) +
                (professor?.rubric_criteria.length ?? 0)}{" "}
              criterios registrados
            </em>
          </span>
          <ArrowRight size={16} />
        </button>
      </section>
      {professorError && (
        <div className="uc-inline-error">{professorError}</div>
      )}
      {professorOpen && (
        <div className="uc-professor-detail-layer">
          <button
            className="uc-overlay"
            aria-label="Cerrar detalle del profesor"
            onClick={() => setProfessorOpen(false)}
          />
          <aside>
            <header>
              <div>
                <p className="uc-eyebrow">Profesor</p>
                <h2>
                  {professor?.professors[0]?.name ?? "Configuración académica"}
                </h2>
              </div>
              <button onClick={() => setProfessorOpen(false)}>Cerrar</button>
            </header>
            {professor?.preferences.length ? (
              <section>
                <h3>Qué valora</h3>
                {professor.preferences.map((item) => (
                  <article key={item.id}>
                    <strong>{item.preference}</strong>
                    {item.source_reference && (
                      <small>{item.source_reference}</small>
                    )}
                  </article>
                ))}
              </section>
            ) : null}
            {professor?.rubric_criteria.length ? (
              <section>
                <h3>Criterios</h3>
                {professor.rubric_criteria.map((item) => (
                  <article key={item.id}>
                    <strong>{item.title}</strong>
                    {item.description && <p>{item.description}</p>}
                    {item.notes && <small>{item.notes}</small>}
                  </article>
                ))}
              </section>
            ) : null}
            <ProfessorAssignmentPanel
              subjectId={subjectId}
              current={professor}
              onChanged={async () => {
                setProfessor(await getSubjectProfessor(subjectId));
              }}
            />
          </aside>
        </div>
      )}
      <section className="uc-subject-analytics">
        <div className="uc-section-heading">
          <div>
            <p className="uc-eyebrow">Analítica reciente</p>
            <h2>Indicadores de las últimas dos semanas</h2>
          </div>
        </div>
        {data.analytics ? (
          <div className="uc-analytics-strip">
            <div>
              <span>Días activos</span>
              <strong>{data.analytics.current.active_days}</strong>
            </div>
            <div>
              <span>Foco medio</span>
              <strong>
                {data.analytics.current.average_focus != null
                  ? `${data.analytics.current.average_focus.toFixed(1)}/5`
                  : "—"}
              </strong>
              <small>Media de foco valorada de 1 a 5.</small>
            </div>
            <div>
              <span>Cumplimiento del plan</span>
              <strong>
                {percent(data.analytics.current.plan_completion_percentage)}
              </strong>
            </div>
            <div>
              <span>Índice de estudio</span>
              <strong>
                {percent(data.analytics.current.study_efficiency_index)}
              </strong>
              <small>Combina foco, quizzes y planificación.</small>
            </div>
          </div>
        ) : (
          <div className="uc-empty-inline">
            No hay analítica suficiente para este periodo.
          </div>
        )}
      </section>
      <section ref={calendar} className="uc-calendar-anchor">
        <SubjectAcademicCalendar
          assessments={assessments}
          tasks={tasks}
          loading={calendarLoading}
        />
      </section>
      <MaterialLibrary subjectId={subjectId} />
    </div>
  );
}
