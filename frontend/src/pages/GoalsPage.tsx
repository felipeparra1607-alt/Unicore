import { Check, RefreshCw, Save, Target, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  getDashboard,
  setGradeGoal,
  type DashboardData,
  type DashboardSubject,
} from "../api";
import {
  getGoalPreferences,
  saveGoalPreferences,
  weeklyMinutesFor,
  type GoalPreferences,
} from "../utils/goalPreferences";

type GoalSubject = { subject: DashboardSubject; detail: DashboardData };
const clamp = (value: number) => Math.max(0, Math.min(100, value));

export default function GoalsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [subjects, setSubjects] = useState<GoalSubject[]>([]);
  const [preferences, setPreferences] =
    useState<GoalPreferences>(getGoalPreferences);
  const [draft, setDraft] = useState<GoalPreferences>(getGoalPreferences);
  const [panelOpen, setPanelOpen] = useState(false);
  const [editingSubject, setEditingSubject] = useState<number | null>(null);
  const [gradeInput, setGradeInput] = useState("");
  const [weeklyInput, setWeeklyInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load(background = false) {
    if (!background) setLoading(true);
    setError(null);
    try {
      const global = await getDashboard();
      const details = await Promise.all(
        global.subjects.map(async (subject) => ({
          subject,
          detail: await getDashboard(subject.id),
        })),
      );
      setDashboard(global);
      setSubjects(details);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudieron cargar los objetivos.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  function saveGeneral() {
    if (draft.dailyMinutes < 10 || draft.studyDays < 1 || draft.studyDays > 7) {
      setError(
        "Indica al menos 10 minutos al día y entre 1 y 7 días por semana.",
      );
      return;
    }
    saveGoalPreferences(draft);
    setPreferences(draft);
    setNotice("Objetivo semanal guardado.");
    setError(null);
  }

  async function saveSubject(subjectId: number) {
    const target = Number(gradeInput);
    const weekly = weeklyInput.trim() ? Number(weeklyInput) : undefined;
    if (!Number.isFinite(target) || target < 0 || target > 10) {
      setError("La nota objetivo debe estar entre 0 y 10.");
      return;
    }
    if (weekly != null && (!Number.isFinite(weekly) || weekly < 0)) {
      setError("El tiempo semanal debe ser positivo o quedar vacío.");
      return;
    }
    setSaving(true);
    setError(null);
    const next = {
      ...draft,
      subjects: {
        ...draft.subjects,
        [String(subjectId)]: { weeklyMinutes: weekly },
      },
    };
    try {
      await setGradeGoal(subjectId, target);
      saveGoalPreferences(next);
      setDraft(next);
      setPreferences(next);
      await load(true);
      setEditingSubject(null);
      setNotice("Cambios guardados correctamente.");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo guardar el objetivo.",
      );
    } finally {
      setSaving(false);
    }
  }

  const averages = useMemo(() => {
    const current = subjects.flatMap(({ subject }) =>
      subject.grade.current_grade_out_of_10 == null
        ? []
        : [subject.grade.current_grade_out_of_10],
    );
    const target = subjects.flatMap(({ subject }) =>
      subject.grade.target_grade == null ? [] : [subject.grade.target_grade],
    );
    return {
      current: current.length
        ? current.reduce((a, b) => a + b, 0) / current.length
        : null,
      target: target.length
        ? target.reduce((a, b) => a + b, 0) / target.length
        : null,
    };
  }, [subjects]);
  const weeklyTarget = weeklyMinutesFor(preferences);
  const draftWeeklyTarget = weeklyMinutesFor(draft);
  const studied = dashboard?.metrics.study_minutes_last_7_days ?? 0;
  const gap =
    averages.current != null && averages.target != null
      ? averages.target - averages.current
      : null;

  if (loading)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Objetivos</p>
        <h1>Preparando tu progreso…</h1>
      </section>
    );
  if (error && !dashboard)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Objetivos</p>
        <h1>No se pudieron cargar tus objetivos.</h1>
        <p>{error}</p>
        <button className="uc-primary-action" onClick={() => void load()}>
          Reintentar <RefreshCw size={16} />
        </button>
      </section>
    );

  return (
    <div className="uc-page-shell uc-goals-page-v2">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">Este semestre</p>
          <h1>Objetivos académicos.</h1>
          <p className="uc-page-subtitle">
            Nota y tiempo de estudio medidos con actividad real.
          </p>
        </div>
        <button
          className="uc-primary-action"
          onClick={() => setPanelOpen(true)}
        >
          <Target size={15} /> Editar por asignatura
        </button>
      </header>
      {notice && <div className="uc-inline-success">{notice}</div>}
      {error && <div className="uc-inline-error">{error}</div>}
      <section className="uc-goal-performance">
        <header>
          <p className="uc-eyebrow">Nota media</p>
          <button className="uc-text-action" onClick={() => setPanelOpen(true)}>
            Editar
          </button>
        </header>
        <div className="uc-goal-grade-strip">
          <div>
            <span>Actual</span>
            <strong>{averages.current?.toFixed(1) ?? "—"}</strong>
          </div>
          <div>
            <span>Objetivo</span>
            <strong>{averages.target?.toFixed(1) ?? "—"}</strong>
          </div>
          <div>
            <span>Diferencia</span>
            <strong className={gap != null && gap > 0 ? "is-gap" : ""}>
              {gap == null ? "—" : `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}`}
            </strong>
          </div>
        </div>
      </section>
      <section className="uc-goal-consistency uc-goal-time-v3">
        <div>
          <p className="uc-eyebrow">Tiempo semanal</p>
          <h2>
            {studied} / {weeklyTarget} <small>min</small>
          </h2>
          <p>
            {preferences.dailyMinutes} min/día × {preferences.studyDays}{" "}
            días/semana = {weeklyTarget} min/semana
          </p>
          <div className="uc-progress-track">
            <div
              className="uc-progress-fill blue"
              style={{
                width: `${clamp((studied / Math.max(1, weeklyTarget)) * 100)}%`,
              }}
            />
          </div>
        </div>
        <div className="uc-goal-fields">
          <label>
            Minutos al día
            <input
              type="number"
              min="10"
              value={draft.dailyMinutes}
              onChange={(event) =>
                setDraft({ ...draft, dailyMinutes: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Días por semana
            <input
              type="number"
              min="1"
              max="7"
              value={draft.studyDays}
              onChange={(event) =>
                setDraft({ ...draft, studyDays: Number(event.target.value) })
              }
            />
          </label>
          <div>
            <span>Calculado</span>
            <strong>{draftWeeklyTarget} min/semana</strong>
          </div>
        </div>
        <button className="uc-goal-save-general" onClick={saveGeneral}>
          <Save size={14} /> Guardar tiempo
        </button>
      </section>
      {panelOpen && (
        <div className="uc-goal-drawer-layer">
          <button
            className="uc-overlay"
            aria-label="Cerrar"
            onClick={() => setPanelOpen(false)}
          />
          <aside className="uc-goal-drawer uc-goal-drawer-v2">
            <header>
              <div>
                <p className="uc-eyebrow">Objetivos por asignatura</p>
                <h2>Nota y dedicación</h2>
              </div>
              <button onClick={() => setPanelOpen(false)} aria-label="Cerrar">
                <X size={18} />
              </button>
            </header>
            <div className="uc-goal-subject-list">
              {subjects.map(({ subject }) => {
                const local = draft.subjects[String(subject.id)];
                const editing = editingSubject === subject.id;
                return (
                  <article key={subject.id}>
                    <header>
                      <div>
                        <strong>
                          {subject.name || "Asignatura sin nombre"}
                        </strong>
                        <small>
                          {subject.grade.evaluated_weight_percentage.toFixed(0)}
                          % evaluado
                        </small>
                      </div>
                      {!editing && (
                        <button
                          className="uc-text-action"
                          onClick={() => {
                            setEditingSubject(subject.id);
                            setGradeInput(
                              String(subject.grade.target_grade ?? ""),
                            );
                            setWeeklyInput(
                              local?.weeklyMinutes == null
                                ? ""
                                : String(local.weeklyMinutes),
                            );
                          }}
                        >
                          Editar
                        </button>
                      )}
                    </header>
                    <div className="uc-subject-goal-values">
                      <span>
                        Actual{" "}
                        <strong>
                          {subject.grade.current_grade_out_of_10?.toFixed(1) ??
                            "—"}
                        </strong>
                      </span>
                      <span>
                        Objetivo{" "}
                        <strong>
                          {subject.grade.target_grade?.toFixed(1) ?? "—"}
                        </strong>
                      </span>
                      <span>
                        Tiempo semanal{" "}
                        <strong>
                          {local?.weeklyMinutes != null
                            ? `${local.weeklyMinutes} min`
                            : "Opcional"}
                        </strong>
                      </span>
                    </div>
                    {editing && (
                      <div className="uc-subject-goal-editor">
                        <label>
                          Nota objetivo
                          <input
                            type="number"
                            min="0"
                            max="10"
                            step="0.1"
                            value={gradeInput}
                            onChange={(event) =>
                              setGradeInput(event.target.value)
                            }
                          />
                        </label>
                        <label>
                          Tiempo semanal opcional
                          <input
                            type="number"
                            min="0"
                            value={weeklyInput}
                            onChange={(event) =>
                              setWeeklyInput(event.target.value)
                            }
                            placeholder="Sin objetivo"
                          />
                        </label>
                        <button
                          className="uc-primary-action"
                          disabled={saving}
                          onClick={() => void saveSubject(subject.id)}
                        >
                          {saving ? "Guardando…" : "Guardar cambios"}{" "}
                          <Check size={13} />
                        </button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
