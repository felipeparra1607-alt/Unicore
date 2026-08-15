export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8766";

export type DashboardSubject = {
  id: number;
  name: string;
  xp: number;
  study_minutes: number;
  quiz_average_percentage: number | null;
  pending_task_count: number;
  next_assessment: { title: string; date: string } | null;
  grade: {
    current_grade_out_of_10: number | null;
    evaluated_weight_percentage: number;
    defined_weight_percentage: number;
    accumulated_final_percentage: number;
    target_grade: number | null;
    required_average_on_remaining: number | null;
  };
};

export type DashboardData = {
  ok: boolean;
  generated_at: string;
  view?: "global" | "subject";
  subject?: { id: number; name: string } | null;
  hero: {
    level: number;
    total_xp: number;
    current_level_start_xp: number;
    next_level_xp: number;
    xp_until_next_level: number;
    level_progress_percentage: number;
    current_streak: number;
    longest_streak: number;
  };
  metrics: {
    study_minutes_today: number;
    study_minutes_last_7_days: number;
    study_hours_last_7_days: number;
    study_session_count: number;
    quiz_attempt_count: number;
    quiz_average_percentage: number | null;
    pending_task_count: number;
    overdue_task_count: number;
    due_review_count: number;
    achievement_count: number;
  };
  daily_activity: Array<{ date: string; weekday: string; minutes: number }>;
  missions: {
    total: number;
    completed: number;
    reward_xp_available: number;
    reward_xp_earned: number;
    items: Array<{
      id: number;
      title: string;
      type: string;
      current_value: number;
      target_value: number;
      reward_xp: number;
      status: string;
    }>;
  };
  next_boss: {
    id: number;
    title: string;
    assessment_title: string | null;
    assessment_date: string | null;
    days_remaining: number | null;
    readiness_percentage: number;
    target_score_percentage: number;
    reward_xp: number;
    weak_topics: Array<unknown>;
    recommended_actions: Array<unknown>;
  } | null;
  next_assessment: {
    id: number;
    title: string;
    type: string;
    date: string;
    days_remaining: number;
    weight_percentage: number;
  } | null;
  priorities: Array<{
    id: number;
    title: string;
    subject_id: number | null;
    priority: number;
    status: string;
    due_date: string | null;
    days_remaining: number | null;
    progress_percentage: number;
  }>;
  achievements: Array<{
    title: string;
    description: string;
    unlocked_at: string;
  }>;
  subjects: DashboardSubject[];
  analytics: SubjectAnalytics | null;
  academic_risk: AcademicRisk | null;
};

export type SubjectAnalytics = {
  current: {
    study_minutes: number;
    active_days: number;
    average_focus: number | null;
    average_satisfaction: number | null;
    quiz_average_percentage: number | null;
    plan_completion_percentage: number | null;
    task_time_efficiency_percentage: number | null;
    study_efficiency_index: number | null;
  };
  previous: {
    study_minutes: number;
    active_days: number;
    average_focus: number | null;
    average_satisfaction: number | null;
    quiz_average_percentage: number | null;
  };
  trends: {
    study_minutes_change_percentage: number | null;
    active_days_change_percentage: number | null;
    focus_change_percentage: number | null;
    quiz_average_change_percentage: number | null;
  };
};

export type AcademicRisk = {
  risk_level?: string;
  risk_score?: number;
  summary?: string;
  reasons?: string[];
  recommendations?: string[];
};

export type DecisionAction = {
  type: "task" | "review" | "knowledge" | "assessment";
  source_id: number;
  subject_id: number | null;
  subject_name: string | null;
  title: string;
  score: number;
  priority: "critical" | "high" | "medium" | "low";
  suggested_minutes: number;
  allocated_minutes: number;
  reasons: string[];
  action: string;
  metadata: Record<string, unknown>;
};

export type DecisionPlan = {
  ok: boolean;
  generated_for_date: string;
  available_minutes: number;
  headline: string;
  recommended_action_count: number;
  allocated_minutes: number;
  remaining_minutes: number;
  actions: DecisionAction[];
  candidate_count: number;
  scoring_note: string;
};

export type AcademicTask = {
  id: number;
  subject_id: number | null;
  subject_name: string | null;
  title: string;
  description: string | null;
  task_type: string;
  status: string;
  priority: number;
  due_date: string | null;
  days_until_due: number | null;
  is_overdue: boolean;
  estimated_minutes: number | null;
  spent_minutes: number;
  remaining_minutes: number | null;
  progress_percentage: number;
  notes: string | null;
};

export type TasksData = {
  ok: boolean;
  count: number;
  tasks: Array<{
    task: AcademicTask;
    planning: {
      planning_score: number;
      urgency_level?: string;
      reasons?: string[];
    };
  }>;
};

export type StudySession = {
  id: number;
  subject_id: number;
  subject_name: string | null;
  session_date: string;
  duration_minutes: number;
  activity_type: string;
  topic: string | null;
  completed_plan: boolean;
  focus_rating: number | null;
  difficulty_rating: number | null;
  satisfaction_rating: number | null;
};

export type QuizAttempt = {
  id: number;
  subject_id: number;
  topic: string;
  study_mode: string;
  difficulty: string;
  total_questions: number;
  correct_answers: number | null;
  score_percentage: number | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
};

export type StudyData = {
  ok: boolean;
  subject: { id: number; name: string };
  available_study_modes: string[];
  summary: {
    study_session_count: number;
    total_study_minutes: number;
    quiz_attempt_count: number;
    completed_quiz_count: number;
    quiz_average_percentage: number | null;
  };
  recent_attempts: QuizAttempt[];
  recent_study_sessions: StudySession[];
  reviews: {
    ok: boolean;
    count: number;
    due_count: number;
    reviews: Array<{
      id: number;
      topic: string;
      status: string;
      next_review_at: string;
      priority: number;
    }>;
  } | null;
};

export type KnowledgeConcept = {
  id: number;
  subject_id: number;
  name: string;
  mastery_percentage: number | null;
  status: "strong" | "developing" | "weak" | "unassessed";
  evidence_count: number;
  assessed_evidence_count: number;
  exposure_minutes: number;
  last_evidence_at: string | null;
};

export type KnowledgeData = {
  ok: boolean;
  subject: { id: number; name: string };
  summary: {
    concept_count: number;
    assessed_concept_count: number;
    overall_mastery_percentage: number | null;
    strong_count: number;
    developing_count: number;
    weak_count: number;
    unassessed_count: number;
  };
  priority_concepts: KnowledgeConcept[];
  concepts: KnowledgeConcept[];
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.error ??
        payload?.message ??
        `La API de UniCore respondió con ${response.status}.`,
    );
  }
  return response.json() as Promise<T>;
}

export function getDashboard(subjectId?: number): Promise<DashboardData> {
  const params = subjectId == null ? "" : `?subject_id=${subjectId}`;
  return requestJson<DashboardData>(`/api/dashboard${params}`);
}

export function getDecisionPlan(
  availableMinutes = 60,
  maximumActions = 3,
  subjectId?: number,
): Promise<DecisionPlan> {
  const params = new URLSearchParams({
    available_minutes: String(availableMinutes),
    maximum_actions: String(maximumActions),
  });
  if (subjectId != null) {
    params.set("subject_id", String(subjectId));
  }
  return requestJson<DecisionPlan>(`/api/decision-plan?${params.toString()}`);
}

export function getTasks(subjectId?: number): Promise<TasksData> {
  const params = subjectId == null ? "" : `?subject_id=${subjectId}`;
  return requestJson<TasksData>(`/api/tasks${params}`);
}

export type AcademicLanguage = "English" | "Spanish";
export type NewSubjectInput = {
  name: string;
  academic_language: AcademicLanguage;
  academic_year?: string | null;
  description?: string | null;
};
export function createSubject(
  input: NewSubjectInput,
): Promise<{
  ok: boolean;
  subject: {
    id: number;
    name: string;
    academic_language: AcademicLanguage;
    academic_year: string | null;
    description: string | null;
  };
}> {
  return requestJson("/api/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type NewTaskInput = {
  title: string;
  subject_id?: number | null;
  description?: string | null;
  task_type: string;
  priority: number;
  due_date?: string | null;
  estimated_minutes?: number | null;
  notes?: string | null;
};
export function createTask(
  input: NewTaskInput,
): Promise<{ ok: boolean; task: AcademicTask }> {
  return requestJson("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function updateTask(
  taskId: number,
  input: { status?: string; progress_percentage?: number },
): Promise<{ ok: boolean; task: AcademicTask }> {
  return requestJson(`/api/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function setGradeGoal(
  subjectId: number,
  targetGrade: number,
): Promise<{
  ok: boolean;
  goal: {
    subject_id: number;
    subject_name: string;
    target_grade: number;
    maximum_grade: number;
  };
}> {
  return requestJson(`/api/subjects/${subjectId}/grade-goal`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_grade: targetGrade, maximum_grade: 10 }),
  });
}

export function getStudy(subjectId: number): Promise<StudyData> {
  return requestJson<StudyData>(`/api/study?subject_id=${subjectId}`);
}

export function getKnowledge(subjectId: number): Promise<KnowledgeData> {
  return requestJson<KnowledgeData>(`/api/subjects/${subjectId}/knowledge`);
}

export type ProfessorData = {
  ok: boolean;
  subject: {
    id: number;
    name: string;
    academic_language?: "English" | "Spanish";
    academic_language_configured?: boolean;
  };
  professors: Array<{
    id: number;
    name: string;
    public_profile_url: string | null;
    notes: string | null;
  }>;
  preferences: Array<{
    id: number;
    professor_id: number;
    professor_name: string | null;
    category: string;
    preference: string;
    importance: number;
    source_type: string;
    source_reference: string | null;
    confidence: number;
  }>;
  rubric_criteria: Array<{
    id: number;
    professor_id: number | null;
    assessment_id: number | null;
    title: string;
    description: string | null;
    weight_percentage: number | null;
    maximum_points: number | null;
    notes: string | null;
  }>;
};

export type SubjectDocumentsData = {
  ok: boolean;
  subject: { id: number; name: string };
  count: number;
  documents: Array<{
    id: number;
    title: string;
    file_type: string | null;
    document_type: string | null;
    material_type: MaterialType;
    curriculum_unit_id: number | null;
    curriculum_unit_name: string | null;
    academic_year: string | null;
    semester: string | null;
    professor_id: number | null;
    subject_id: number | null;
    has_extracted_text: boolean;
    character_count: number;
    chunk_count: number;
    created_at: string | null;
    processing_status?: "processing" | "ready" | "error";
    processing_stage?: string | null;
    processing_error?: string | null;
  }>;
};

export type MaterialType =
  | "official_unit"
  | "class_notes"
  | "personal_summary"
  | "assignment"
  | "required_reading"
  | "supplementary"
  | "past_exam"
  | "rubric"
  | "other";

export type DocumentContent = {
  ok: boolean;
  document: SubjectDocumentsData["documents"][number];
  content: string;
};

export function getSubjectProfessor(subjectId: number): Promise<ProfessorData> {
  return requestJson<ProfessorData>(`/api/subjects/${subjectId}/professor`);
}

export function getSubjectDocuments(
  subjectId: number,
): Promise<SubjectDocumentsData> {
  return requestJson<SubjectDocumentsData>(
    `/api/subjects/${subjectId}/documents`,
  );
}

export async function uploadSubjectMaterial(
  subjectId: number,
  file: File,
  _metadata: {
    document_type?: string;
    material_type?: MaterialType;
    curriculum_unit_id?: number | null;
    academic_year?: string | null;
    semester?: string | null;
    professor_id?: number | null;
  } = {},
): Promise<{
  ok: boolean;
  duplicate: boolean;
  message: string;
  document: SubjectDocumentsData["documents"][number];
}> {
  try {
    const query = new URLSearchParams({ file_name: file.name });
    if (_metadata.material_type)
      query.set("material_type", _metadata.material_type);
    if (_metadata.curriculum_unit_id != null)
      query.set("curriculum_unit_id", String(_metadata.curriculum_unit_id));
    return await requestJson(
      `/api/subjects/${subjectId}/materials?${query.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      },
    );
  } catch (error) {
    if (error instanceof TypeError)
      throw new Error("No se pudo conectar con UniCore durante la subida.");
    throw error;
  }
}

export function updateDocumentClassification(
  documentId: number,
  classification: {
    material_type: MaterialType;
    curriculum_unit_id: number | null;
  },
): Promise<{
  ok: boolean;
  changed: boolean;
  embeddings_reused: boolean;
  document: SubjectDocumentsData["documents"][number];
}> {
  return requestJson(`/api/documents/${documentId}/classification`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(classification),
  });
}

export function deleteSubjectMaterial(
  documentId: number,
): Promise<{ ok: boolean; document_id: number }> {
  return requestJson(`/api/documents/${documentId}`, { method: "DELETE" });
}

export function rebuildSubjectCurriculum(
  subjectId: number,
): Promise<{
  ok: boolean;
  document_count: number;
  processed_count: number;
  embeddings_reused: boolean;
}> {
  return requestJson(`/api/subjects/${subjectId}/curriculum/rebuild`, {
    method: "POST",
  });
}

export function retryDocumentProcessing(
  documentId: number,
): Promise<{ ok: boolean; message: string }> {
  return requestJson(`/api/documents/${documentId}/retry-processing`, {
    method: "POST",
  });
}

export function getDocumentContent(
  documentId: number,
): Promise<DocumentContent> {
  return requestJson(`/api/documents/${documentId}`);
}

export function getDocumentFileUrl(documentId: number): string {
  return `${API_BASE_URL}/api/documents/${documentId}/file`;
}

export type Assessment = {
  id: number;
  subject_id: number;
  subject_name: string | null;
  title: string;
  assessment_type: string;
  assessment_date: string | null;
  weight_percentage: number | null;
  status: string;
};

export function getAssessments(): Promise<{
  ok: boolean;
  assessments: Assessment[];
}> {
  return requestJson("/api/assessments");
}

export type AgentSource = {
  source_number: number;
  document_id: number;
  document_title: string;
  source_label: string | null;
};
export type ConversationMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: AgentSource[];
  created_at: string;
};
export type ConversationSummary = {
  id: string;
  title: string;
  context_type: "general" | "subject" | "document" | "work_session";
  subject_id: number | null;
  document_id: number | null;
  summary_available: boolean;
  message_count: number;
  created_at: string;
  updated_at: string;
};
export type ConversationDetail = ConversationSummary & {
  messages: ConversationMessage[];
};
export type TokenUsage = {
  available: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
};
export type AgentResponse = {
  ok: boolean;
  answer: string | null;
  status: string;
  conversation_id: string;
  error: string | null;
  sources: AgentSource[];
  usage?: TokenUsage;
  context_usage: {
    used: boolean;
    top_k: number;
    source_count: number;
    context_characters: number;
    subject_filtered: boolean;
    document_filtered: boolean;
  };
  job?: { status: string; kind: string; objective: string; created_at: string };
};

export type AgentMessageOptions = {
  conversationId?: string;
  subjectId?: number | null;
  documentId?: number | null;
  contextType?: "general" | "subject" | "document" | "work_session";
  workContext?: Record<string, unknown>;
};

export function sendAgentMessage(
  message: string,
  options: AgentMessageOptions = {},
): Promise<AgentResponse> {
  return requestJson<AgentResponse>("/api/agent/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: options.conversationId,
      subject_id: options.subjectId ?? null,
      document_id: options.documentId ?? null,
      context_type: options.contextType,
      work_context: options.workContext,
    }),
  });
}

export type PromptBuildResponse = {
  ok: boolean;
  prompt: string;
  sources: AgentSource[];
  context: {
    subject_id: number | null;
    subject_name: string | null;
    task_id: number | null;
    task_title: string | null;
    document_id: number | null;
    document_title: string | null;
    professor_criteria_count: number;
    rubric_criteria_count: number;
  };
  retrieval: {
    top_k: number;
    source_count: number;
    context_characters: number;
    subject_filtered: boolean;
    document_filtered: boolean;
    provider_called: boolean;
    historical_source_count?: number;
  };
  context_selection?: {
    professor: boolean;
    rubric: boolean;
    academic_memory: boolean;
    improvements: boolean;
    strengths: boolean;
    estimated_load: "Bajo" | "Medio" | "Alto";
  };
};

export function buildAcademicPrompt(input: {
  objective: string;
  subject_id?: number | null;
  task_id?: number | null;
  document_id?: number | null;
  include_professor?: boolean;
  include_rubric?: boolean;
  include_academic_memory?: boolean;
  include_improvements?: boolean;
  include_strengths?: boolean;
}): Promise<PromptBuildResponse> {
  return requestJson<PromptBuildResponse>("/api/prompts/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type StudyExplanationResponse = {
  ok: boolean;
  conversation_id: string;
  topic: string;
  explanation: string;
  sources: AgentSource[];
  curriculum_item_id?: number | null;
  retrieval: {
    top_k: number;
    source_count: number;
    context_characters: number;
    document_filtered: boolean;
    curriculum_filtered?: boolean;
  };
  usage?: TokenUsage;
  cache?: { hit: boolean; updated_at?: string };
};

export type Flashcard = {
  id: number;
  subject_id: number;
  topic: string;
  question: string;
  correct_answer: string;
  sources: AgentSource[];
  status: string;
  repetition_count: number;
  interval_days: number;
  leitner_box: number;
  leitner_name: string;
  cognitive_level: string;
  concept_name: string | null;
  last_reviewed_at?: string | null;
  next_review_at?: string | null;
  subject_name?: string | null;
};

export type FlashcardDraft = {
  id: number;
  subject_id: number;
  document_id: number | null;
  topic: string;
  question: string;
  correct_answer: string;
  sources: AgentSource[];
  cognitive_level: string;
  answer_mode: string;
  probable_duplicate: boolean;
  status: string;
  rejection_reason: string | null;
};

export type FlashcardBatchResponse = {
  ok: boolean;
  topic: string;
  cards: Flashcard[];
  drafts?: FlashcardDraft[];
  reused: boolean;
  provider_called: boolean;
  source_count: number;
  usage?: TokenUsage;
};

export function startExplanation(input: {
  subject_id: number;
  curriculum_item_id: number;
  topic?: string;
  difficulty?: string;
}): Promise<StudyExplanationResponse> {
  return requestJson<StudyExplanationResponse>("/api/study/explanations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function startFlashcards(input: {
  subject_id: number;
  curriculum_item_id: number;
  topic?: string;
  item_count?: number;
  difficulty?: string;
  cognitive_level?: string;
  answer_mode?: string;
}): Promise<FlashcardBatchResponse> {
  return requestJson<FlashcardBatchResponse>("/api/study/flashcards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function rateFlashcard(
  reviewItemId: number,
  rating: "difficult" | "good" | "easy",
): Promise<{ ok: boolean }> {
  return requestJson(`/api/study/flashcards/${reviewItemId}/rate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
}

export function rejectFlashcard(
  reviewItemId: number,
  rejectionReason?: string,
): Promise<{ ok: boolean; rejected: boolean }> {
  return requestJson(`/api/study/flashcards/${reviewItemId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rejection_reason: rejectionReason }),
  });
}

export function decideFlashcardDraft(
  draftId: number,
  accept: boolean,
  rejectionReason?: string,
): Promise<{ ok: boolean; accepted: boolean; card?: Flashcard }> {
  return requestJson(`/api/study/flashcard-drafts/${draftId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accept, rejection_reason: rejectionReason }),
  });
}

export function moveFlashcard(
  reviewItemId: number,
  targetBox?: number,
  reviewEarlier = false,
): Promise<{ ok: boolean; card: Flashcard }> {
  return requestJson(`/api/study/flashcards/${reviewItemId}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_box: targetBox,
      review_earlier: reviewEarlier,
    }),
  });
}

export type WrittenEvaluation = {
  id: number;
  overall_score: number;
  dimensions: Array<{ name: string; score: number; feedback: string }>;
  errors: string[];
  improvements: string[];
  example_improvement: string | null;
};
export function evaluateFlashcardAnswer(
  reviewItemId: number,
  answer: string,
): Promise<{ ok: boolean; evaluation: WrittenEvaluation; usage: TokenUsage }> {
  return requestJson(`/api/study/flashcards/${reviewItemId}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
}

export function getConversations(): Promise<{
  ok: boolean;
  count: number;
  conversations: ConversationSummary[];
}> {
  return requestJson("/api/conversations");
}

export function getConversation(
  conversationId: string,
): Promise<{ ok: boolean; conversation: ConversationDetail }> {
  return requestJson(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
  );
}

export function deleteConversation(
  conversationId: string,
): Promise<{ ok: boolean }> {
  return requestJson(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    { method: "DELETE" },
  );
}

export type StudySessionInput = {
  subject_id: number;
  duration_minutes: number;
  activity_type:
    | "quiz"
    | "flashcards"
    | "quick_review"
    | "summary"
    | "explanation"
    | "reading"
    | "class_notes"
    | "project"
    | "other";
  session_date?: string;
  topic?: string | null;
  notes?: string | null;
  planned_minutes?: number | null;
  completed_plan?: boolean;
  focus_rating?: number | null;
  difficulty_rating?: number | null;
  satisfaction_rating?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
};

export function createStudySession(
  input: StudySessionInput,
): Promise<{ ok: boolean; study_session: StudySession }> {
  return requestJson("/api/study-sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type TaskFileProposal = {
  title: string | null;
  subject_id: number | null;
  task_type: string | null;
  priority: number | null;
  due_date: string | null;
  estimated_minutes: number | null;
  description: string | null;
  notes: string | null;
  detected_requirements: string[] | null;
  evidence: Record<string, string | null> | null;
};

export type TaskFileAnalysis = {
  ok: boolean;
  file: { name: string; extension: string; character_count: number };
  proposal: TaskFileProposal;
  subjects: Array<{ id: number; name: string }>;
  analysis_mode: "read_only_agent";
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(
        result.includes(",") ? result.slice(result.indexOf(",") + 1) : result,
      );
    };
    reader.onerror = () =>
      reject(new Error("No se pudo leer el archivo seleccionado."));
    reader.readAsDataURL(file);
  });
}

export async function analyzeTaskFile(
  file: File,
  subjectId?: number | null,
): Promise<TaskFileAnalysis> {
  const contentBase64 = await fileToBase64(file);
  return requestJson<TaskFileAnalysis>("/api/task-files/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_name: file.name,
      content_base64: contentBase64,
      subject_id: subjectId ?? null,
    }),
  });
}

export type AIUsageData = {
  ok: boolean;
  today: number;
  this_week: number;
  daily: Array<{
    date: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    request_count: number;
  }>;
  by_subject: Array<{
    subject_id: number | null;
    subject_name: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    request_count: number;
  }>;
};
export function getAIUsage(days = 14): Promise<AIUsageData> {
  return requestJson(`/api/ai-usage?days=${days}`);
}

export type LeitnerData = {
  ok: boolean;
  boxes: Array<{
    box: number;
    name: string;
    interval_days: number;
    count: number;
    due_count: number;
  }>;
  cards: Flashcard[];
};
export function getLeitner(subjectId?: number | null): Promise<LeitnerData> {
  return requestJson(
    `/api/leitner${subjectId == null ? "" : `?subject_id=${subjectId}`}`,
  );
}

export type StudentDimension = {
  dimension: string;
  score: number;
  trend: number;
  status: "weakness" | "improving" | "stable" | "strength";
  evidence_count: number;
  last_observed_at: string;
};
export type StudentModelData = {
  ok: boolean;
  dimensions: StudentDimension[];
  strengths: StudentDimension[];
  areas_for_improvement: StudentDimension[];
};
export function getStudentModel(
  subjectId?: number | null,
): Promise<StudentModelData> {
  return requestJson(
    `/api/student-model${subjectId == null ? "" : `?subject_id=${subjectId}`}`,
  );
}

export type ProfessorOverview = {
  id: number;
  name: string;
  notes: string | null;
  subjects: Array<{ id: number; name: string }>;
  criteria_count: number;
  transcript_count: number;
};
export function getProfessors(): Promise<{
  ok: boolean;
  professors: ProfessorOverview[];
}> {
  return requestJson("/api/professors");
}
export function createProfessor(input: {
  subject_id: number;
  name: string;
  notes?: string | null;
}): Promise<{
  ok: boolean;
  professor: { id: number; name: string; notes: string | null };
}> {
  return requestJson("/api/professors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export function assignProfessor(
  subjectId: number,
  input: { professor_id?: number; name?: string; notes?: string | null },
): Promise<{
  ok: boolean;
  professor: { id: number; name: string; notes?: string | null };
}> {
  return requestJson(`/api/subjects/${subjectId}/professor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export function addProfessorCriterion(
  professorId: number,
  subjectId: number,
  text: string,
  importance: number,
): Promise<{ ok: boolean }> {
  return requestJson(`/api/professors/${professorId}/criteria`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id: subjectId, text, importance }),
  });
}
export function setAcademicLanguage(
  subjectId: number,
  academicLanguage: "English" | "Spanish",
): Promise<{ ok: boolean }> {
  return requestJson(`/api/subjects/${subjectId}/academic-language`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ academic_language: academicLanguage }),
  });
}

export type AcademicMapData = {
  ok: boolean;
  concepts: Array<{
    id: number;
    name: string;
    subject_id: number;
    subject_name: string | null;
    academic_year: string | null;
    curriculum_type?: "topic" | "subtopic" | null;
    global_concept?: string | null;
    mastery: "mastered" | "consolidating" | "not_mastered" | "unassessed";
    evidence_count: number;
  }>;
  connections: Array<{
    id: number;
    source: string;
    target: string;
    relationship: string;
    source_type: string;
  }>;
  student_model: StudentModelData;
};
export function getAcademicMap(): Promise<AcademicMapData> {
  return requestJson("/api/academic-map");
}

export type CurriculumStatus =
  "not_studied" | "learning" | "consolidating" | "mastered";
export type CurriculumSource = {
  document_id: number;
  title: string;
  file_type: string | null;
  material_type?: MaterialType;
  source_label: string | null;
};
export type CurriculumItemBase = {
  id: number;
  name: string;
  type: "unit" | "topic" | "subtopic";
  source: "automatic" | "manual";
  manually_locked: boolean;
  status: CurriculumStatus;
  sources: CurriculumSource[];
  also_seen_in: Array<{
    subject_id: number;
    subject_name: string;
    concept_name: string;
  }>;
  merged_item_ids?: number[];
};
export type CurriculumSubtopic = CurriculumItemBase & { type: "subtopic" };
export type CurriculumTopic = CurriculumItemBase & {
  type: "topic";
  subtopics: CurriculumSubtopic[];
};
export type CurriculumUnit = CurriculumItemBase & {
  type: "unit";
  topics: CurriculumTopic[];
  topic_count: number;
  worked_topic_count: number;
};
export type CurriculumData = {
  ok: boolean;
  subject: {
    id: number;
    name: string;
    academic_language: AcademicLanguage;
    academic_language_configured: boolean;
  };
  units: CurriculumUnit[];
  item_count: number;
  pending_document_count: number;
};
export function getCurriculum(subjectId: number): Promise<CurriculumData> {
  return requestJson(`/api/subjects/${subjectId}/curriculum`);
}

export type JobSummary = {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  kind: string;
  objective: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};
export type JobDetail = JobSummary & {
  context_summary: string;
  expected_output: string;
  result: string | null;
  error: string | null;
};
export function getJobs(
  status?: string,
): Promise<{ ok: boolean; count: number; jobs: JobSummary[] }> {
  const params = status ? `?status=${status}` : "";
  return requestJson(`/api/jobs${params}`);
}
export function getJob(id: string): Promise<{ ok: boolean; job: JobDetail }> {
  return requestJson(`/api/jobs/${encodeURIComponent(id)}`);
}
