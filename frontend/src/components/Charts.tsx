import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData, DashboardSubject } from "../api";
import Card from "./Card";

const weekdayNames: Record<string, string> = {
  Mon: "L",
  Tue: "M",
  Wed: "X",
  Thu: "J",
  Fri: "V",
  Sat: "S",
  Sun: "D",
};

const tooltipStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-strong)",
  borderRadius: 6,
  color: "var(--text-primary)",
  boxShadow: "var(--shadow-tooltip)",
};

export function StudyMinutesChart({
  activity,
  totalMinutes,
}: {
  activity: DashboardData["daily_activity"];
  totalMinutes: number;
}) {
  const data = activity.map((item) => ({
    day: weekdayNames[item.weekday] ?? item.weekday,
    minutes: item.minutes,
  }));

  return (
    <Card
      eyebrow="Constancia"
      title="Minutos estudiados"
      className="uc-chart-panel uc-chart-panel-wide"
      action={<span className="uc-chart-range">7 días</span>}
    >
      <div className="uc-chart-summary">
        <strong>{totalMinutes} min</strong>
        <span>registrados en los últimos 7 días</span>
      </div>
      <div className="uc-chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
            <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--chart-cursor)" }} />
            <Bar dataKey="minutes" fill="var(--accent)" radius={[3, 3, 0, 0]} maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function ReadinessChart({ boss }: { boss: DashboardData["next_boss"] }) {
  if (!boss) {
    return (
      <Card eyebrow="Evaluaciones" title="Preparación estimada" className="uc-chart-panel">
        <p className="uc-metric-explainer">
          Combina progreso y evidencias académicas para estimar tu preparación. No es una nota predicha.
        </p>
        <div className="uc-readiness-row">
          <strong>—</strong>
          <span>No hay Boss Battle activo</span>
        </div>
      </Card>
    );
  }

  const chartData = [
    { label: "Actual", value: boss.readiness_percentage },
    { label: "Objetivo", value: boss.target_score_percentage },
  ];

  return (
    <Card
      eyebrow={boss.assessment_title ? `Examen · ${boss.assessment_title}` : "Próxima evaluación"}
      title="Preparación estimada"
      className="uc-chart-panel"
    >
      <p className="uc-metric-explainer">
        Combina tu progreso, actividad reciente y evidencias de aprendizaje para estimar qué tan preparado llegas al próximo examen. No es una nota predicha.
      </p>
      <div className="uc-readiness-row">
        <strong>{boss.readiness_percentage.toFixed(1)}%</strong>
        <span>Objetivo {boss.target_score_percentage.toFixed(0)}%</span>
      </div>
      <div className="uc-chart-canvas compact-chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="readinessFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-blue)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--chart-blue)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
            <YAxis hide domain={[0, 100]} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey="value" stroke="var(--chart-blue)" fill="url(#readinessFill)" strokeWidth={2.4} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function PerformanceChart({
  subject,
  readiness,
}: {
  subject: DashboardSubject | null;
  readiness: number | null;
}) {
  const data = [
    ...(subject?.grade.current_grade_out_of_10 != null
      ? [{ name: "Nota actual", value: subject.grade.current_grade_out_of_10 * 10 }]
      : []),
    ...(readiness != null ? [{ name: "Preparación", value: readiness }] : []),
    ...(subject?.quiz_average_percentage != null
      ? [{ name: "Quiz", value: subject.quiz_average_percentage }]
      : []),
  ];

  return (
    <Card eyebrow={subject?.name ?? "Asignatura"} title="Señales de rendimiento" className="uc-chart-panel">
      <p className="uc-metric-explainer">
        Compara indicadores distintos de la asignatura en una escala común: tu nota actual, la preparación estimada y el rendimiento medio en quizzes.
      </p>
      {data.length === 0 ? (
        <div className="uc-readiness-row">
          <strong>—</strong>
          <span>Aún no hay suficientes datos</span>
        </div>
      ) : (
        <div className="uc-chart-canvas compact-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid horizontal={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
              <XAxis type="number" hide domain={[0, 100]} />
              <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={92} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="var(--chart-neutral)" radius={[0, 3, 3, 0]} barSize={13} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

export function GradeTrendChart({ subject }: { subject: DashboardSubject | null }) {
  const grade = subject?.grade;
  const data = [
    ...(grade?.current_grade_out_of_10 != null ? [{ label: "Actual", value: grade.current_grade_out_of_10 }] : []),
    ...(grade?.target_grade != null ? [{ label: "Objetivo", value: grade.target_grade }] : []),
    ...(grade?.required_average_on_remaining != null ? [{ label: "Necesaria", value: grade.required_average_on_remaining }] : []),
  ];

  return (
    <Card eyebrow="Situación de nota" title="Objetivo académico" className="uc-chart-panel">
      <div className="uc-readiness-row">
        <strong>{grade?.current_grade_out_of_10 != null ? grade.current_grade_out_of_10.toFixed(1) : "—"}</strong>
        <span>{grade?.target_grade != null ? `objetivo ${grade.target_grade.toFixed(1)}` : "sin objetivo registrado"}</span>
      </div>
      {data.length > 0 ? (
        <div className="uc-chart-canvas compact-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
              <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
              <YAxis domain={[0, 10]} axisLine={false} tickLine={false} tick={{ fill: "var(--text-faint)", fontSize: 10 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="var(--accent)" radius={[3, 3, 0, 0]} maxBarSize={38} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </Card>
  );
}
