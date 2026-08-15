export type SubjectGoalPreference = { weeklyMinutes: number; readinessTarget: number };
export type GoalPreferences = { weeklyMinutes: number; dailyMinutes: number; studyDays: number; readinessTarget: number; subjects: Record<string, SubjectGoalPreference> };

const KEY = "unicore-goal-preferences-v1";
const defaults: GoalPreferences = { weeklyMinutes: 180, dailyMinutes: 45, studyDays: 4, readinessTarget: 80, subjects: {} };

export function getGoalPreferences(): GoalPreferences {
  try {
    const value = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as Partial<GoalPreferences> | null;
    return value ? { ...defaults, ...value, subjects: value.subjects ?? {} } : defaults;
  } catch { return defaults; }
}

export function saveGoalPreferences(value: GoalPreferences) {
  window.localStorage.setItem(KEY, JSON.stringify(value));
  window.dispatchEvent(new Event("unicore-goals-changed"));
}
