import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarDays,
  Clock3,
  Flame,
  RefreshCw,
  Target,
  Trophy,
} from "lucide-react";
import {
  getDashboard,
  getDecisionPlan,
  type DashboardData,
  type DecisionPlan,
} from "../api";
import Card from "./Card";
import {
  GradeTrendChart,
  PerformanceChart,
  ReadinessChart,
  StudyMinutesChart,
} from "./Charts";

const weekdayNames = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const monthNames = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

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
  return ({ Mon: "L", Tue: "M", Wed: "X", Thu: "J", Fri: "V", Sat: "S", Sun: "D" } as Record<string, string>)[value] ?? value;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [plan, setPlan] = useState<DecisionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    setLoading(true);
    setError(null);
    try {
      const [dashboard, decisionPlan] = await Promise.all([
        getDashboard(),
        getDecisionPlan(60, 3),
      ]);
      setData(dashboard);
      setPlan(decisionPlan);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo cargar UniCore.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const mainSubject = data?.subjects[0] ?? null;
  const readiness = data?.next_boss?.readiness_percentage ?? null;
  const topAction = plan?.actions[0] ?? null;
  const nextActions = plan?.actions.slice(1, 3) ?? [];
  const activity = data?.daily_activity ?? [];
  const maxActivity = Math.max(0, ...activity.map((item) => item.minutes));
  const currentGrade = mainSubject?.grade.current_grade_out_of_10 ?? null;
  const quizAverage = data?.metrics.quiz_average_percentage ?? null;
  const readinessGap = readiness != null && data?.next_boss
    ? Math.max(0, data.next_boss.target_score_percentage - readiness)
    : null;
  const subjectRows = useMemo(() => data?.subjects ?? [], [data]);

  if (loading) {
    return (
      <div className="uc-dashboard uc-page-shell">
        <section className="uc-priority-block">
          <p className="uc-eyebrow">UniCore</p>
          <h2>Cargando tu estado académico…</h2>
          <p>Estamos leyendo tus datos locales y calculando las prioridades actuales.</p>
        </section>
      </div>
    );
  }

  if (error || !data || !plan) {
    return (
      <div className="uc-dashboard uc-page-shell">
        <section className="uc-priority-block">
          <p className="uc-eyebrow">No se pudo conectar</p>
          <h2>El frontend no encuentra la API local de UniCore.</h2>
          <p>{error ?? "Comprueba que la API está ejecutándose."}</p>
          <button className="uc-primary-action" onClick={() => void loadDashboard()}>
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
            Prioridades, preparación y progreso real. UniCore calcula el estado a partir de tus datos académicos locales.
          </p>
        </div>
        <div className="uc-date-chip">
          <CalendarDays size={16} />
          {data.next_assessment
            ? `${daysLabel(data.next_assessment.days_remaining)} para ${data.next_assessment.title}`
            : "Sin evaluación próxima"}
        </div>
      </header>

      <section className="uc-dashboard-grid uc-dashboard-grid-top">
        <article className="uc-priority-block">
          <div className="uc-priority-topline">
            <div>
              <p className="uc-eyebrow">Prioridad ahora</p>
              <span className="uc-priority-badge">
                {topAction ? `${topAction.priority} · score ${topAction.score.toFixed(0)}/100` : "Sin prioridad urgente"}
              </span>
            </div>
            <span className="uc-priority-score">01</span>
          </div>

          <div className="uc-priority-content">
            <div>
              <h2>{topAction?.title ?? "No hay una prioridad académica urgente detectada."}</h2>
              <p>{topAction?.reasons?.join(" ") ?? "Puedes usar este tiempo para repasar, organizar materiales o adelantar trabajo."}</p>
            </div>
            {topAction ? (
              <button className="uc-primary-action">
                Empezar bloque de {topAction.allocated_minutes} min <ArrowRight size={17} />
              </button>
            ) : null}
          </div>

          <div className="uc-priority-progress">
            <div className="uc-priority-progress-meta">
              <span>Prioridad calculada por Decision Engine</span>
              <strong>{topAction ? `${topAction.score.toFixed(0)}%` : "0%"}</strong>
            </div>
            <div className="uc-progress-track">
              <div className="uc-progress-fill" style={{ width: `${topAction?.score ?? 0}%` }} />
            </div>
          </div>
        </article>

        <aside className="uc-level-block">
          <div className="uc-level-kicker"><Trophy size={18} /> Progreso UniCore</div>
          <div className="uc-level-number">{data.hero.level}</div>
          <div className="uc-level-copy">
            <span>Nivel académico</span>
            <strong>{data.hero.total_xp} XP</strong>
          </div>
          <div className="uc-progress-track compact">
            <div className="uc-progress-fill" style={{ width: `${data.hero.level_progress_percentage}%` }} />
          </div>
          <p>{data.hero.xp_until_next_level} XP para el nivel {data.hero.level + 1}</p>
          <div className="uc-streak-inline"><Flame size={15} /><span>Racha actual</span><strong>{data.hero.current_streak} día(s)</strong></div>
        </aside>
      </section>

      <section className="uc-kpis" aria-label="Indicadores académicos">
        <div className="uc-kpi">
          <span>Nota actual</span>
          <strong>{currentGrade != null ? currentGrade.toFixed(1) : "—"}</strong>
          <small>{mainSubject?.grade.target_grade != null ? `objetivo ${mainSubject.grade.target_grade.toFixed(1)}` : "sin objetivo registrado"}</small>
        </div>
        <div className="uc-kpi">
          <span>Preparación</span>
          <strong>{readiness != null ? `${readiness.toFixed(1)}%` : "—"}</strong>
          <small>{readinessGap != null ? `${readinessGap.toFixed(1)} pts hasta objetivo` : "sin Boss Battle activo"}</small>
        </div>
        <div className="uc-kpi">
          <span>Estudio registrado</span>
          <strong>{data.metrics.study_minutes_last_7_days} min</strong>
          <small>{data.metrics.study_session_count} sesiones totales</small>
        </div>
        <div className="uc-kpi">
          <span>Quiz medio</span>
          <strong>{quizAverage != null ? `${quizAverage.toFixed(0)}%` : "—"}</strong>
          <small>{data.metrics.quiz_attempt_count} intento(s)</small>
        </div>
      </section>

      <section className="uc-dashboard-grid uc-dashboard-grid-charts">
        <StudyMinutesChart activity={data.daily_activity} totalMinutes={data.metrics.study_minutes_last_7_days} />
        <ReadinessChart boss={data.next_boss} />
      </section>

      <section className="uc-dashboard-grid uc-dashboard-grid-middle">
        <Card eyebrow="Plan inmediato" title="Después de esta prioridad" className="uc-next-actions">
          <div className="uc-action-list">
            {nextActions.length === 0 ? (
              <div className="uc-action-row muted">
                <div className="uc-action-index">—</div>
                <div className="uc-action-main">
                  <strong>No hay más acciones urgentes</strong>
                  <span>El Decision Engine no necesita llenar tu tiempo con trabajo artificial.</span>
                </div>
                <Target size={16} />
              </div>
            ) : nextActions.map((action, index) => (
              <div className={`uc-action-row ${index > 0 ? "muted" : ""}`} key={`${action.type}-${action.source_id}`}>
                <div className="uc-action-index">{String(index + 2).padStart(2, "0")}</div>
                <div className="uc-action-main">
                  <strong>{action.title}</strong>
                  <span>{action.subject_name ?? "UniCore"} · {action.allocated_minutes} min · score {action.score.toFixed(0)}</span>
                </div>
                <Clock3 size={16} />
              </div>
            ))}
          </div>
        </Card>

        <Card eyebrow="Gamificación" title="Misiones de hoy" className="uc-week-goals">
          {data.missions.items.length === 0 ? (
            <div className="uc-action-row muted">
              <div className="uc-action-main">
                <strong>No hay misiones generadas para hoy</strong>
                <span>Cuando existan, su progreso y recompensa XP aparecerán aquí.</span>
              </div>
            </div>
          ) : data.missions.items.slice(0, 3).map((mission) => {
            const percentage = mission.target_value > 0
              ? Math.min(100, (mission.current_value / mission.target_value) * 100)
              : 0;
            return (
              <div key={mission.id}>
                <div className="uc-goal-row">
                  <div><BookOpenCheck size={16} /><span>{mission.title}</span></div>
                  <strong>{mission.current_value} / {mission.target_value} · +{mission.reward_xp} XP</strong>
                </div>
                <div className="uc-progress-track subtle">
                  <div className="uc-progress-fill" style={{ width: `${percentage}%` }} />
                </div>
              </div>
            );
          })}

          <div className="uc-activity-strip">
            <div><span>Actividad</span><strong>Últimos 7 días</strong></div>
            <div className="uc-heat-row">
              {activity.map((item) => (
                <div key={item.date} className="uc-heat-cell-wrap">
                  <span className={`uc-heat-cell heat-${heatIntensity(item.minutes, maxActivity)}`} title={`${item.date}: ${item.minutes} min`} />
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
          <div><p className="uc-eyebrow">Asignaturas</p><h2>Estado académico</h2></div>
          <button className="uc-text-action">Ver todas <ArrowRight size={15} /></button>
        </div>

        <div className="uc-subject-table">
          <div className="uc-subject-table-head">
            <span>Asignatura</span><span>Nota</span><span>Quiz</span><span>Próximo examen</span><span>Estado</span>
          </div>
          {subjectRows.length === 0 ? (
            <div className="uc-subject-row"><strong>No hay asignaturas registradas</strong></div>
          ) : subjectRows.map((subject) => (
            <div className="uc-subject-row" key={subject.id}>
              <strong>{subject.name}</strong>
              <span className="uc-grade-cell">{subject.grade.current_grade_out_of_10 != null ? subject.grade.current_grade_out_of_10.toFixed(1) : "—"}</span>
              <div className="uc-readiness-cell">
                <div className="uc-progress-track table-track"><div className="uc-progress-fill blue" style={{ width: `${subject.quiz_average_percentage ?? 0}%` }} /></div>
                <span>{subject.quiz_average_percentage != null ? `${subject.quiz_average_percentage.toFixed(0)}%` : "—"}</span>
              </div>
              <span>{subject.next_assessment?.date ? new Date(`${subject.next_assessment.date}T00:00:00`).toLocaleDateString("es-ES", { day: "2-digit", month: "short" }) : "—"}</span>
              <span className="uc-state-pill">{subject.pending_task_count > 0 ? `${subject.pending_task_count} pendiente(s)` : "Al día"}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
