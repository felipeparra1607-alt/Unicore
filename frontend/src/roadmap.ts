export type RoadmapStatus = "Siguiente" | "Próximamente" | "Más adelante" | "Idea";
export type RoadmapItem = { title: string; description: string; status: RoadmapStatus; area: string };

export const roadmapItems: RoadmapItem[] = [
  { title: "Quiz avanzado", status: "Próximamente", area: "Evaluación", description: "Evaluaciones temporizadas con preguntas adaptadas al temario y al profesor." },
  { title: "Transcripción automática de clases", status: "Próximamente", area: "Clases", description: "Conectar audio/transcription API y analizar el contenido de las clases." },
  { title: "Análisis del profesor desde transcripciones", status: "Próximamente", area: "Profesor", description: "Detectar énfasis, preferencias, errores advertidos y posibles pistas de evaluación." },
  { title: "Recursos externos", status: "Próximamente", area: "Estudio", description: "Buscar casos, ejemplos y recursos externos relacionados con el tema actual." },
  { title: "Gamificación académica", status: "Más adelante", area: "Experiencia", description: "Sistema opcional de progreso, niveles y recompensas." },
];
