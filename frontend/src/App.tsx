import React from "react";
import Dashboard from "./components/Dashboard";
import Layout, { SectionId } from "./components/Layout";
import type { SearchDestination } from "./components/GlobalSearch";
import SubjectsPage from "./pages/SubjectsPage";
import SubjectDetailPage from "./pages/SubjectDetailPage";
import TasksPage from "./pages/TasksPage";
import StudyPage from "./pages/StudyPage";
import EvaluationPage from "./pages/EvaluationPage";
import KnowledgePage from "./pages/KnowledgePage";
import AgentPage from "./pages/AgentPage";
import JobsPage from "./pages/JobsPage";
import SettingsPage from "./pages/SettingsPage";
import GoalsPage from "./pages/GoalsPage";
import WorkSessionPage from "./pages/WorkSessionPage";
import WorkBlockDialog from "./components/WorkBlockDialog";
import ProfessorsPage from "./pages/ProfessorsPage";
import TranscriptsPage from "./pages/TranscriptsPage";
import UpcomingPage from "./pages/UpcomingPage";
import SessionBuilderPage from "./pages/SessionBuilderPage";
import type { DecisionAction } from "./api";
import {
  normalizeStoredWorkSession,
  WORK_SESSION_STORAGE_KEY,
  type LegacyWorkSession,
  type StoredWorkSession,
} from "./workSession";

const sectionCopy: Record<
  Exclude<SectionId, "dashboard">,
  { eyebrow: string; title: string; body: string }
> = {
  subjects: {
    eyebrow: "Asignaturas",
    title: "Centro académico por asignatura",
    body: "Aquí conectaremos notas, evaluaciones, tareas, material, sesiones y Knowledge Map de cada asignatura.",
  },
  tasks: {
    eyebrow: "Tareas",
    title: "Prioridades, fechas y progreso",
    body: "Esta vista se conectará al Decision Engine y a las Tools de tareas para planificar y ejecutar trabajo real.",
  },
  study: {
    eyebrow: "Estudio",
    title: "Sesiones, quizzes y constancia",
    body: "Aquí vivirán las sesiones de estudio, los modos de aprendizaje, los quizzes y el historial de actividad.",
  },
  evaluation: {
    eyebrow: "Evaluación",
    title: "Práctica académica",
    body: "Flashcards, Leitner y configuración de Quiz basados en el temario real.",
  },
  goals: {
    eyebrow: "Objetivos",
    title: "Progreso académico",
    body: "Define el rumbo de tu trabajo académico.",
  },
  knowledge: {
    eyebrow: "Conocimiento",
    title: "Mapa de dominio académico",
    body: "Esta vista visualizará el Knowledge Map con conceptos dominados, parciales, débiles y pendientes de evaluación.",
  },
  professors: {
    eyebrow: "Profesores",
    title: "Professor Intelligence",
    body: "Criterios, evidencias y asignaturas asociadas.",
  },
  transcripts: {
    eyebrow: "Transcripciones",
    title: "Memoria de clase",
    body: "Transcripciones manuales hoy y captura de audio en una integración futura.",
  },
  agent: {
    eyebrow: "UniCore Agent",
    title: "Asistencia contextual, no un chat wrapper",
    body: "El Agent estará disponible con el contexto académico de la aplicación, sin convertir toda la experiencia en una copia de ChatGPT.",
  },
  jobs: {
    eyebrow: "Jobs",
    title: "Análisis largos en segundo plano",
    body: "Aquí aparecerán los análisis profundos, su estado y sus resultados cuando conectemos Handoff + Worker.",
  },
  settings: {
    eyebrow: "Ajustes",
    title: "Preferencias de UniCore",
    body: "Configura el tema y las preferencias locales de tu espacio académico.",
  },
  upcoming: {
    eyebrow: "Hoja de ruta",
    title: "Próximamente",
    body: "Capacidades previstas para futuras versiones de UniCore.",
  },
};

export default function App() {
  const [section, setSection] = React.useState<SectionId>("dashboard");
  const [selectedSubjectId, setSelectedSubjectId] = React.useState<
    number | null
  >(null);
  const [focusedTaskId, setFocusedTaskId] = React.useState<number | null>(null);
  const [sessionBuilder, setSessionBuilder] = React.useState(false);
  const [studyFocusMode, setStudyFocusMode] = React.useState(false);
  const [pendingWorkAction, setPendingWorkAction] =
    React.useState<DecisionAction | null>(null);
  const [agentLaunchContext, setAgentLaunchContext] = React.useState<{
    subjectId: number;
    subjectName: string;
    documentId?: number;
    documentTitle?: string;
    topic?: string;
    explanation?: string;
    sources?: unknown[];
  } | null>(null);
  const [studyLaunchContext, setStudyLaunchContext] = React.useState<{
    subjectId: number;
    subjectName: string;
    documentId?: number;
    topic?: string;
  } | null>(null);
  const [workSession, setWorkSession] =
    React.useState<StoredWorkSession | null>(() => {
      try {
        const stored = window.localStorage.getItem(WORK_SESSION_STORAGE_KEY);
        return stored
          ? normalizeStoredWorkSession(
              JSON.parse(stored) as StoredWorkSession | LegacyWorkSession,
            )
          : null;
      } catch {
        window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
        return null;
      }
    });

  const selectSection = (nextSection: SectionId) => {
    if (workSession) {
      const leave = window.confirm(
        "Hay un bloque activo. Si cambias de sección se cerrará sin registrar. ¿Quieres salir del modo foco?",
      );
      if (!leave) return;
      window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
      setWorkSession(null);
    }
    if (nextSection === "agent") setAgentLaunchContext(null);
    if (nextSection === "study") setStudyLaunchContext(null);
    if (sessionBuilder) {
      setSessionBuilder(false);
      window.history.pushState({}, "", "/");
    }
    if (nextSection !== "study") setStudyFocusMode(false);
    setSection(nextSection);
    if (nextSection !== "subjects") setSelectedSubjectId(null);
  };

  const handleSearchNavigate = (destination: SearchDestination) => {
    if (workSession) {
      window.alert(
        "Hay un bloque de trabajo activo. Finalízalo antes de abrir otro resultado.",
      );
      return;
    }
    if (destination.kind === "subject") {
      setSelectedSubjectId(destination.subjectId);
      setSection("subjects");
      return;
    }
    setSelectedSubjectId(null);
    setSection(destination.kind === "task" ? "tasks" : "knowledge");
  };

  const updateWorkSession = React.useCallback(
    (nextSession: StoredWorkSession) => {
      setWorkSession(nextSession);
      window.localStorage.setItem(
        WORK_SESSION_STORAGE_KEY,
        JSON.stringify(nextSession),
      );
    },
    [],
  );

  const startWorkSession = (durationMinutes: number) => {
    if (!pendingWorkAction) return;
    startWorkPlan([pendingWorkAction], durationMinutes);
    setPendingWorkAction(null);
  };

  const startWorkPlan = (
    actions: DecisionAction[],
    durationMinutes: number,
  ) => {
    if (!actions.length) return;
    const remainingMs = durationMinutes * 60_000;
    const actionRemainingMs = Math.min(
      remainingMs,
      actions[0].allocated_minutes * 60_000,
    );
    const nextSession: StoredWorkSession = {
      actions,
      durationMinutes,
      startedAt: new Date().toISOString(),
      deadline: Date.now() + remainingMs,
      remainingMs,
      running: true,
      activeIndex: 0,
      actionDeadline: Date.now() + actionRemainingMs,
      actionRemainingMs,
    };
    updateWorkSession(nextSession);
  };

  const closeWorkSession = () => {
    window.localStorage.removeItem(WORK_SESSION_STORAGE_KEY);
    setWorkSession(null);
    setSection("dashboard");
  };

  return (
    <Layout
      active={section}
      onSection={selectSection}
      onSearchNavigate={handleSearchNavigate}
      focusMode={Boolean(workSession) || studyFocusMode}
    >
      {workSession ? (
        <WorkSessionPage
          session={workSession}
          onChange={updateWorkSession}
          onClose={closeWorkSession}
        />
      ) : sessionBuilder ? (
        <SessionBuilderPage
          onBack={() => { setSessionBuilder(false); setSection("tasks"); window.history.pushState({}, "", "/"); }}
          onStart={(actions, duration) => { setSessionBuilder(false); startWorkPlan(actions, duration); }}
        />
      ) : section === "dashboard" ? (
        <Dashboard
          onOpenSubjects={() => selectSection("subjects")}
          onOpenTasks={() => selectSection("tasks")}
          onOpenTask={(taskId) => { setFocusedTaskId(taskId); setSection("tasks"); }}
        />
      ) : section === "subjects" ? (
        selectedSubjectId == null ? (
          <SubjectsPage onSelect={setSelectedSubjectId} />
        ) : (
          <SubjectDetailPage
            subjectId={selectedSubjectId}
            onBack={() => setSelectedSubjectId(null)}
            onNavigate={selectSection}
            onStartStudy={(subjectName) => {
              setStudyLaunchContext({
                subjectId: selectedSubjectId,
                subjectName,
              });
              setSection("study");
            }}
          />
        )
      ) : section === "tasks" ? (
        <TasksPage focusedTaskId={focusedTaskId} onStartSession={() => { setSessionBuilder(true); window.history.pushState({}, "", "/session/new"); }} />
      ) : section === "study" ? (
        <StudyPage
          launchContext={studyLaunchContext}
          onFocusChange={setStudyFocusMode}
          onConfigureSubject={(subjectId) => {
            setSelectedSubjectId(subjectId);
            setSection("subjects");
          }}
        />
      ) : section === "evaluation" ? (
        <EvaluationPage
          onConfigureSubject={(subjectId) => {
            setSelectedSubjectId(subjectId);
            setSection("subjects");
          }}
        />
      ) : section === "goals" ? (
        <GoalsPage />
      ) : section === "knowledge" ? (
        <KnowledgePage />
      ) : section === "professors" ? (
        <ProfessorsPage />
      ) : section === "transcripts" ? (
        <TranscriptsPage />
      ) : section === "agent" ? (
        <AgentPage launchContext={agentLaunchContext} />
      ) : section === "jobs" ? (
        <JobsPage />
      ) : section === "settings" ? (
        <SettingsPage />
      ) : section === "upcoming" ? (
        <UpcomingPage />
      ) : (
        <section className="uc-page-shell uc-placeholder">
          <p className="uc-eyebrow">
            {sectionCopy[section as keyof typeof sectionCopy].eyebrow}
          </p>
          <h1>{sectionCopy[section as keyof typeof sectionCopy].title}</h1>
          <p>{sectionCopy[section as keyof typeof sectionCopy].body}</p>
          <div className="uc-placeholder-rule" />
          <span>
            Se construirá sobre el backend real en los siguientes bloques.
          </span>
        </section>
      )}
      {pendingWorkAction && (
        <WorkBlockDialog
          action={pendingWorkAction}
          onClose={() => setPendingWorkAction(null)}
          onStart={startWorkSession}
        />
      )}
    </Layout>
  );
}
