import React from "react";
import Dashboard from "./components/Dashboard";
import Layout, { SectionId } from "./components/Layout";
import SubjectsPage from "./pages/SubjectsPage";
import SubjectDetailPage from "./pages/SubjectDetailPage";

const sectionCopy: Record<Exclude<SectionId, "dashboard">, { eyebrow: string; title: string; body: string }> = {
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
  knowledge: {
    eyebrow: "Conocimiento",
    title: "Mapa de dominio académico",
    body: "Esta vista visualizará el Knowledge Map con conceptos dominados, parciales, débiles y pendientes de evaluación.",
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
};

export default function App() {
  const [section, setSection] = React.useState<SectionId>("dashboard");
  const [selectedSubjectId, setSelectedSubjectId] = React.useState<number | null>(null);

  const selectSection = (nextSection: SectionId) => {
    setSection(nextSection);
    if (nextSection !== "subjects") setSelectedSubjectId(null);
  };

  return (
    <Layout active={section} onSection={selectSection}>
      {section === "dashboard" ? (
        <Dashboard />
      ) : section === "subjects" ? (
        selectedSubjectId == null ? (
          <SubjectsPage onSelect={setSelectedSubjectId} />
        ) : (
          <SubjectDetailPage subjectId={selectedSubjectId} onBack={() => setSelectedSubjectId(null)} />
        )
      ) : (
        <section className="uc-page-shell uc-placeholder">
          <p className="uc-eyebrow">{sectionCopy[section].eyebrow}</p>
          <h1>{sectionCopy[section].title}</h1>
          <p>{sectionCopy[section].body}</p>
          <div className="uc-placeholder-rule" />
          <span>Se construirá sobre el backend real en los siguientes bloques.</span>
        </section>
      )}
    </Layout>
  );
}
