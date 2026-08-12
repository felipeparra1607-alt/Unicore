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
  analytics: Record<string, unknown> | null;
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

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error ?? `La API de UniCore respondió con ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getDashboard(): Promise<DashboardData> {
  return requestJson<DashboardData>("/api/dashboard");
}

export function getDecisionPlan(availableMinutes = 60, maximumActions = 3): Promise<DecisionPlan> {
  const params = new URLSearchParams({
    available_minutes: String(availableMinutes),
    maximum_actions: String(maximumActions),
  });
  return requestJson<DecisionPlan>(`/api/decision-plan?${params.toString()}`);
}
