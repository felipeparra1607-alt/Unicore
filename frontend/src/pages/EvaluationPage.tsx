import {
  ArrowLeft,
  Check,
  Layers3,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createStudySession,
  decideFlashcardDraft,
  evaluateFlashcardAnswer,
  getCurriculum,
  getDashboard,
  getLeitner,
  moveFlashcard,
  rateFlashcard,
  startFlashcards,
  type CurriculumData,
  type CurriculumSubtopic,
  type CurriculumTopic,
  type CurriculumUnit,
  type DashboardData,
  type Flashcard,
  type FlashcardDraft,
  type LeitnerData,
  type TokenUsage,
  type WrittenEvaluation,
} from "../api";
import TokenUsageNote from "../components/TokenUsageNote";

type EvaluationView = "select" | "flashcards" | "quiz";
type FlashcardView = "practice" | "leitner";
type AnswerMode = "mental" | "written" | "mixed";
type CognitiveLevel =
  | "recall"
  | "understanding"
  | "application"
  | "analysis"
  | "mixed";
type CurriculumTarget = CurriculumTopic | CurriculumSubtopic;

const levelCopy: Record<CognitiveLevel, string> = {
  recall: "Recall",
  understanding: "Understanding",
  application: "Application",
  analysis: "Analysis",
  mixed: "Mixed",
};
const answerModeCopy: Record<AnswerMode, string> = {
  mental: "Mental",
  written: "Escrita",
  mixed: "Mixto",
};

export default function EvaluationPage({ onConfigureSubject }: { onConfigureSubject: (subjectId: number) => void }) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [leitner, setLeitner] = useState<LeitnerData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [unitId, setUnitId] = useState<number | null>(null);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [subtopicId, setSubtopicId] = useState<number | null>(null);
  const [view, setView] = useState<EvaluationView>("select");
  const [flashcardView, setFlashcardView] = useState<FlashcardView>("practice");
  const [level, setLevel] = useState<CognitiveLevel>("mixed");
  const [answerMode, setAnswerMode] = useState<AnswerMode>("mental");
  const [cardCount, setCardCount] = useState(8);
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<FlashcardDraft[]>([]);
  const [draftIndex, setDraftIndex] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [cardIndex, setCardIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [writtenAnswer, setWrittenAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<WrittenEvaluation | null>(null);
  const [evaluationUsage, setEvaluationUsage] = useState<TokenUsage>();
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [ratingCounts, setRatingCounts] = useState({
    difficult: 0,
    successful: 0,
  });
  const [selectedBox, setSelectedBox] = useState(1);
  const [completed, setCompleted] = useState<{
    minutes: number;
    cards: number;
  } | null>(null);

  const units = curriculum?.units ?? [];
  const selectedUnit = units.find((unit) => unit.id === unitId) ?? null;
  const selectedTopic =
    selectedUnit?.topics.find((topic) => topic.id === topicId) ?? null;
  const selectedSubtopic =
    selectedTopic?.subtopics.find((subtopic) => subtopic.id === subtopicId) ??
    null;
  const target: CurriculumTarget | null = selectedSubtopic ?? selectedTopic;
  const languageReady =
    curriculum?.subject.academic_language_configured === true;
  const academicLanguageLabel = languageReady
    ? curriculum?.subject.academic_language
    : "Idioma académico pendiente";

  function selectDefaults(data: CurriculumData) {
    const unit = data.units[0] ?? null;
    const topic = unit?.topics[0] ?? null;
    setUnitId(unit?.id ?? null);
    setTopicId(topic?.id ?? null);
    setSubtopicId(null);
  }

  async function loadSubject(id: number) {
    setSubjectId(id);
    setLoading(true);
    setError(null);
    try {
      const [curriculumData, boxes] = await Promise.all([
        getCurriculum(id),
        getLeitner(id),
      ]);
      setCurriculum(curriculumData);
      setLeitner(boxes);
      selectDefaults(curriculumData);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo cargar Evaluación.",
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
      if (data.subjects[0]) await loadSubject(data.subjects[0].id);
      else setLoading(false);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo cargar Evaluación.",
      );
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function beginFlashcards() {
    if (subjectId == null || !target || starting) return;
    if (!curriculum?.subject.academic_language_configured) {
      setError(
        "Confirma el idioma académico desde el detalle de la asignatura antes de generar flashcards.",
      );
      return;
    }
    setStarting(true);
    setError(null);
    setDrafts([]);
    setCards([]);
    setCompleted(null);
    try {
      const result = await startFlashcards({
        subject_id: subjectId,
        curriculum_item_id: target.id,
        topic: target.name,
        item_count: cardCount,
        cognitive_level: level,
        answer_mode: answerMode,
      });
      if (result.drafts?.length) {
        setDrafts(result.drafts);
        setDraftIndex(0);
        setEvaluationUsage(result.usage);
      } else startCardSession(result.cards);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudieron preparar las flashcards.",
      );
    } finally {
      setStarting(false);
    }
  }

  function startCardSession(nextCards: Flashcard[]) {
    if (!nextCards.length) {
      setError("No aceptaste ninguna tarjeta para esta sesión.");
      return;
    }
    setCards(nextCards);
    setDrafts([]);
    setCardIndex(0);
    setRevealed(false);
    setWrittenAnswer("");
    setEvaluation(null);
    setRatingCounts({ difficult: 0, successful: 0 });
    setStartedAt(Date.now());
  }

  async function decideDraft(accept: boolean) {
    const draft = drafts[draftIndex];
    if (!draft || starting) return;
    setStarting(true);
    setError(null);
    try {
      const result = await decideFlashcardDraft(
        draft.id,
        accept,
        accept ? undefined : rejectionReason || undefined,
      );
      const accepted = result.card ? [...cards, result.card] : cards;
      setCards(accepted);
      setRejectionReason("");
      if (draftIndex === drafts.length - 1) startCardSession(accepted);
      else setDraftIndex((value) => value + 1);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo procesar la tarjeta.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function finishSession(counts = ratingCounts) {
    if (subjectId == null || startedAt == null || !target) {
      setCards([]);
      return;
    }
    const minutes = Math.max(1, Math.ceil((Date.now() - startedAt) / 60_000));
    try {
      await createStudySession({
        subject_id: subjectId,
        duration_minutes: minutes,
        activity_type: "flashcards",
        topic: target.name,
        planned_minutes: duration,
        completed_plan: minutes >= duration,
        started_at: new Date(startedAt).toISOString(),
        completed_at: new Date().toISOString(),
      });
      setCompleted({ minutes, cards: counts.difficult + counts.successful });
      setCards([]);
      setStartedAt(null);
      setLeitner(await getLeitner(subjectId));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo registrar la sesión.",
      );
    }
  }

  async function submitCardRating(nextRating: "difficult" | "good" | "easy") {
    const card = cards[cardIndex];
    if (!card || !revealed || starting) return;
    setStarting(true);
    setError(null);
    try {
      await rateFlashcard(card.id, nextRating);
      const nextCounts = {
        difficult:
          ratingCounts.difficult + (nextRating === "difficult" ? 1 : 0),
        successful:
          ratingCounts.successful + (nextRating === "difficult" ? 0 : 1),
      };
      setRatingCounts(nextCounts);
      if (cardIndex === cards.length - 1) await finishSession(nextCounts);
      else {
        setCardIndex((value) => value + 1);
        setRevealed(false);
        setWrittenAnswer("");
        setEvaluation(null);
      }
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo guardar la valoración.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function evaluateWritten() {
    const card = cards[cardIndex];
    if (!card || !writtenAnswer.trim() || starting) return;
    setStarting(true);
    setError(null);
    try {
      const result = await evaluateFlashcardAnswer(card.id, writtenAnswer);
      setEvaluation(result.evaluation);
      setEvaluationUsage(result.usage);
      setRevealed(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo evaluar la respuesta.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function advanceWritten() {
    if (!evaluation) return;
    const nextCounts = {
      difficult:
        ratingCounts.difficult + (evaluation.overall_score < 70 ? 1 : 0),
      successful:
        ratingCounts.successful + (evaluation.overall_score >= 70 ? 1 : 0),
    };
    setRatingCounts(nextCounts);
    if (cardIndex === cards.length - 1) await finishSession(nextCounts);
    else {
      setCardIndex((value) => value + 1);
      setRevealed(false);
      setWrittenAnswer("");
      setEvaluation(null);
    }
  }

  async function changeBox(
    card: Flashcard,
    targetBox?: number,
    earlier = false,
  ) {
    setStarting(true);
    setError(null);
    try {
      await moveFlashcard(card.id, targetBox, earlier);
      if (subjectId != null) setLeitner(await getLeitner(subjectId));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo mover la tarjeta.",
      );
    } finally {
      setStarting(false);
    }
  }

  const currentCard = cards[cardIndex];
  const writtenTurn =
    answerMode === "written" || (answerMode === "mixed" && cardIndex % 2 === 1);
  const boxCards =
    leitner?.cards.filter((item) => item.leitner_box === selectedBox) ?? [];
  const dueCount =
    leitner?.boxes.reduce((sum, box) => sum + box.due_count, 0) ?? 0;
  const masteryCount = useMemo(
    () =>
      leitner?.boxes
        .filter((box) => box.box >= 4)
        .reduce((sum, box) => sum + box.count, 0) ?? 0,
    [leitner],
  );

  if (loading && !dashboard)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Evaluación</p>
        <h1>Preparando tu práctica…</h1>
      </section>
    );
  if (error && !dashboard)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Evaluación</p>
        <h1>No se pudo cargar Evaluación.</h1>
        <p>{error}</p>
        <button className="uc-primary-action" onClick={() => void load()}>
          Reintentar <RefreshCw size={15} />
        </button>
      </section>
    );
  if (!dashboard?.subjects.length)
    return (
      <section className="uc-page-shell uc-state-page">
        <p className="uc-eyebrow">Evaluación</p>
        <h1>Aún no hay asignaturas.</h1>
        <p>
          Crea una asignatura y añade materiales antes de evaluar conocimiento.
        </p>
      </section>
    );

  if (drafts.length) {
    const draft = drafts[draftIndex];
    return (
      <div className="uc-page-shell uc-flashcard-review">
        <button
          className="uc-back-link"
          onClick={() => {
            setDrafts([]);
            setCards([]);
          }}
        >
          <ArrowLeft size={15} /> Volver a configuración
        </button>
        <header>
          <p className="uc-eyebrow">
            Control de calidad · {draftIndex + 1}/{drafts.length}
          </p>
          <h1>Acepta solo las tarjetas que merecen entrar en tu memoria.</h1>
          <TokenUsageNote
            usage={evaluationUsage}
            sources={draft.sources.length}
          />
        </header>
        <article className="uc-flashcard-draft">
          {draft.probable_duplicate && (
            <span className="uc-duplicate-warning">Posible duplicado</span>
          )}
          <span>
            {levelCopy[draft.cognitive_level as CognitiveLevel] ??
              draft.cognitive_level}
          </span>
          <h2>{draft.question}</h2>
          <div>
            <span>Respuesta propuesta</span>
            <p>{draft.correct_answer}</p>
          </div>
        </article>
        <div className="uc-draft-actions">
          <button
            className="uc-reject-action"
            onClick={() => void decideDraft(false)}
            disabled={starting}
          >
            <X size={15} /> Rechazar
          </button>
          <select
            value={rejectionReason}
            onChange={(event) => setRejectionReason(event.target.value)}
            aria-label="Motivo de rechazo"
          >
            <option value="">Motivo opcional</option>
            {[
              "Repetida",
              "Ya lo domino",
              "No entra en evaluación",
              "Mala pregunta",
              "Irrelevante",
              "Otra",
            ].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <button
            className="uc-primary-action"
            onClick={() => void decideDraft(true)}
            disabled={starting}
          >
            <Check size={15} /> Aceptar
          </button>
        </div>
        {error && <div className="uc-inline-error">{error}</div>}
      </div>
    );
  }

  if (cards.length && currentCard)
    return (
      <div className="uc-page-shell uc-live-study uc-flashcard-session">
        <header>
          <button className="uc-back-link" onClick={() => void finishSession()}>
            <ArrowLeft size={15} /> Finalizar sesión
          </button>
          <div>
            <p className="uc-eyebrow">
              Evaluación · {answerModeCopy[answerMode]} ·{" "}
              {curriculum?.subject.academic_language}
            </p>
            <h1>{target?.name}</h1>
            <p>
              {cardIndex + 1} / {cards.length} · Box{" "}
              {currentCard.leitner_box ?? 1}
            </p>
          </div>
        </header>
        <div className="uc-flashcard-progress">
          <span
            style={{
              width: `${((cardIndex + (revealed ? 1 : 0)) / cards.length) * 100}%`,
            }}
          />
        </div>
        <article className="uc-flashcard">
          <span>
            {levelCopy[currentCard.cognitive_level as CognitiveLevel] ??
              "Mixed"}
          </span>
          <h2>{currentCard.question}</h2>
          {writtenTurn ? (
            <div className="uc-written-answer">
              <label>
                Tu respuesta
                <textarea
                  rows={7}
                  value={writtenAnswer}
                  onChange={(event) => setWrittenAnswer(event.target.value)}
                  disabled={Boolean(evaluation)}
                />
              </label>
              {!evaluation && (
                <button
                  onClick={() => void evaluateWritten()}
                  disabled={starting || writtenAnswer.trim().length < 20}
                >
                  {starting ? "Evaluando…" : "Evaluar respuesta"}
                </button>
              )}
            </div>
          ) : revealed ? (
            <div>
              <span>Respuesta</span>
              <p>{currentCard.correct_answer}</p>
            </div>
          ) : (
            <button onClick={() => setRevealed(true)}>Mostrar respuesta</button>
          )}
        </article>
        {evaluation && (
          <section className="uc-written-feedback">
            <header>
              <div>
                <p className="uc-eyebrow">Evaluación estricta</p>
                <h2>{evaluation.overall_score.toFixed(0)}/100</h2>
              </div>
              <TokenUsageNote usage={evaluationUsage} />
            </header>
            <div className="uc-evaluation-dimensions">
              {evaluation.dimensions.map((item) => (
                <div key={item.name}>
                  <span>{item.name.replaceAll("_", " ")}</span>
                  <strong>{item.score}/100</strong>
                  <p>{item.feedback}</p>
                </div>
              ))}
            </div>
            {evaluation.errors.length > 0 && (
              <div>
                <h3>Errores concretos</h3>
                <ul>
                  {evaluation.errors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {evaluation.improvements.length > 0 && (
              <div>
                <h3>Cómo mejorar</h3>
                <ul>
                  {evaluation.improvements.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {evaluation.example_improvement && (
              <blockquote>{evaluation.example_improvement}</blockquote>
            )}
          </section>
        )}
        {(writtenTurn ? Boolean(evaluation) : revealed) &&
          (writtenTurn ? (
            <button
              className="uc-primary-action uc-written-next"
              disabled={starting}
              onClick={() => void advanceWritten()}
            >
              {cardIndex === cards.length - 1
                ? "Finalizar sesión"
                : "Siguiente tarjeta"}
            </button>
          ) : (
            <div className="uc-flashcard-ratings">
              <button
                disabled={starting}
                onClick={() => void submitCardRating("difficult")}
              >
                No la sabía
              </button>
              <button
                disabled={starting}
                onClick={() => void submitCardRating("good")}
              >
                La sabía
              </button>
              <button
                disabled={starting}
                onClick={() => void submitCardRating("easy")}
              >
                La dominaba
              </button>
            </div>
          ))}
        {error && <div className="uc-inline-error">{error}</div>}
      </div>
    );

  if (completed)
    return (
      <div className="uc-page-shell uc-study-complete">
        <Check size={24} />
        <p className="uc-eyebrow">Sesión registrada</p>
        <h1>Práctica completada.</h1>
        <div>
          <span>
            Tiempo real <strong>{completed.minutes} min</strong>
          </span>
          <span>
            Tarjetas <strong>{completed.cards}</strong>
          </span>
        </div>
        <button
          className="uc-primary-action"
          onClick={() => setCompleted(null)}
        >
          Volver a Evaluación
        </button>
      </div>
    );

  return (
    <div className="uc-page-shell uc-evaluation-page">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">Evaluación académica</p>
          <h1>Comprueba lo que realmente sabes.</h1>
          <p className="uc-page-subtitle">
            La práctica parte del mismo temario persistente que Estudio.
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
          <button onClick={() => subjectId != null && onConfigureSubject(subjectId)}>Configurar</button>
        </div>
      )}
      {view === "select" ? (
        <section className="uc-evaluation-selector">
          <header>
            <span>{academicLanguageLabel}</span>
            <strong>{dueCount} repasos para hoy</strong>
            <strong>{masteryCount} tarjetas dominadas</strong>
          </header>
          <button
            onClick={() => {
              setView("flashcards");
              setFlashcardView("practice");
            }}
          >
            <Layers3 size={22} />
            <span>
              <small>Memoria activa</small>
              <strong>Flashcards</strong>
              <p>
                Práctica adaptativa, respuesta escrita y control de calidad
                antes de Leitner.
              </p>
            </span>
            <em>Entrar</em>
          </button>
          <button onClick={() => setView("quiz")}>
            <ShieldCheck size={22} />
            <span>
              <small>Simulación</small>
              <strong>Quiz</strong>
              <p>
                Configura tema, nivel, preguntas y tiempo. El motor permanece
                futuro.
              </p>
            </span>
            <em>Configurar</em>
          </button>
        </section>
      ) : (
        <>
          <button className="uc-back-link" onClick={() => setView("select")}>
            <ArrowLeft size={15} /> Modos de evaluación
          </button>
          {view === "flashcards" && (
            <section className="uc-evaluation-workspace">
              <nav>
                <button
                  className={flashcardView === "practice" ? "is-active" : ""}
                  onClick={() => setFlashcardView("practice")}
                >
                  <Layers3 size={14} /> Practicar
                </button>
                <button
                  className={flashcardView === "leitner" ? "is-active" : ""}
                  onClick={() => setFlashcardView("leitner")}
                >
                  <RotateCcw size={14} /> Leitner
                </button>
              </nav>
              {flashcardView === "practice" ? (
                <div className="uc-evaluation-sequence"><p className="uc-evaluation-step"><span>01</span> Elige el alcance del temario</p>
                <EvaluationConfig
                  units={units}
                  unitId={unitId}
                  topicId={topicId}
                  subtopicId={subtopicId}
                  onUnit={(id) => {
                    const unit = units.find((item) => item.id === id);
                    setUnitId(id);
                    setTopicId(unit?.topics[0]?.id ?? null);
                    setSubtopicId(null);
                  }}
                  onTopic={(id) => {
                    setTopicId(id);
                    setSubtopicId(null);
                  }}
                  onSubtopic={setSubtopicId}
                >
                  <p className="uc-evaluation-step"><span>02</span> Ajusta cómo quieres practicar</p>
                  <div className="uc-flashcard-config">
                    <label>
                      <span>Nivel</span>
                      <select
                        value={level}
                        onChange={(event) =>
                          setLevel(event.target.value as CognitiveLevel)
                        }
                      >
                        {Object.entries(levelCopy).map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Modo</span>
                      <select
                        value={answerMode}
                        onChange={(event) =>
                          setAnswerMode(event.target.value as AnswerMode)
                        }
                      >
                        {Object.entries(answerModeCopy).map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Tarjetas</span>
                      <select
                        value={cardCount}
                        onChange={(event) =>
                          setCardCount(Number(event.target.value))
                        }
                      >
                        {[5, 6, 7, 8, 9, 10].map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Duración</span>
                      <select
                        value={duration}
                        onChange={(event) =>
                          setDuration(Number(event.target.value))
                        }
                      >
                        {[15, 30, 45, 60, 90].map((value) => (
                          <option key={value}>{value} min</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p className="uc-mixed-note">
                    Mixed: 10% recall · 20% understanding · 35% application ·
                    35% analysis.{" "}
                    {languageReady
                      ? `Generación en ${academicLanguageLabel}.`
                      : "Configura el idioma académico para generar."}
                  </p>
                  <button
                    className="uc-primary-action"
                    disabled={starting || !target}
                    onClick={() => languageReady ? void beginFlashcards() : subjectId != null && onConfigureSubject(subjectId)}
                  >
                    {starting ? "Generando lote…" : "Crear flashcards"}
                  </button>
                </EvaluationConfig>
                </div>
              ) : (
                <LeitnerView
                  leitner={leitner}
                  selectedBox={selectedBox}
                  setSelectedBox={setSelectedBox}
                  starting={starting}
                  changeBox={changeBox}
                />
              )}
            </section>
          )}
          {view === "quiz" && (
            <section className="uc-quiz-config">
              <header>
                <p className="uc-eyebrow">Quiz · futuro próximo</p>
                <h2>Configura la evaluación</h2>
                <p>
                  El selector utiliza el temario real; el motor todavía no está
                  activo.
                </p>
              </header>
              <EvaluationConfig
                units={units}
                unitId={unitId}
                topicId={topicId}
                subtopicId={subtopicId}
                onUnit={(id) => {
                  const unit = units.find((item) => item.id === id);
                  setUnitId(id);
                  setTopicId(unit?.topics[0]?.id ?? null);
                  setSubtopicId(null);
                }}
                onTopic={(id) => {
                  setTopicId(id);
                  setSubtopicId(null);
                }}
                onSubtopic={setSubtopicId}
              >
                <p className="uc-evaluation-step"><span>02</span> Ajusta el formato futuro</p>
                <div className="uc-quiz-options">
                  <label>
                    <span>Nivel</span>
                    <select
                      value={level}
                      onChange={(event) =>
                        setLevel(event.target.value as CognitiveLevel)
                      }
                    >
                      {Object.entries(levelCopy).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Preguntas</span>
                    <select defaultValue="10">
                      <option>5</option>
                      <option>10</option>
                      <option>15</option>
                    </select>
                  </label>
                  <label>
                    <span>Duración</span>
                    <select defaultValue="20">
                      <option value="10">10:00</option>
                      <option value="20">20:00</option>
                      <option value="30">30:00</option>
                    </select>
                  </label>
                </div>
                <button className="uc-primary-action" disabled>
                  Próximamente
                </button>
              </EvaluationConfig>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function EvaluationConfig({
  units,
  unitId,
  topicId,
  subtopicId,
  onUnit,
  onTopic,
  onSubtopic,
  children,
}: {
  units: CurriculumUnit[];
  unitId: number | null;
  topicId: number | null;
  subtopicId: number | null;
  onUnit: (id: number) => void;
  onTopic: (id: number) => void;
  onSubtopic: (id: number | null) => void;
  children: React.ReactNode;
}) {
  const unit = units.find((item) => item.id === unitId);
  const topic = unit?.topics.find((item) => item.id === topicId);
  return (
    <div className="uc-curriculum-config">
      <div className="uc-curriculum-selectors">
        <label>
          <span>Unidad</span>
          <select
            value={unitId ?? ""}
            onChange={(event) => onUnit(Number(event.target.value))}
          >
            <option value="" disabled>
              Seleccionar
            </option>
            {units.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Tema</span>
          <select
            value={topicId ?? ""}
            disabled={!unit}
            onChange={(event) => onTopic(Number(event.target.value))}
          >
            <option value="" disabled>
              Seleccionar
            </option>
            {unit?.topics.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Subtema · opcional</span>
          <select
            value={subtopicId ?? ""}
            disabled={!topic?.subtopics.length}
            onChange={(event) =>
              onSubtopic(event.target.value ? Number(event.target.value) : null)
            }
          >
            <option value="">Todo el tema</option>
            {topic?.subtopics.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!units.length && (
        <div className="uc-task-empty">
          <strong>No hay temario disponible.</strong>
          <span>Añade material estructurado desde la asignatura.</span>
        </div>
      )}
      {children}
    </div>
  );
}

function LeitnerView({
  leitner,
  selectedBox,
  setSelectedBox,
  starting,
  changeBox,
}: {
  leitner: LeitnerData | null;
  selectedBox: number;
  setSelectedBox: (box: number) => void;
  starting: boolean;
  changeBox: (
    card: Flashcard,
    targetBox?: number,
    earlier?: boolean,
  ) => Promise<void>;
}) {
  const boxCards =
    leitner?.cards.filter((item) => item.leitner_box === selectedBox) ?? [];
  return (
    <section className="uc-leitner-view">
      <header>
        <p className="uc-eyebrow">Spaced repetition</p>
        <h2>Tu memoria por boxes</h2>
        <p>El sistema recomienda; tú mantienes el control final.</p>
      </header>
      <div className="uc-leitner-boxes">
        {leitner?.boxes.map((box) => (
          <button
            key={box.box}
            className={selectedBox === box.box ? "is-active" : ""}
            onClick={() => setSelectedBox(box.box)}
          >
            <span>Box {box.box}</span>
            <strong>{box.count}</strong>
            <small>
              {box.name} · {box.interval_days} día
              {box.interval_days === 1 ? "" : "s"}
            </small>
            <em>{box.due_count} para hoy</em>
          </button>
        ))}
      </div>
      <div className="uc-leitner-ledger">
        <div className="uc-leitner-head">
          <span>Pregunta</span>
          <span>Nivel</span>
          <span>Último repaso</span>
          <span>Próximo</span>
          <span>Mover</span>
        </div>
        {boxCards.length ? (
          boxCards.map((card) => (
            <article key={card.id}>
              <div>
                <strong>{card.question}</strong>
                <small>
                  {card.subject_name} · {card.concept_name ?? card.topic}
                </small>
              </div>
              <span>
                {levelCopy[card.cognitive_level as CognitiveLevel] ??
                  card.cognitive_level}
              </span>
              <span>
                {card.last_reviewed_at
                  ? new Date(card.last_reviewed_at).toLocaleDateString("es-ES")
                  : "Sin repaso"}
              </span>
              <span>
                {card.next_review_at
                  ? new Date(card.next_review_at).toLocaleDateString("es-ES")
                  : "—"}
              </span>
              <div>
                <select
                  value={card.leitner_box}
                  disabled={starting}
                  onChange={(event) =>
                    void changeBox(card, Number(event.target.value))
                  }
                >
                  {[1, 2, 3, 4, 5].map((box) => (
                    <option key={box} value={box}>
                      Box {box}
                    </option>
                  ))}
                </select>
                <button
                  disabled={starting}
                  onClick={() => void changeBox(card, undefined, true)}
                >
                  Repasar antes
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="uc-task-empty">
            <strong>Esta box está vacía.</strong>
            <span>Las tarjetas aceptadas aparecerán aquí.</span>
          </div>
        )}
      </div>
    </section>
  );
}
