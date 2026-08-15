import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CalendarDays, RefreshCw } from "lucide-react";
import {
  getAssessments,
  getDashboard,
  getTasks,
  type Assessment,
  type DashboardData,
  type TasksData,
} from "../api";
import AssessmentCalendar from "./AssessmentCalendar";
import AIUsagePanel from "./AIUsagePanel";
import Card from "./Card";
import {
  GradeTrendChart,
  PerformanceChart,
  ReadinessChart,
  StudyMinutesChart,
} from "./Charts";

const weekdayNames = [
  "domingo",
  "lunes",
  "martes",
  "miércoles",
  "jueves",
  "viernes",
  "sábado",
];
const monthNames = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

function formatToday() {
  const now = new Date();
  const weekday = weekdayNames[now.getDay()];
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)} · ${now.getDate()} de ${monthNames[now.getMonth()]}`;
}

function daysLabel(days: number | null | undefined) {
  if (days == null) return "Sin evaluación próxima";
  if (days < 0) return `Vencida hace ${Math.abs(days)} día(s)`;
  if (days === 0) return "Hoy";
  if (days === 1) return "Mañana";
  return `${days} días`;
}

function heatIntensity(minutes: number, maximum: number) {
  if (minutes <= 0 || maximum <= 0) return 0;
  const ratio = minutes / maximum;
  if (ratio >= 0.75) return 3;
  if (ratio >= 0.35) return 2;
  return 1;
}

function weekdayLetter(value: string) {
  return (
    (
      {
        Mon: "L",
        Tue: "M",
        Wed: "X",
        Thu: "J",
        Fri: "V",
        Sat: "S",
        Sun: "D",
      } as Record<string, string>
    )[value] ?? value
  );
}

export default function Dashboard({
  onOpenSubjects,
  onOpenTasks,
}: {
  onOpenSubjects: () => void;
  onOpenTasks: () => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [tasks, setTasks] = useState<TasksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [assessmentsLoading, setAssessmentsLoading] = useState(false);

  async function loadDashboard() {
    setLoading(true);
    setError(null);
    try {
      const [dashboard, activeTasks] = await Promise.all([
        getDashboard(),
        getTasks(),
      ]);
      setData(dashboard);
      setTasks(activeTasks);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No se pudo cargar UniCore.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const openCalendar = async () => {
    setCalendarOpen(true);
    if (assessments.length) return;
    setAssessmentsLoading(true);
    try {
      const response = await getAssessments();
      setAssessments(response.assessments);
    } finally {
      setAssessmentsLoading(false);
    }
  };

  const mainSubject = data?.subjects[0] ?? null;
  const readiness = data?.next_boss?.readiness_percentage ?? null;
  const activity = data?.daily_activity ?? [];
  const maxActivity = Math.max(0, ...activity.map((item) => item.minutes));
  const currentGrade = mainSubject?.grade.current_grade_out_of_10 ?? null;
  const quizAverage = data?.metrics.quiz_average_percentage ?? null;
  const readinessGap =
    readiness != null && data?.next_boss
      ? Math.max(0, data.next_boss.target_score_percentage - readiness)
      : null;
  const subjectRows = useMemo(() => data?.subjects ?? [], [data]);

  if (loading) {
    return (
      <div className="uc-dashboard uc-page-shell">
        <section className="uc-priority-block">
          <p className="uc-eyebrow">UniCore</p>
          <h2>Cargando tu estado académico…</h2>
          <p>
            Estamos leyendo tus datos locales y calculando las prioridades
            actuales.
          </p>
        </section>
      </div>
    );
  }

  if (error || !data || !tasks) {
    return (
      <div className="uc-dashboard uc-page-shell">
        <section className="uc-priority-block">
          <p className="uc-eyebrow">No se pudo conectar</p>
          <h2>El frontend no encuentra la API local de UniCore.</h2>
          <p>{error ?? "Comprueba que la API está ejecutándose."}</p>
          <button
            className="uc-primary-action"
            onClick={() => void loadDashboard()}
          >
            Reintentar <RefreshCw size={17} />
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="uc-dashboard uc-page-shell">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">{formatToday()}</p>
          <h1>Tu semana académica, en una sola vista.</h1>
          <p className="uc-page-subtitle">
            Prioridades, preparación y progreso real. UniCore calcula el estado
            a partir de tus datos académicos locales.
          </p>
        </div>
        <button
          className="uc-date-chip uc-button-chip"
          onClick={() => void openCalendar()}
          aria-haspopup="dialog"
          aria-expanded={calendarOpen}
        >
          <CalendarDays size={16} />
          {data.next_assessment
            ? `${daysLabel(data.next_assessment.days_remaining)} para ${data.next_assessment.title}`
            : "Sin evaluación próxima"}
        </button>
      </header>

      <section className="uc-home-tasks">
        <header>
          <div>
            <p className="uc-eyebrow">Tareas pendientes</p>
            <h2>Trabajo activo</h2>
          </div>
          <button className="uc-text-action" onClick={onOpenTasks}>
            Ver todas <ArrowRight size={15} />
          </button>
        </header>
        {tasks.tasks.length ? (
          <div>
            {tasks.tasks.slice(0, 5).map(({ task }) => (
              <article key={task.id}>
                <div>
                  <strong>{task.title}</strong>
                  <span>
                    {task.subject_name ?? "Sin asignatura"}
                    {task.due_date
                      ? ` · ${new Date(`${task.due_date}T00:00:00`).toLocaleDateString("es-ES", { day: "numeric", month: "short" })}`
                      : ""}{" "}
                    · prioridad {task.priority}
                  </span>
                </div>
                <button onClick={onOpenTasks}>Abrir</button>
              </article>
            ))}
          </div>
        ) : (
          <p className="uc-empty-inline">No hay tareas activas.</p>
        )}
      </section>

      <section className="uc-kpis" aria-label="Indicadores académicos">
        <div className="uc-kpi">
          <span>Nota actual</span>
          <strong>
            {currentGrade != null ? currentGrade.toFixed(1) : "—"}
          </strong>
          <small>
            {mainSubject?.grade.target_grade != null
              ? `objetivo ${mainSubject.grade.target_grade.toFixed(1)}`
              : "sin objetivo registrado"}
          </small>
        </div>
        <div className="uc-kpi">
          <span>Preparación</span>
          <strong>
            {readiness != null ? `${readiness.toFixed(1)}%` : "—"}
          </strong>
          <small>
            {readinessGap != null
              ? `${readinessGap.toFixed(1)} pts hasta objetivo`
              : "sin Boss Battle activo"}
          </small>
        </div>
        <div className="uc-kpi">
          <span>Estudio registrado</span>
          <strong>{data.metrics.study_minutes_last_7_days} min</strong>
          <small>{data.metrics.study_session_count} sesiones totales</small>
        </div>
        <div className="uc-kpi">
          <span>Quiz medio</span>
          <strong>
            {quizAverage != null ? `${quizAverage.toFixed(0)}%` : "—"}
          </strong>
          <small>{data.metrics.quiz_attempt_count} intento(s)</small>
        </div>
      </section>

      <section className="uc-dashboard-grid uc-dashboard-grid-charts">
        <StudyMinutesChart
          activity={data.daily_activity}
          totalMinutes={data.metrics.study_minutes_last_7_days}
        />
        <ReadinessChart boss={data.next_boss} />
      </section>

      <AIUsagePanel />

      <section className="uc-dashboard-grid uc-dashboard-grid-middle">
        <Card title="Actividad semanal" className="uc-week-goals">
          <div className="uc-activity-strip">
            <div>
              <span>Actividad</span>
              <strong>Últimos 7 días</strong>
            </div>
            <div className="uc-heat-row">
              {activity.map((item) => (
                <div key={item.date} className="uc-heat-cell-wrap">
                  <span
                    className={`uc-heat-cell heat-${heatIntensity(item.minutes, maxActivity)}`}
                    title={`${item.date}: ${item.minutes} min`}
                  />
                  <small>{weekdayLetter(item.weekday)}</small>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </section>

      <section className="uc-dashboard-grid uc-dashboard-grid-bottom">
        <PerformanceChart subject={mainSubject} readiness={readiness} />
        <GradeTrendChart subject={mainSubject} />
      </section>

      <section className="uc-subject-section">
        <div className="uc-section-heading">
          <div>
            <p className="uc-eyebrow">Asignaturas</p>
            <h2>Estado académico</h2>
          </div>
          <button className="uc-text-action" onClick={onOpenSubjects}>
            Ver todas <ArrowRight size={15} />
          </button>
        </div>

        <div className="uc-subject-table">
          <div className="uc-subject-table-head">
            <span>Asignatura</span>
            <span>Nota</span>
            <span>Quiz</span>
            <span>Próximo examen</span>
            <span>Estado</span>
          </div>
          {subjectRows.length === 0 ? (
            <div className="uc-subject-row">
              <strong>No hay asignaturas registradas</strong>
            </div>
          ) : (
            subjectRows.map((subject) => (
              <div className="uc-subject-row" key={subject.id}>
                <strong>{subject.name}</strong>
                <span className="uc-grade-cell">
                  {subject.grade.current_grade_out_of_10 != null
                    ? subject.grade.current_grade_out_of_10.toFixed(1)
                    : "—"}
                </span>
                <div className="uc-readiness-cell">
                  <div className="uc-progress-track table-track">
                    <div
                      className="uc-progress-fill blue"
                      style={{
                        width: `${subject.quiz_average_percentage ?? 0}%`,
                      }}
                    />
                  </div>
                  <span>
                    {subject.quiz_average_percentage != null
                      ? `${subject.quiz_average_percentage.toFixed(0)}%`
                      : "—"}
                  </span>
                </div>
                <span>
                  {subject.next_assessment?.date
                    ? new Date(
                        `${subject.next_assessment.date}T00:00:00`,
                      ).toLocaleDateString("es-ES", {
                        day: "2-digit",
                        month: "short",
                      })
                    : "—"}
                </span>
                <span className="uc-state-pill">
                  {subject.pending_task_count > 0
                    ? `${subject.pending_task_count} pendiente(s)`
                    : "Al día"}
                </span>
              </div>
            ))
          )}
        </div>
      </section>
      {calendarOpen && (
        <AssessmentCalendar
          assessments={assessments}
          loading={assessmentsLoading}
          onClose={() => setCalendarOpen(false)}
        />
      )}
    </div>
  );
}
