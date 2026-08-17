import {
  ArrowLeft,
  BookOpen,
  Brain,
  Clock3,
  Copy,
  ChevronDown,
  ChevronRight,
  FileText,
  Link2,
  MessageCircle,
  GripVertical,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  analyzeStudyTopic,
  createStudySession,
  createStudyTopicDiagnostic,
  getCurriculum,
  getCurriculumReview,
  resetCurriculum,
  getDashboard,
  getStudy,
  getStudyPriority,
  getStudyTopicAnalysis,
  gradeStudyTopicDiagnostic,
  saveCurriculumReview,
  setCurriculumImportance,
  startExplanation,
  sendAgentMessage,
  type AgentSource,
  type CurriculumData,
  type CurriculumReviewData,
  type CurriculumStatus,
  type CurriculumSubtopic,
  type CurriculumTopic,
  type DashboardData,
  type StudyData,
  type StudyPriorityData,
  type StudyPriorityItem,
  type StudyTopicAnalysis,
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

type ReviewSubtopicDraft = {
  id?: number;
  name: string;
  selected: boolean;
  key: string;
  sourceLabel?: string | null;
};

type ReviewTopicDraft = {
  id?: number;
  name: string;
  selected: boolean;
  key: string;
  sourceLabel?: string | null;
  subtopics: ReviewSubtopicDraft[];
};

const statusCopy: Record<CurriculumStatus, string> = {
  not_studied: "No estudiado",
  learning: "En aprendizaje",
  consolidating: "Consolidando",
  mastered: "Dominado",
};
const analysisStages = [
  "Buscando el material relacionado",
  "Midiendo la carga de contenido",
  "Evaluando la complejidad conceptual",
  "Calculando la importancia académica",
  "Análisis listo",
];
const shortDate = (value: string) =>
  new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
  });

function externalCurriculumPrompt(subjectName: string) {
  return `Quiero que extraigas el temario académico REAL de los materiales que te voy a adjuntar o pegar para la asignatura "${subjectName}".

Tu objetivo NO es resumir el contenido y NO es inventar temas. Debes identificar únicamente la estructura que un estudiante debería usar para estudiar: temas principales y, cuando tenga sentido, sus subtemas.

REGLAS IMPORTANTES:
1. Ignora títulos generales de la asignatura, nombres repetidos en todas las diapositivas, encabezados, pies de página, números de unidad, nombres del profesor, casos prácticos aislados, ejercicios, ejemplos, bibliografía y textos decorativos.
2. Un TEMA debe representar un bloque real y suficientemente amplio del temario. No conviertas cada diapositiva o cada encabezado pequeño en un tema.
3. Un SUBTEMA debe pertenecer claramente al tema anterior y ser una parte concreta que tenga sentido estudiar por separado.
4. Si un concepto aparece muchas veces pero solo como cabecera general del curso, NO lo incluyas como tema.
5. Mantén el orden académico original de los materiales.
6. No dupliques temas con nombres parecidos. Fusiónalos si representan el mismo bloque.
7. No añadas explicaciones, comentarios, introducciones ni conclusiones.
8. Devuelve TODO dentro de un único bloque de código de texto para que pueda copiarse con un solo clic. No escribas absolutamente nada fuera de ese bloque.
9. Dentro del bloque usa SOLO el formato indicado abajo. Es muy importante respetarlo exactamente porque otro programa leerá tu respuesta automáticamente.

FORMATO OBLIGATORIO DENTRO DEL BLOQUE:
TOPIC: Nombre del primer tema
SUBTOPIC: Subtema del primer tema
SUBTOPIC: Otro subtema del primer tema
TOPIC: Nombre del segundo tema
SUBTOPIC: Subtema del segundo tema

Si un tema no tiene subtemas, escribe solo su línea TOPIC.
No uses listas numeradas, guiones, tablas ni negritas dentro del bloque. Solo líneas TOPIC: y SUBTOPIC:.`;
}

function parseExternalCurriculum(text: string): ReviewTopicDraft[] {
  const topics: ReviewTopicDraft[] = [];
  let current: ReviewTopicDraft | null = null;
  let sequence = 0;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine
      .trim()
      .replace(/^```[a-zA-Z]*$/, "")
      .replace(/^[-*•]+\s*/, "")
      .replace(/^\d+[.)]\s*/, "")
      .trim();
    if (!line || line === "```") continue;

    const topicMatch = line.match(/^(?:TOPIC|TEMA)\s*:\s*(.+)$/i);
    if (topicMatch) {
      const name = topicMatch[1].trim();
      if (!name) continue;
      sequence += 1;
      current = {
        name,
        selected: true,
        key: `imported-topic-${Date.now()}-${sequence}`,
        subtopics: [],
      };
      topics.push(current);
      continue;
    }

    const subtopicMatch = line.match(/^(?:SUBTOPIC|SUBTEMA)\s*:\s*(.+)$/i);
    if (subtopicMatch && current) {
      const name = subtopicMatch[1].trim();
      if (!name) continue;
      sequence += 1;
      current.subtopics.push({
        name,
        selected: true,
        key: `imported-subtopic-${Date.now()}-${sequence}`,
      });
    }
  }
  return topics;
}

export default function StudyPage({
  launchContext,
  onConfigureSubject,
  onFocusChange,
}: {
  launchContext?: StudyLaunchContext;
  onConfigureSubject: (subjectId: number) => void;
  onFocusChange: (active: boolean) => void;
}) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [study, setStudy] = useState<StudyData | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [priority, setPriority] = useState<StudyPriorityData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(
    launchContext?.subjectId ?? null,
  );
  const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set());
  const [expandedTopics, setExpandedTopics] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<SelectedCurriculumItem | null>(null);
  const [duration, setDuration] = useState(30);
  const [active, setActive] = useState<ActiveExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewData, setReviewData] = useState<CurriculumReviewData | null>(null);
  const [reviewUnitId, setReviewUnitId] = useState<number | null>(null);
  const [reviewTopics, setReviewTopics] = useState<ReviewTopicDraft[]>([]);
  const [draggedTopicIndex, setDraggedTopicIndex] = useState<number | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);
  const [aiImportOpen, setAiImportOpen] = useState(false);
  const [aiCurriculumText, setAiCurriculumText] = useState("");
  const [promptCopied, setPromptCopied] = useState(false);
  const [aiImportMessage, setAiImportMessage] = useState<string | null>(null);
  const [importanceSaving, setImportanceSaving] = useState(false);
  const [topicAnalysis, setTopicAnalysis] = useState<StudyTopicAnalysis | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [diagnosticMode, setDiagnosticMode] = useState(false);
  const [diagnosticBusy, setDiagnosticBusy] = useState(false);
  const [diagnosticAnswers, setDiagnosticAnswers] = useState<[string, string]>(["", ""]);
  const [error, setError] = useState<string | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentInput, setAgentInput] = useState("");
  const [agentMessages, setAgentMessages] = useState<Array<{ role: "user" | "agent"; text: string; sources?: AgentSource[] }>>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [agentBusy, setAgentBusy] = useState(false);

  async function loadSubject(id: number) {
    setSubjectId(id);
    setLoading(true);
    setError(null);
    setSelected(null);
    setActive(null);
    try {
      const [curriculumData, studyData, priorityData] = await Promise.all([
        getCurriculum(id),
        getStudy(id),
        getStudyPriority(id),
      ]);
      setCurriculum(curriculumData);
      setStudy(studyData);
      setPriority(priorityData);
      setExpandedUnits(new Set());
      setExpandedTopics(new Set());
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

  useEffect(() => {
    let cancelled = false;
    if (!selected) {
      setTopicAnalysis(null);
      return () => { cancelled = true; };
    }
    void getStudyTopicAnalysis(selected.id)
      .then((result) => {
        if (!cancelled) setTopicAnalysis(result.analysis ?? null);
      })
      .catch(() => {
        if (!cancelled) setTopicAnalysis(null);
      });
    return () => { cancelled = true; };
  }, [selected?.id]);

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
      onFocusChange(true);
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

  async function openCurriculumReview() {
    if (subjectId == null || reviewLoading) return;

    setReviewLoading(true);
    setError(null);

    try {
      const data = await getCurriculumReview(subjectId);
      setReviewData(data);
      setAiImportOpen(false);
      setAiCurriculumText("");
      setPromptCopied(false);
      setAiImportMessage(null);

      const unit = data.units[0];
      if (!unit) {
        setError("No hay ninguna unidad disponible para revisar.");
        return;
      }

      setReviewUnitId(unit.id);
      setReviewTopics(
        unit.topics
          .filter((topic) => topic.selected)
          .map((topic) => ({
            id: topic.id,
            name: topic.name,
            selected: true,
            key: `topic-${topic.id}`,
            sourceLabel: topic.sources?.[0]?.source_label ?? null,
            subtopics: (topic.subtopics ?? [])
              .filter((subtopic) => subtopic.selected)
              .map((subtopic) => ({
                id: subtopic.id,
                name: subtopic.name,
                selected: true,
                key: `subtopic-${subtopic.id}`,
                sourceLabel: subtopic.sources?.[0]?.source_label ?? null,
              })),
          })),
      );
      setReviewOpen(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo cargar la revisión del temario.",
      );
    } finally {
      setReviewLoading(false);
    }
  }

  function updateReviewTopic(
    index: number,
    changes: Partial<ReviewTopicDraft>,
  ) {
    setReviewTopics((current) =>
      current.map((topic, topicIndex) =>
        topicIndex === index ? { ...topic, ...changes } : topic,
      ),
    );
  }

  function addReviewTopic() {
    setReviewTopics((current) => [
      ...current,
      {
        name: "",
        selected: true,
        key: `new-topic-${Date.now()}`,
        subtopics: [],
      },
    ]);
  }

  function rejectReviewTopic(index: number) {
    setReviewTopics((current) =>
      current.filter((_, topicIndex) => topicIndex !== index),
    );
  }

  function moveDraggedTopic(targetIndex: number) {
    if (draggedTopicIndex == null || draggedTopicIndex === targetIndex) return;

    setReviewTopics((current) => {
      const next = [...current];
      const [dragged] = next.splice(draggedTopicIndex, 1);
      next.splice(targetIndex, 0, dragged);
      return next;
    });
    setDraggedTopicIndex(targetIndex);
  }

  function addReviewSubtopic(topicIndex: number) {
    setReviewTopics((current) =>
      current.map((topic, index) =>
        index === topicIndex
          ? {
              ...topic,
              selected: true,
              subtopics: [
                ...topic.subtopics,
                {
                  name: "",
                  selected: true,
                  key: `new-subtopic-${Date.now()}-${topicIndex}`,
                },
              ],
            }
          : topic,
      ),
    );
  }

  function updateReviewSubtopic(
    topicIndex: number,
    subtopicIndex: number,
    changes: Partial<ReviewSubtopicDraft>,
  ) {
    setReviewTopics((current) =>
      current.map((topic, index) =>
        index === topicIndex
          ? {
              ...topic,
              subtopics: topic.subtopics.map((subtopic, childIndex) =>
                childIndex === subtopicIndex
                  ? { ...subtopic, ...changes }
                  : subtopic,
              ),
            }
          : topic,
      ),
    );
  }

  function removeReviewSubtopic(topicIndex: number, subtopicIndex: number) {
    setReviewTopics((current) =>
      current.map((topic, index) =>
        index === topicIndex
          ? {
              ...topic,
              subtopics: topic.subtopics.filter((_, childIndex) =>
                childIndex !== subtopicIndex
              ),
            }
          : topic,
      ),
    );
  }

  async function saveReview() {
    if (subjectId == null || reviewUnitId == null || reviewSaving) return;

    setReviewSaving(true);
    setError(null);

    try {
      await saveCurriculumReview(
        subjectId,
        reviewUnitId,
        reviewTopics.map(({ id, name, selected, subtopics }) => ({
          id,
          name,
          selected,
          subtopics: subtopics.map((subtopic) => ({
            id: subtopic.id,
            name: subtopic.name,
            selected: subtopic.selected,
          })),
        })),
      );

      const [curriculumData, studyData] = await Promise.all([
        getCurriculum(subjectId),
        getStudy(subjectId),
      ]);

      setCurriculum(curriculumData);
      setStudy(studyData);
      setSelected(null);
      setExpandedUnits(new Set());
      setExpandedTopics(new Set());
      setReviewOpen(false);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo guardar el temario.",
      );
    } finally {
      setReviewSaving(false);
    }
  }

  async function finishExplanation() {
    if (!active || subjectId == null) {
      setActive(null);
      setAgentOpen(false);
      onFocusChange(false);
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

  async function askAgent() {
    if (!agentInput.trim() || subjectId == null || !active || agentBusy) return;
    const question = agentInput.trim();
    setAgentInput(""); setAgentMessages((current) => [...current, { role: "user", text: question }]); setAgentBusy(true);
    try {
      const result = await sendAgentMessage(question, { conversationId, subjectId, contextType: "work_session", workContext: { topic: active.item.name, explanation: active.content, source_document_ids: active.sources.map((source) => source.document_id) } });
      setConversationId(result.conversation_id);
      setAgentMessages((current) => [...current, { role: "agent", text: result.answer ?? result.error ?? "No pude preparar una respuesta.", sources: result.sources }]);
    } catch (caught) { setAgentMessages((current) => [...current, { role: "agent", text: caught instanceof Error ? caught.message : "No se pudo consultar a UniCore." }]); }
    finally { setAgentBusy(false); }
  }

  function toggleUnit(id: number) {
    setExpandedUnits((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleTopic(id: number) {
    setExpandedTopics((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function refreshCurriculum() {
    if (subjectId == null || loading) return;
    setLoading(true);
    setError(null);
    try {
      const [curriculumData, studyData, priorityData] = await Promise.all([
        getCurriculum(subjectId),
        getStudy(subjectId),
        getStudyPriority(subjectId),
      ]);
      setCurriculum(curriculumData);
      setStudy(studyData);
      setPriority(priorityData);
      setSelected(null);
      setExpandedUnits(new Set());
      setExpandedTopics(new Set());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo actualizar el temario.");
    } finally {
      setLoading(false);
    }
  }

  async function clearCurriculum() {
    if (subjectId == null || reviewSaving) return;
    const accepted = window.confirm(
      "Se borrarán todos los temas y subtemas de esta asignatura. Los materiales no se borrarán. ¿Continuar?",
    );
    if (!accepted) return;

    setReviewSaving(true);
    setError(null);
    try {
      const result = await resetCurriculum(subjectId);
      const [curriculumData, studyData, priorityData] = await Promise.all([
        getCurriculum(subjectId),
        getStudy(subjectId),
        getStudyPriority(subjectId),
      ]);
      setReviewData(result);
      setReviewUnitId(result.units[0]?.id ?? null);
      setReviewTopics([]);
      setCurriculum(curriculumData);
      setStudy(studyData);
      setPriority(priorityData);
      setSelected(null);
      setExpandedUnits(new Set());
      setExpandedTopics(new Set());
      setAiCurriculumText("");
      setAiImportMessage("Temario borrado. Ya puedes crear uno nuevo desde cero.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo borrar el temario.");
    } finally {
      setReviewSaving(false);
    }
  }

  async function changeImportance(mode: "manual", level: 1 | 2 | 3) {
    if (!selected || subjectId == null || importanceSaving) return;
    setImportanceSaving(true);
    setError(null);
    try {
      await setCurriculumImportance(selected.id, mode, level);
      const priorityData = await getStudyPriority(subjectId);
      setPriority(priorityData);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo guardar la importancia.");
    } finally {
      setImportanceSaving(false);
    }
  }

  async function runUniCoreAnalysis(force = false) {
    if (!selected || subjectId == null || analysisBusy) return;
    setAnalysisOpen(true);
    setDiagnosticMode(false);
    setDiagnosticAnswers(["", ""]);
    setAnalysisBusy(true);
    setAnalysisStage(0);
    setError(null);

    const timer = window.setInterval(() => {
      setAnalysisStage((current) => Math.min(3, current + 1));
    }, 800);

    try {
      const result = await analyzeStudyTopic(selected.id, force);
      setTopicAnalysis(result.analysis ?? null);
      setAnalysisStage(4);
    } catch (caught) {
      setAnalysisOpen(false);
      setError(caught instanceof Error ? caught.message : "UniCore no pudo analizar este tema.");
    } finally {
      window.clearInterval(timer);
      setAnalysisBusy(false);
    }
  }

  async function useUniCoreImportance() {
    if (!selected || subjectId == null || importanceSaving || !topicAnalysis) return;
    setImportanceSaving(true);
    setError(null);
    try {
      await setCurriculumImportance(selected.id, "unicore");
      const priorityData = await getStudyPriority(subjectId);
      setPriority(priorityData);
      setAnalysisOpen(false);
      setDiagnosticMode(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo aplicar el análisis de UniCore.");
    } finally {
      setImportanceSaving(false);
    }
  }

  async function startDiagnostic() {
    if (!selected || diagnosticBusy) return;
    setDiagnosticBusy(true);
    setError(null);
    try {
      const result = await createStudyTopicDiagnostic(selected.id);
      setTopicAnalysis(result.analysis ?? null);
      setDiagnosticMode(true);
      setDiagnosticAnswers(["", ""]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudieron preparar las preguntas.");
    } finally {
      setDiagnosticBusy(false);
    }
  }

  async function submitDiagnostic() {
    if (!selected || subjectId == null || diagnosticBusy) return;
    setDiagnosticBusy(true);
    setError(null);
    try {
      const result = await gradeStudyTopicDiagnostic(selected.id, diagnosticAnswers);
      setTopicAnalysis(result.analysis ?? null);
      const priorityData = await getStudyPriority(subjectId);
      setPriority(priorityData);
      setDiagnosticMode(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudieron evaluar las respuestas.");
    } finally {
      setDiagnosticBusy(false);
    }
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
  const priorityByItem = useMemo(
    () => new Map((priority?.items ?? []).map((item) => [item.item_id, item])),
    [priority],
  );
  const selectedPriority: StudyPriorityItem | null = selected
    ? priorityByItem.get(selected.id) ?? null
    : null;
  const nextRecommendation = priority?.recommendations?.[0] ?? null;
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
      <div className={`uc-page-shell uc-live-study uc-curriculum-explanation ${agentOpen ? "is-agent-open" : ""}`}>
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
                <button className="uc-agent-context-cta" onClick={() => setAgentOpen(true)}><MessageCircle size={15} /> Preguntar a UniCore sobre este tema</button>
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
        {agentOpen && <aside className="uc-study-agent-drawer"><header><div><p className="uc-eyebrow">UniCore Agent</p><h2>Ayuda contextual</h2></div><button onClick={() => setAgentOpen(false)} aria-label="Cerrar"><X size={18} /></button></header><p>La conversación conoce el tema, la explicación y sus fuentes.</p><div className="uc-study-agent-stream">{agentMessages.length === 0 && <div className="uc-work-agent-neutral"><strong>Asistencia disponible.</strong><p>Escribe una duda concreta cuando la necesites.</p></div>}{agentMessages.map((message, index) => <article className={`uc-message is-${message.role}`} key={index}><span>{message.role === "user" ? "Tú" : "UniCore"}</span>{message.role === "agent" ? <AcademicMarkdown content={message.text} sources={message.sources} /> : <p>{message.text}</p>}</article>)}{agentBusy && <p>Consultando el contexto…</p>}</div><form onSubmit={(event) => { event.preventDefault(); void askAgent(); }}><textarea rows={1} value={agentInput} disabled={agentBusy} onChange={(event) => setAgentInput(event.target.value)} onInput={(event) => { event.currentTarget.style.height = "auto"; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 104)}px`; }} placeholder={`Pregunta sobre ${active.item.name}…`} /><button disabled={agentBusy || !agentInput.trim()} aria-label="Enviar"><Send size={16} /></button></form></aside>}
      </div>
    );

  return (
    <div className="uc-page-shell uc-curriculum-study">
      <header className="uc-page-intro">
        <div>
          <p className="uc-eyebrow">Aprendizaje · Temario personal</p>
          <h1>Estudia desde tu temario.</h1>
          <p className="uc-page-subtitle">
            Tu temario es la estructura maestra: UniCore conecta materiales, progreso,
            flashcards, quizzes y recomendaciones alrededor de cada tema.
          </p>
        </div>
        <div className="uc-study-header-actions">
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
          <button
            className="uc-curriculum-refresh"
            onClick={() => void refreshCurriculum()}
            disabled={loading}
            title="Recarga el temario guardado y recalcula progreso y prioridades"
          >
            <RefreshCw size={14} />
            {loading ? "Actualizando…" : "Actualizar temario"}
          </button>
          <button
            className="uc-curriculum-refresh"
            onClick={() => void openCurriculumReview()}
            disabled={reviewLoading}
          >
            <BookOpen size={14} />
            {reviewLoading ? "Cargando…" : "Revisar temario"}
          </button>
        </div>
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
      {nextRecommendation && (
        <section className="uc-study-next-action">
          <div className="uc-study-next-action-icon"><Target size={20} /></div>
          <div className="uc-study-next-action-copy">
            <p className="uc-eyebrow">Qué estudiar ahora</p>
            <h2>{nextRecommendation.name}</h2>
            <div className="uc-study-next-meta">
              <span className={`is-priority-${nextRecommendation.priority_label.toLowerCase().replace(" ", "-")}`}>
                Prioridad {nextRecommendation.priority_label.toLowerCase()}
              </span>
              <span><Clock3 size={13} /> {nextRecommendation.estimated_minutes} min recomendados</span>
              <span><Brain size={13} /> {nextRecommendation.mastery == null ? "Dominio sin medir" : `${Math.round(nextRecommendation.mastery)}% dominio`}</span>
              <span>Importancia {nextRecommendation.importance_label.toLowerCase()}</span>
            </div>
          </div>
          <button
            className="uc-primary-action"
            onClick={() => {
              const target = curriculum?.units.flatMap((unit) => unit.topics).find((topic) => topic.id === nextRecommendation.item_id);
              if (target) {
                setSelected(target);
                setExpandedTopics((current) => new Set(current).add(target.id));
              }
            }}
          >
            Empezar por aquí <ChevronRight size={15} />
          </button>
        </section>
      )}

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
                      {unit.topics.map((topic) => {
                        const topicOpen = expandedTopics.has(topic.id);
                        const topicMetric = priorityByItem.get(topic.id);
                        return (
                          <div className="uc-topic-tree" key={topic.id}>
                            <button
                              type="button"
                              className={`uc-topic-row ${selected?.id === topic.id ? "is-active" : ""}`}
                              onClick={() => {
                                setSelected(topic);
                                if (topic.subtopics.length > 0) toggleTopic(topic.id);
                              }}
                              aria-expanded={topic.subtopics.length > 0 ? topicOpen : undefined}
                            >
                              <span className={`uc-curriculum-state is-${topic.status}`} />
                              <strong className="uc-topic-title">{topic.name}</strong>
                              {topicMetric && (
                                <em className="uc-topic-priority">{topicMetric.priority_label}</em>
                              )}
                              {topic.subtopics.length > 0 ? (
                                <span className="uc-topic-expand" aria-hidden="true">
                                  {topicOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                                  <span>{topic.subtopics.length}</span>
                                </span>
                              ) : (
                                <span className="uc-topic-expand is-empty" aria-hidden="true" />
                              )}
                            </button>
                            {topicOpen && topic.subtopics.length > 0 && (
                              <div className="uc-subtopic-tree">
                                <button
                                  className={selected?.id === topic.id ? "is-active is-all-topic" : "is-all-topic"}
                                  onClick={() => setSelected(topic)}
                                >
                                  <span className="uc-all-topic-icon"><BookOpen size={13} /></span>
                                  <span className="uc-all-topic-copy">
                                    <strong>Todo el tema</strong>
                                    <small>Estudiar {topic.name} completo · incluye todos los subtemas</small>
                                  </span>
                                  <ChevronRight size={14} />
                                </button>
                                {topic.subtopics.map((subtopic) => {
                                  const subMetric = priorityByItem.get(subtopic.id);
                                  return (
                                    <button
                                      className={selected?.id === subtopic.id ? "is-active" : ""}
                                      key={subtopic.id}
                                      onClick={() => setSelected(subtopic)}
                                    >
                                      <span>↳</span>
                                      <strong>{subtopic.name}</strong>
                                      <small>
                                        {subMetric?.mastery == null
                                          ? statusCopy[subtopic.status]
                                          : `${Math.round(subMetric.mastery)}% dominio`}
                                      </small>
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
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
                <section className="uc-study-topic-intelligence">
                  <div className="uc-study-intelligence-head">
                    <h3>Prioridad de estudio</h3>
                    {selectedPriority && (
                      <span className={`uc-priority-pill is-${selectedPriority.priority_label.toLowerCase().replace(" ", "-")}`}>
                        {selectedPriority.priority_label}
                      </span>
                    )}
                  </div>
                  {selectedPriority ? (
                    <>
                      <div className="uc-study-intelligence-grid">
                        <div><span>Dominio</span><strong>{selectedPriority.mastery == null ? "Sin datos" : `${Math.round(selectedPriority.mastery)}%`}</strong></div>
                        <div><span>Tiempo sugerido</span><strong>{selectedPriority.estimated_minutes} min</strong></div>
                        <div><span>Flashcards</span><strong>{selectedPriority.flashcard_reviews ? `${selectedPriority.flashcard_errors}/${selectedPriority.flashcard_reviews} fallos` : "Sin historial"}</strong></div>
                        <div><span>Quiz</span><strong>{selectedPriority.quiz_average == null ? "Sin historial" : `${Math.round(selectedPriority.quiz_average)}%`}</strong></div>
                      </div>
                      <div className="uc-importance-control">
                        <div>
                          <span>Importancia académica</span>
                          <small>Elige tú la importancia o pide a UniCore que analice el contenido del tema.</small>
                        </div>
                        <div className="uc-importance-manual-options">
                          {([1, 2, 3] as const).map((level) => (
                            <button
                              key={level}
                              disabled={importanceSaving}
                              className={selectedPriority.importance_mode === "manual" && selectedPriority.manual_importance === level ? "is-active" : ""}
                              onClick={() => void changeImportance("manual", level)}
                            >
                              {level === 1 ? "Baja" : level === 2 ? "Media" : "Alta"}
                            </button>
                          ))}
                        </div>
                        <button
                          className={`uc-unicore-analysis-trigger ${selectedPriority.importance_mode === "unicore" ? "is-active" : ""}`}
                          disabled={analysisBusy}
                          onClick={() => void runUniCoreAnalysis(Boolean(topicAnalysis?.stale))}
                        >
                          <span><Sparkles size={14} /> UniCore</span>
                          <small>Analizar carga, complejidad e importancia de este tema</small>
                          <ChevronRight size={15} />
                        </button>
                        {topicAnalysis && !topicAnalysis.stale && (
                          <div className="uc-analysis-inline-summary">
                            <span>Último análisis</span>
                            <strong>{topicAnalysis.academic_importance_label}</strong>
                            <small>Complejidad {topicAnalysis.conceptual_complexity_label.toLowerCase()} · carga {topicAnalysis.content_load_label.toLowerCase()}</small>
                          </div>
                        )}
                      </div>
                      {selectedPriority.needs_diagnostic && (
                        <p className="uc-diagnostic-note">
                          Todavía no hay evidencia personal suficiente. Puedes usar el análisis de UniCore tal cual o responder 2 preguntas para afinar tu prioridad de estudio.
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="uc-diagnostic-note">Todavía no hay métricas para este elemento.</p>
                  )}
                </section>
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
          <h2>El temario está pendiente de revisión.</h2>
          <p>
            Todavía no hay temas confirmados. Crea el temario manualmente o pega la estructura preparada con el prompt para IA externa.
          </p>
          <button
            className="uc-primary-action"
            onClick={() => void openCurriculumReview()}
            disabled={reviewLoading}
          >
            <BookOpen size={15} />
            {reviewLoading ? "Cargando…" : "Revisar temario"}
          </button>
        </section>
      )}
{reviewOpen && reviewData && (
        <div
          role="presentation"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 140,
            overflowY: "auto",
            background: "var(--overlay)",
            padding: "32px 20px",
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Revisión del temario"
            style={{
              width: "min(980px, 100%)",
              margin: "0 auto",
              border: "1px solid var(--border-strong)",
              background: "var(--surface-raised)",
              color: "var(--text-primary)",
              boxShadow: "0 28px 90px rgba(0,0,0,.24)",
            }}
          >
            <header
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) auto",
                gap: 24,
                alignItems: "start",
                borderBottom: "1px solid var(--border)",
                padding: "28px 30px 24px",
              }}
            >
              <div>
                <p className="uc-eyebrow">Revisión del temario</p>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 12,
                    flexWrap: "wrap",
                    marginTop: 7,
                  }}
                >
                  <h2
                    style={{
                      margin: 0,
                      fontFamily: 'Georgia, "Times New Roman", serif',
                      fontSize: 32,
                      fontWeight: 500,
                      letterSpacing: "-.035em",
                    }}
                  >
                    {reviewData.units.find((unit) => unit.id === reviewUnitId)?.name ??
                      "Unidad"}
                  </h2>
                  <span
                    style={{
                      color: "var(--text-muted)",
                      fontSize: 10,
                      fontWeight: 800,
                      letterSpacing: ".08em",
                      textTransform: "uppercase",
                    }}
                  >
                    {reviewTopics.length} temas
                  </span>
                </div>
                <p
                  style={{
                    maxWidth: 700,
                    margin: "10px 0 0",
                    color: "var(--text-secondary)",
                    fontSize: 12,
                    lineHeight: 1.6,
                  }}
                >
                  Este temario es manual y manda sobre Estudio. Puedes escribirlo tú o
                  pegar una estructura preparada por una IA externa y revisarla antes de guardar.
                </p>
              </div>
              <button
                onClick={() => setReviewOpen(false)}
                aria-label="Cerrar revisión"
                style={{
                  display: "grid",
                  width: 38,
                  height: 38,
                  placeItems: "center",
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                <X size={18} />
              </button>
            </header>

            <div style={{ padding: "22px 30px 8px" }}>
              <div
                style={{
                  marginBottom: 16,
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                  padding: 16,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                  <div>
                    <strong style={{ display: "block", fontSize: 13 }}>Crear temario con una IA externa</strong>
                    <span style={{ display: "block", marginTop: 4, color: "var(--text-muted)", fontSize: 10, lineHeight: 1.5 }}>
                      UniCore no intenta detectar el temario. Copia el prompt, úsalo con ChatGPT u otra IA y pega aquí su respuesta.
                    </span>
                  </div>
                  <button
                    onClick={() => { setAiImportOpen((current) => !current); setAiImportMessage(null); }}
                    style={{ border: "1px solid var(--border-strong)", background: "var(--surface-raised)", color: "var(--text-primary)", padding: "9px 12px", cursor: "pointer", fontSize: 10, fontWeight: 800 }}
                  >
                    {aiImportOpen ? "Ocultar" : "Usar IA externa"}
                  </button>
                </div>

                {aiImportOpen && (
                  <div style={{ display: "grid", gap: 10, marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border-soft)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                      <span style={{ color: "var(--text-secondary)", fontSize: 10, fontWeight: 800 }}>1. Copia este prompt y úsalo junto a tus materiales</span>
                      <button
                        onClick={async () => {
                          const subjectName = dashboard?.subjects.find((subject) => subject.id === subjectId)?.name ?? "esta asignatura";
                          try {
                            await navigator.clipboard.writeText(externalCurriculumPrompt(subjectName));
                            setPromptCopied(true);
                            window.setTimeout(() => setPromptCopied(false), 1800);
                          } catch {
                            setAiImportMessage("No se pudo copiar automáticamente. Selecciona el prompt de abajo y cópialo manualmente.");
                          }
                        }}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid var(--border)", background: "transparent", color: "var(--text-secondary)", padding: "7px 9px", cursor: "pointer", fontSize: 9, fontWeight: 800 }}
                      >
                        <Copy size={12} /> {promptCopied ? "Copiado" : "Copiar prompt"}
                      </button>
                    </div>
                    <textarea
                      readOnly
                      value={externalCurriculumPrompt(dashboard?.subjects.find((subject) => subject.id === subjectId)?.name ?? "esta asignatura")}
                      rows={6}
                      onFocus={(event) => event.currentTarget.select()}
                      style={{ width: "100%", resize: "vertical", border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-secondary)", padding: 12, fontSize: 10, lineHeight: 1.55 }}
                    />
                    <span style={{ color: "var(--text-secondary)", fontSize: 10, fontWeight: 800 }}>2. Pega aquí la respuesta completa de la IA</span>
                    <textarea
                      value={aiCurriculumText}
                      onChange={(event) => { setAiCurriculumText(event.target.value); setAiImportMessage(null); }}
                      rows={7}
                      placeholder={"TOPIC: What is Strategy?\nSUBTOPIC: Definition of strategy\nTOPIC: Levels of Strategy\nSUBTOPIC: Corporate level"}
                      style={{ width: "100%", resize: "vertical", border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", padding: 12, fontSize: 11, lineHeight: 1.55 }}
                    />
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <button
                        onClick={() => {
                          const parsed = parseExternalCurriculum(aiCurriculumText);
                          if (!parsed.length) {
                            setAiImportMessage("No encontré líneas TOPIC:. Pide a la IA que respete exactamente el formato del prompt.");
                            return;
                          }
                          setReviewTopics(parsed);
                          setAiImportMessage(`${parsed.length} temas importados. Revísalos y pulsa Confirmar temario.`);
                        }}
                        disabled={!aiCurriculumText.trim()}
                        className="uc-primary-action"
                      >
                        Convertir texto en temario
                      </button>
                      {aiImportMessage && <span style={{ color: "var(--text-muted)", fontSize: 10 }}>{aiImportMessage}</span>}
                    </div>
                  </div>
                )}
              </div>

              {reviewTopics.length === 0 ? (
                <div
                  style={{
                    border: "1px dashed var(--border-strong)",
                    padding: 28,
                    textAlign: "center",
                    color: "var(--text-muted)",
                    fontSize: 12,
                  }}
                >
                  No hay temas todavía. Añádelos manualmente o impórtalos desde una IA externa.
                </div>
              ) : (
                <div style={{ display: "grid", gap: 12 }}>
                  {reviewTopics.map((topic, topicIndex) => (
                    <article
                      key={topic.key}
                      draggable
                      onDragStart={() => setDraggedTopicIndex(topicIndex)}
                      onDragOver={(event) => {
                        event.preventDefault();
                        moveDraggedTopic(topicIndex);
                      }}
                      onDragEnd={() => setDraggedTopicIndex(null)}
                      style={{
                        border:
                          draggedTopicIndex === topicIndex
                            ? "1px solid var(--accent)"
                            : "1px solid var(--border)",
                        background: "var(--surface)",
                        opacity: draggedTopicIndex === topicIndex ? 0.66 : 1,
                        transition: "border-color 120ms ease, opacity 120ms ease",
                      }}
                    >
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "38px 42px minmax(0, 1fr) auto",
                          gap: 10,
                          alignItems: "center",
                          minHeight: 62,
                          padding: "10px 12px",
                        }}
                      >
                        <span
                          title="Mantén pulsado y arrastra"
                          style={{
                            display: "grid",
                            height: 38,
                            placeItems: "center",
                            color: "var(--text-faint)",
                            cursor: "grab",
                          }}
                        >
                          <GripVertical size={18} />
                        </span>
                        <span
                          style={{
                            display: "grid",
                            width: 34,
                            height: 34,
                            placeItems: "center",
                            background: "var(--surface-active)",
                            color: "var(--text-secondary)",
                            fontFamily: 'Georgia, "Times New Roman", serif',
                            fontSize: 16,
                          }}
                        >
                          {String(topicIndex + 1).padStart(2, "0")}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <input
                            value={topic.name}
                            placeholder="Nombre del tema"
                            onChange={(event) =>
                              updateReviewTopic(topicIndex, { name: event.target.value })
                            }
                            style={{
                              width: "100%",
                              minWidth: 0,
                              border: 0,
                              borderBottom: "1px solid transparent",
                              outline: 0,
                              background: "transparent",
                              color: "var(--text-primary)",
                              padding: "5px 2px",
                              fontSize: 14,
                              fontWeight: 700,
                            }}
                          />
                          {topic.sourceLabel && (
                            <span
                              style={{
                                display: "block",
                                marginTop: 3,
                                color: "var(--text-faint)",
                                fontSize: 9,
                                textTransform: "uppercase",
                                letterSpacing: ".06em",
                              }}
                            >
                              Fuente · {topic.sourceLabel}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => rejectReviewTopic(topicIndex)}
                          title="Eliminar del temario"
                          aria-label={`Eliminar ${topic.name || "tema"}`}
                          style={{
                            display: "grid",
                            width: 36,
                            height: 36,
                            placeItems: "center",
                            border: "1px solid var(--border)",
                            background: "transparent",
                            color: "var(--danger)",
                            cursor: "pointer",
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>

                      <div
                        style={{
                          margin: "0 14px 14px 92px",
                          borderTop: "1px solid var(--border-soft)",
                          paddingTop: 8,
                        }}
                      >
                        {topic.subtopics.length > 0 && (
                          <div style={{ display: "grid" }}>
                            {topic.subtopics.map((subtopic, subtopicIndex) => (
                              <div
                                key={subtopic.key}
                                style={{
                                  display: "grid",
                                  gridTemplateColumns: "24px minmax(0, 1fr) auto",
                                  gap: 7,
                                  alignItems: "center",
                                  minHeight: 42,
                                  borderBottom: "1px solid var(--border-soft)",
                                }}
                              >
                                <span
                                  style={{
                                    color: "var(--accent)",
                                    fontSize: 13,
                                    textAlign: "center",
                                  }}
                                >
                                  ↳
                                </span>
                                <div style={{ minWidth: 0 }}>
                                  <input
                                    value={subtopic.name}
                                    placeholder="Nombre del subtema"
                                    onChange={(event) =>
                                      updateReviewSubtopic(topicIndex, subtopicIndex, {
                                        name: event.target.value,
                                      })
                                    }
                                    style={{
                                      width: "100%",
                                      border: 0,
                                      outline: 0,
                                      background: "transparent",
                                      color: "var(--text-secondary)",
                                      padding: "6px 2px",
                                      fontSize: 11,
                                    }}
                                  />
                                  {subtopic.sourceLabel && (
                                    <span
                                      style={{
                                        display: "block",
                                        marginTop: -2,
                                        color: "var(--text-faint)",
                                        fontSize: 8,
                                      }}
                                    >
                                      {subtopic.sourceLabel}
                                    </span>
                                  )}
                                </div>
                                <button
                                  onClick={() =>
                                    removeReviewSubtopic(topicIndex, subtopicIndex)
                                  }
                                  title="Eliminar subtema"
                                  aria-label={`Eliminar ${subtopic.name || "subtema"}`}
                                  style={{
                                    display: "grid",
                                    width: 30,
                                    height: 30,
                                    placeItems: "center",
                                    background: "transparent",
                                    color: "var(--text-muted)",
                                    cursor: "pointer",
                                  }}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}

                        <button
                          onClick={() => addReviewSubtopic(topicIndex)}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            marginTop: 9,
                            background: "transparent",
                            color: "var(--text-secondary)",
                            padding: "6px 2px",
                            cursor: "pointer",
                            fontSize: 10,
                            fontWeight: 700,
                          }}
                        >
                          <Plus size={13} /> Añadir subtema
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>

            <div style={{ padding: "8px 30px 22px" }}>
              <button
                onClick={addReviewTopic}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                  border: "1px dashed var(--border-strong)",
                  background: "transparent",
                  color: "var(--text-secondary)",
                  padding: "10px 12px",
                  cursor: "pointer",
                  fontSize: 10,
                  fontWeight: 800,
                }}
              >
                <Plus size={14} /> Añadir tema
              </button>
            </div>

            <footer
              style={{
                position: "sticky",
                bottom: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 18,
                borderTop: "1px solid var(--border)",
                background: "var(--surface-raised)",
                padding: "17px 30px",
              }}
            >
              <span style={{ color: "var(--text-muted)", fontSize: 10 }}>
                {reviewTopics.length} temas · {reviewTopics.reduce(
                  (total, topic) => total + topic.subtopics.length,
                  0,
                )} subtemas
              </span>
              <div style={{ display: "flex", gap: 9 }}>
                <button
                  onClick={() => void clearCurriculum()}
                  disabled={reviewSaving}
                  style={{
                    border: "1px solid var(--border)",
                    background: "transparent",
                    color: "var(--danger)",
                    padding: "10px 12px",
                    cursor: "pointer",
                  }}
                >
                  Borrar temario
                </button>
                <button
                  onClick={() => setReviewOpen(false)}
                  disabled={reviewSaving}
                  style={{
                    background: "transparent",
                    color: "var(--text-secondary)",
                    padding: "10px 12px",
                    cursor: "pointer",
                  }}
                >
                  Cancelar
                </button>
                <button
                  className="uc-primary-action"
                  onClick={() => void saveReview()}
                  disabled={reviewSaving}
                >
                  {reviewSaving ? "Guardando…" : "Confirmar temario"}
                </button>
              </div>
            </footer>
          </section>
        </div>
      )}
      {analysisOpen && selected && (
        <div className="uc-study-analysis-backdrop" role="dialog" aria-modal="true">
          <section className="uc-study-analysis-modal">
            <header className="uc-study-analysis-header">
              <div>
                <p className="uc-eyebrow">Análisis de UniCore</p>
                <h2>{selected.name}</h2>
              </div>
              {!analysisBusy && (
                <button
                  className="uc-study-analysis-close"
                  onClick={() => {
                    setAnalysisOpen(false);
                    setDiagnosticMode(false);
                  }}
                  aria-label="Cerrar análisis"
                >
                  <X size={17} />
                </button>
              )}
            </header>

            {analysisBusy ? (
              <div className="uc-study-analysis-loading">
                <div className="uc-study-analysis-progress">
                  <span style={{ width: `${Math.max(12, ((analysisStage + 1) / analysisStages.length) * 100)}%` }} />
                </div>
                <div className="uc-study-analysis-stages">
                  {analysisStages.map((stage, index) => (
                    <div
                      key={stage}
                      className={index < analysisStage ? "is-done" : index === analysisStage ? "is-current" : ""}
                    >
                      <span>{index < analysisStage ? "✓" : index + 1}</span>
                      <strong>{stage}</strong>
                    </div>
                  ))}
                </div>
                <p>UniCore usa solo fragmentos relevantes de tus materiales; no vuelve a enviar el PDF completo.</p>
              </div>
            ) : diagnosticMode && topicAnalysis?.diagnostic_questions.length === 2 ? (
              <div className="uc-study-diagnostic">
                <div className="uc-study-analysis-result-intro">
                  <p className="uc-eyebrow">Afinar análisis</p>
                  <h3>Dos preguntas breves</h3>
                  <p>La primera es de nivel medio y la segunda es más exigente. Se usarán para estimar mejor tu dominio personal.</p>
                </div>
                {topicAnalysis.diagnostic_questions.map((question, index) => (
                  <label key={`${question.level}-${index}`} className="uc-study-diagnostic-question">
                    <span>{index === 0 ? "Pregunta 1 · Nivel medio" : "Pregunta 2 · Nivel difícil"}</span>
                    <strong>{question.question}</strong>
                    <textarea
                      value={diagnosticAnswers[index]}
                      onChange={(event) =>
                        setDiagnosticAnswers((current) => {
                          const next: [string, string] = [current[0], current[1]];
                          next[index] = event.target.value;
                          return next;
                        })
                      }
                      placeholder="Responde brevemente con tus propias palabras…"
                    />
                  </label>
                ))}
                <div className="uc-study-analysis-actions">
                  <button className="uc-secondary-action" onClick={() => setDiagnosticMode(false)} disabled={diagnosticBusy}>Volver</button>
                  <button
                    className="uc-primary-action"
                    onClick={() => void submitDiagnostic()}
                    disabled={diagnosticBusy || diagnosticAnswers.some((answer) => answer.trim().length < 3)}
                  >
                    {diagnosticBusy ? "Evaluando…" : "Evaluar respuestas"}
                  </button>
                </div>
              </div>
            ) : topicAnalysis ? (
              <div className="uc-study-analysis-result">
                <div className="uc-study-analysis-ready">
                  <span><Sparkles size={18} /></span>
                  <div>
                    <p className="uc-eyebrow">Ya está listo</p>
                    <h3>UniCore terminó el análisis</h3>
                  </div>
                </div>
                <div className="uc-study-analysis-metrics">
                  <div><span>Carga de contenido</span><strong>{topicAnalysis.content_load_label}</strong></div>
                  <div><span>Complejidad</span><strong>{topicAnalysis.conceptual_complexity_label}</strong></div>
                  <div><span>Importancia recomendada</span><strong>{topicAnalysis.academic_importance_label}</strong></div>
                  <div><span>Tiempo base</span><strong>{topicAnalysis.estimated_minutes ? `${topicAnalysis.estimated_minutes} min` : "—"}</strong></div>
                </div>
                {topicAnalysis.rationale && <p className="uc-study-analysis-rationale">{topicAnalysis.rationale}</p>}
                {topicAnalysis.diagnostic_completed && (
                  <div className="uc-study-diagnostic-result">
                    <div>
                      <span>Diagnóstico personal</span>
                      <strong>{topicAnalysis.diagnostic_mastery == null ? "—" : `${Math.round(topicAnalysis.diagnostic_mastery)}%`}</strong>
                    </div>
                    {topicAnalysis.diagnostic_scores.map((score) => (
                      <p key={score.level}>
                        <strong>{score.level === "medium" ? "Nivel medio" : "Nivel difícil"}: {Math.round(score.score)}%</strong>
                        <span>{score.feedback}</span>
                      </p>
                    ))}
                  </div>
                )}
                <div className="uc-study-analysis-choice-copy">
                  <strong>¿Cómo quieres continuar?</strong>
                  <span>Puedes usar el análisis ahora o responder dos preguntas para personalizar todavía más la prioridad de estudio.</span>
                </div>
                <div className="uc-study-analysis-actions">
                  <button className="uc-primary-action" onClick={() => void useUniCoreImportance()} disabled={importanceSaving}>
                    {importanceSaving ? "Aplicando…" : "Usar análisis de UniCore"}
                  </button>
                  <button className="uc-secondary-action" onClick={() => void startDiagnostic()} disabled={diagnosticBusy}>
                    {diagnosticBusy ? "Preparando…" : topicAnalysis.diagnostic_completed ? "Repetir 2 preguntas" : "Responder 2 preguntas para afinar"}
                  </button>
                </div>
              </div>
            ) : null}
          </section>
        </div>
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