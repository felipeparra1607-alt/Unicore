export const API_BASE_URL = "http://127.0.0.1:8766";

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
  achievements: Array<{ title: string; description: string; unlocked_at: string }>;
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
  previous: { study_minutes: number; active_days: number; average_focus: number | null; average_satisfaction: number | null; quiz_average_percentage: number | null };
  trends: { study_minutes_change_percentage: number | null; active_days_change_percentage: number | null; focus_change_percentage: number | null; quiz_average_change_percentage: number | null };
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
  id: number; subject_id: number | null; subject_name: string | null; title: string;
  description: string | null; task_type: string; status: string; priority: number;
  due_date: string | null; days_until_due: number | null; is_overdue: boolean;
  estimated_minutes: number | null; spent_minutes: number; remaining_minutes: number | null;
  progress_percentage: number; notes: string | null;
};

export type TasksData = {
  ok: boolean; count: number;
  tasks: Array<{ task: AcademicTask; planning: { planning_score: number; urgency_level?: string; reasons?: string[] } }>;
};

export type StudySession = {
  id: number; subject_id: number; subject_name: string | null; session_date: string;
  duration_minutes: number; activity_type: string; topic: string | null; completed_plan: boolean;
  focus_rating: number | null; difficulty_rating: number | null; satisfaction_rating: number | null;
};

export type QuizAttempt = {
  id: number; subject_id: number; topic: string; study_mode: string; difficulty: string;
  total_questions: number; correct_answers: number | null; score_percentage: number | null;
  status: string; started_at: string | null; completed_at: string | null;
};

export type StudyData = {
  ok: boolean; subject: { id: number; name: string }; available_study_modes: string[];
  summary: { study_session_count: number; total_study_minutes: number; quiz_attempt_count: number; completed_quiz_count: number; quiz_average_percentage: number | null };
  recent_attempts: QuizAttempt[]; recent_study_sessions: StudySession[];
  reviews: { ok: boolean; count: number; due_count: number; reviews: Array<{ id: number; topic: string; status: string; next_review_at: string; priority: number }> } | null;
};

export type KnowledgeConcept = {
  id: number; subject_id: number; name: string; mastery_percentage: number | null;
  status: "strong" | "developing" | "weak" | "unassessed"; evidence_count: number;
  assessed_evidence_count: number; exposure_minutes: number; last_evidence_at: string | null;
};

export type KnowledgeData = {
  ok: boolean; subject: { id: number; name: string };
  summary: { concept_count: number; assessed_concept_count: number; overall_mastery_percentage: number | null; strong_count: number; developing_count: number; weak_count: number; unassessed_count: number };
  priority_concepts: KnowledgeConcept[]; concepts: KnowledgeConcept[];
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error ?? `La API de UniCore respondió con ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getDashboard(subjectId?: number): Promise<DashboardData> {
  const params = subjectId == null ? "" : `?subject_id=${subjectId}`;
  return requestJson<DashboardData>(`/api/dashboard${params}`);
}

export function getDecisionPlan(availableMinutes = 60, maximumActions = 3, subjectId?: number): Promise<DecisionPlan> {
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

export function getStudy(subjectId: number): Promise<StudyData> {
  return requestJson<StudyData>(`/api/study?subject_id=${subjectId}`);
}

export function getKnowledge(subjectId: number): Promise<KnowledgeData> {
  return requestJson<KnowledgeData>(`/api/subjects/${subjectId}/knowledge`);
}

export type AgentResponse = { ok: boolean; answer: string | null; status: string; conversation_id: string; error: string | null; job?: { status: string; kind: string; objective: string; created_at: string } };

export function sendAgentMessage(message: string, conversationId?: string): Promise<AgentResponse> {
  return requestJson<AgentResponse>("/api/agent/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}
