import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronRight,
  FileText,
  Link2,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createStudySession,
  getCurriculum,
  getDashboard,
  getStudy,
  startExplanation,
  type AgentSource,
  type CurriculumData,
  type CurriculumStatus,
  type CurriculumSubtopic,
  type CurriculumTopic,
  type DashboardData,
  type StudyData,
  type TokenUsage,
} from "../api";
import AcademicMarkdown from "../components/AcademicMarkdown";
import TokenUsageNote from "../components/TokenUsageNote";

type StudyLaunchContext = {
  subjectId: number;
  subjectName: string;
  documentId?: number;
  topic?: string;
} | null;
type SelectedCurriculumItem = CurriculumTopic | CurriculumSubtopic;
type ActiveExplanation = {
  conversationId: string;
  item: SelectedCurriculumItem;
  content: string;
  sources: AgentSource[];
  usage?: TokenUsage;
  cacheHit?: boolean;
  startedAt: number;
};

const statusCopy: Record<CurriculumStatus, string> = {
  not_studied: "No estudiado",
  learning: "En aprendizaje",
  consolidating: "Consolidando",
  mastered: "Dominado",
};
const shortDate = (value: string) =>
  new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
  });

export default function StudyPage({
  launchContext,
  onConfigureSubject,
  onAskAgent,
}: {
  launchContext?: StudyLaunchContext;
  onConfigureSubject: (subjectId: number) => void;
  onAskAgent: (context: {
    subjectId: number;
    subjectName: string;
    topic: string;
    explanation: string;
    sources: AgentSource[];
  }) => void;
}) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [study, setStudy] = useState<StudyData | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(
    launchContext?.subjectId ?? null,
  );
  const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<SelectedCurriculumItem | null>(null);
  const [duration, setDuration] = useState(30);
  const [active, setActive] = useState<ActiveExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadSubject(id: number) {
    setSubjectId(id);
    setLoading(true);
    setError(null);
    setSelected(null);
    setActive(null);
    try {
      const [curriculumData, studyData] = await Promise.all([
        getCurriculum(id),
        getStudy(id),
      ]);
      setCurriculum(curriculumData);
      setStudy(studyData);
      setExpandedUnits(
        new Set(curriculumData.units.slice(0, 1).map((unit) => unit.id)),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo cargar el temario.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboard();
      setDashboard(data);
      const initial =
        data.subjects.find(
          (subject) => subject.id === (launchContext?.subjectId ?? subjectId),
        ) ?? data.subjects[0];
      if (initial) await loadSubject(initial.id);
      else setLoading(false);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No se pudo cargar Estudio.",
      );
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [launchContext?.subjectId]);

  async function beginExplanation() {
    if (subjectId == null || !selected || starting) return;
    if (!curriculum?.subject.academic_language_configured) {
      setError(
        "Confirma el idioma académico desde el detalle de la asignatura antes de estudiar.",
      );
      return;
    }
    setStarting(true);
    setError(null);
    try {
      const result = await startExplanation({
        subject_id: subjectId,
        curriculum_item_id: selected.id,
      });
      setActive({
        conversationId: result.conversation_id,
        item: selected,
        content: result.explanation,
        sources: result.sources,
        usage: result.usage,
        cacheHit: result.cache?.hit ?? false,
        startedAt: Date.now(),
      });
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo preparar la explicación.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function finishExplanation() {
    if (!active || subjectId == null) {
      setActive(null);
      return;
    }
    const minutes = Math.max(
      1,
      Math.ceil((Date.now() - active.startedAt) / 60_000),
    );
    try {
      await createStudySession({
        subject_id: subjectId,
        duration_minutes: minutes,
        activity_type: "explanation",
        topic: active.item.name,
        planned_minutes: duration,
        completed_plan: minutes >= duration,
        started_at: new Date(active.startedAt).toISOString(),
        completed_at: new Date().toISOString(),
      });
      setActive(null);
      const [curriculumData, studyData] = await Promise.all([
        getCurriculum(subjectId),
        getStudy(subjectId),
      ]);
      setCurriculum(curriculumData);
      setStudy(studyData);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo registrar la sesión.",
      );
    }
  }

  function toggleUnit(id: number) {
    setExpandedUnits((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const uniqueSources = useMemo(
    () =>
      selected?.sources.filter(
        (source, index, all) =>
          all.findIndex(
            (candidate) => candidate.document_id === source.document_id,
          ) === index,
      ) ?? [],
    [selected],
  );
  const languageReady =
    curriculum?.subject.academic_language_configured === true;
  const selectedUnit = curriculum?.units.find((unit) =>
    unit.topics.some(
      (topic) =>
        topic.id === selected?.id ||
        topic.subtopics.some((subtopic) => subtopic.id === selected?.id),
    ),
  );
  if (loading && !curriculum)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Estudio</p>
        <h1>Ordenando tu temario real…</h1>
        <p>Recuperando unidades, temas y fuentes persistidas.</p>
      </section>
    );
  if (error && !curriculum)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Estudio</p>
        <h1>No se pudo cargar el temario.</h1>
        <p>{error}</p>
        <button className="uc-primary-action" onClick={() => void load()}>
          Reintentar <RefreshCw size={16} />
        </button>
      </section>
    );
  if (!dashboard?.subjects.length)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Estudio</p>
        <h1>Aún no hay asignaturas.</h1>
        <p>Crea una asignatura y añade materiales para construir su temario.</p>
      </section>
    );

  if (active)
    return (
      <div className="uc-page-shell uc-live-study uc-curriculum-explanation">
        <header>
          <button
            className="uc-back-link"
            onClick={() => void finishExplanation()}
          >
            <ArrowLeft size={15} /> Finalizar sesión
          </button>
          <div>
            <p className="uc-eyebrow">
              Aprendizaje · {curriculum?.subject.academic_language}
            </p>
            <h1>{active.item.name}</h1>
            <p>
              {curriculum?.subject.name} · contexto restringido al{" "}
              {active.item.type === "subtopic" ? "subtema" : "tema"}
            </p>
          </div>
        </header>
        <div className="uc-tutor-layout">
          <section className="uc-tutor-thread">
            <article className="is-assistant">
              <span>UniCore Tutor</span>
              <AcademicMarkdown
                content={active.content}
                sources={active.sources}
              />
              <TokenUsageNote
                usage={active.usage}
                sources={active.sources.length}
              />
              <p className="uc-cache-note">
                {active.cacheHit
                  ? "Reutilizada desde la explicación guardada · 0 tokens"
                  : "Explicación guardada para reutilizarla mientras el material no cambie."}
              </p>
              <div className="uc-explanation-agent">
                <strong>¿Tienes alguna duda?</strong>
                <button
                  onClick={() =>
                    subjectId != null &&
                    onAskAgent({
                      subjectId,
                      subjectName: curriculum?.subject.name ?? "Asignatura",
                      topic: active.item.name,
                      explanation: active.content,
                      sources: active.sources,
                    })
                  }
                >
                  ✦ Preguntar a UniCore sobre este tema
                </button>
              </div>
            </article>
          </section>
          <aside className="uc-study-sources">
            <p className="uc-eyebrow">Fuentes utilizadas</p>
            {active.sources.map((source) => (
              <a
                href={`http://127.0.0.1:8766/api/documents/${source.document_id}/file`}
                target="_blank"
                rel="noreferrer"
                key={`${source.document_id}-${source.source_number}`}
              >
                <FileText size={14} />
                <span>
                  <strong>{source.document_title}</strong>
                  <small>{source.source_label ?? "Abrir material"}</small>
                </span>
              </a>
            ))}
            <small>
              El retrieval se limita a los chunks asociados al elemento
              curricular.
            </small>
          </aside>
        </div>
        {error && <div className="uc-inline-error">{error}</div>}
      </div>
    );

  return (
    <div className="uc-page-shell uc-curriculum-study">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">Aprendizaje · Curriculum Engine</p>
          <h1>Estudia desde tu temario.</h1>
          <p className="uc-page-subtitle">
            Unidades y temas extraídos de tus materiales, sin pedirte que
            reconstruyas manualmente el curso.
          </p>
        </div>
        <label className="uc-subject-select">
          <span>Asignatura</span>
          <select
            value={subjectId ?? ""}
            onChange={(event) => void loadSubject(Number(event.target.value))}
          >
            {dashboard.subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error && <div className="uc-inline-error">{error}</div>}
      {!languageReady && (
        <div className="uc-language-note">
          Idioma académico pendiente ·{" "}
          <button
            onClick={() => subjectId != null && onConfigureSubject(subjectId)}
          >
            Configurar
          </button>
        </div>
      )}
      {curriculum?.pending_document_count ? (
        <div className="uc-inline-warning">
          Hay {curriculum.pending_document_count} material(es) pendiente(s) de
          estructurar.
        </div>
      ) : null}
      {curriculum?.units.length ? (
        <div className="uc-curriculum-workspace">
          <section className="uc-curriculum-browser">
            <header>
              <p className="uc-eyebrow">Tu temario</p>
              <span>{curriculum.item_count} elementos persistidos</span>
            </header>
            {curriculum.units.map((unit) => {
              const open = expandedUnits.has(unit.id);
              return (
                <article className="uc-curriculum-unit" key={unit.id}>
                  <button
                    className="uc-curriculum-unit-head"
                    onClick={() => toggleUnit(unit.id)}
                  >
                    <span>
                      {open ? (
                        <ChevronDown size={16} />
                      ) : (
                        <ChevronRight size={16} />
                      )}
                    </span>
                    <div>
                      <strong>{unit.name}</strong>
                      <small>
                        {unit.topic_count} tema
                        {unit.topic_count === 1 ? "" : "s"}
                      </small>
                    </div>
                    <em>
                      {unit.worked_topic_count
                        ? `${unit.worked_topic_count} / ${unit.topic_count} trabajados`
                        : "Sin evidencia todavía"}
                    </em>
                  </button>
                  {open && (
                    <div className="uc-curriculum-topics">
                      {unit.topics.map((topic) => (
                        <div key={topic.id}>
                          <button
                            className={
                              selected?.id === topic.id ? "is-active" : ""
                            }
                            onClick={() => setSelected(topic)}
                          >
                            <span
                              className={`uc-curriculum-state is-${topic.status}`}
                            />{" "}
                            <strong>{topic.name}</strong>
                            <small>{statusCopy[topic.status]}</small>
                            <ChevronRight size={14} />
                          </button>
                          {topic.subtopics.length > 0 && (
                            <div>
                              {topic.subtopics.map((subtopic) => (
                                <button
                                  className={
                                    selected?.id === subtopic.id
                                      ? "is-active"
                                      : ""
                                  }
                                  key={subtopic.id}
                                  onClick={() => setSelected(subtopic)}
                                >
                                  <span>↳</span>
                                  <strong>{subtopic.name}</strong>
                                  <small>{statusCopy[subtopic.status]}</small>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </section>
          <aside className="uc-curriculum-detail">
            {selected ? (
              <>
                <header>
                  <p className="uc-eyebrow">
                    {selected.type === "subtopic" ? "Subtema" : "Tema"}
                  </p>
                  <h2>{selected.name}</h2>
                  <span
                    className={`uc-curriculum-status is-${selected.status}`}
                  >
                    {statusCopy[selected.status]}
                  </span>
                </header>
                {selected.type === "topic" && selected.subtopics.length > 0 && (
                  <section>
                    <h3>Subtemas</h3>
                    <div className="uc-subtopic-pills">
                      {selected.subtopics.map((subtopic) => (
                        <button
                          key={subtopic.id}
                          onClick={() => setSelected(subtopic)}
                        >
                          {subtopic.name}
                        </button>
                      ))}
                    </div>
                  </section>
                )}
                <section>
                  <h3>Fuentes</h3>
                  {uniqueSources.length ? (
                    <div className="uc-curriculum-sources">
                      {uniqueSources.map((source) => (
                        <a
                          key={source.document_id}
                          href={`http://127.0.0.1:8766/api/documents/${source.document_id}/file`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <FileText size={14} />
                          <span>
                            <strong>{source.title}</strong>
                            <small>
                              {source.source_label ??
                                source.file_type?.toUpperCase() ??
                                "Material"}
                            </small>
                          </span>
                        </a>
                      ))}
                    </div>
                  ) : (
                    <p className="uc-empty-inline">
                      No hay una fuente directa asociada.
                    </p>
                  )}
                </section>
                {selected.also_seen_in.length > 0 && (
                  <section>
                    <h3>También lo has visto en</h3>
                    {selected.also_seen_in.map((item) => (
                      <p
                        className="uc-cross-subject"
                        key={`${item.subject_id}-${item.concept_name}`}
                      >
                        <Link2 size={13} /> {item.subject_name} ·{" "}
                        {item.concept_name}
                      </p>
                    ))}
                  </section>
                )}
                <label className="uc-study-duration">
                  <span>Objetivo de tiempo</span>
                  <select
                    value={duration}
                    onChange={(event) =>
                      setDuration(Number(event.target.value))
                    }
                  >
                    {[15, 30, 45, 60, 90].map((value) => (
                      <option key={value} value={value}>
                        {value} minutos
                      </option>
                    ))}
                  </select>
                </label>
                <div className="uc-study-actions">
                  <button
                    className="uc-primary-action"
                    disabled={starting || !selected.sources.length}
                    onClick={() =>
                      languageReady
                        ? void beginExplanation()
                        : subjectId != null && onConfigureSubject(subjectId)
                    }
                  >
                    <BookOpen size={15} />{" "}
                    {starting ? "Preparando…" : "Ver explicación"}
                  </button>
                </div>
              </>
            ) : (
              <div className="uc-curriculum-detail-empty">
                <BookOpen size={24} />
                <h2>Selecciona un tema.</h2>
                <p>
                  Verás sus subtemas, fuentes y estado antes de iniciar una
                  explicación.
                </p>
              </div>
            )}
          </aside>
        </div>
      ) : (
        <section className="uc-curriculum-empty">
          <BookOpen size={25} />
          <h2>No se ha detectado un temario todavía.</h2>
          <p>
            Añade un material con títulos, unidades, capítulos o secciones.
            UniCore conservará la estructura detectada y no inventará temas.
          </p>
        </section>
      )}
      <section className="uc-study-history">
        <div className="uc-section-heading">
          <div>
            <p className="uc-eyebrow">Actividad real</p>
            <h2>Aprendizaje reciente</h2>
          </div>
        </div>
        {study?.recent_study_sessions.length ? (
          <div className="uc-study-session-list">
            {study.recent_study_sessions
              .filter((session) => session.activity_type === "explanation")
              .slice(0, 5)
              .map((session) => (
                <article key={session.id}>
                  <time>{shortDate(session.session_date)}</time>
                  <div>
                    <strong>{session.topic ?? "Explicación"}</strong>
                    <span>{session.duration_minutes} min</span>
                  </div>
                  <div className="uc-session-ratings">
                    <span>
                      Foco <strong>{session.focus_rating ?? "—"}</strong>
                    </span>
                    <span>
                      Dificultad{" "}
                      <strong>{session.difficulty_rating ?? "—"}</strong>
                    </span>
                  </div>
                </article>
              ))}
          </div>
        ) : (
          <div className="uc-task-empty">
            <strong>No hay explicaciones registradas.</strong>
            <span>Al finalizar una sesión aparecerá aquí.</span>
          </div>
        )}
      </section>
    </div>
  );
}
