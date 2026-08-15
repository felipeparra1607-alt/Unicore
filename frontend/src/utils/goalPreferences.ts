export type SubjectGoalPreference = { weeklyMinutes?: number };
export type GoalPreferences = {
  dailyMinutes: number;
  studyDays: number;
  subjects: Record<string, SubjectGoalPreference>;
};

const KEY = "unicore-goal-preferences-v1";
const defaults: GoalPreferences = {
  dailyMinutes: 45,
  studyDays: 4,
  subjects: {},
};

export function getGoalPreferences(): GoalPreferences {
  try {
    const value = JSON.parse(
      window.localStorage.getItem(KEY) ?? "null",
    ) as Partial<GoalPreferences> | null;
    if (!value) return defaults;
    const subjects = Object.fromEntries(
      Object.entries(value.subjects ?? {}).map(([id, item]) => [
        id,
        { weeklyMinutes: item.weeklyMinutes },
      ]),
    );
    return {
      dailyMinutes: value.dailyMinutes ?? defaults.dailyMinutes,
      studyDays: value.studyDays ?? defaults.studyDays,
      subjects,
    };
  } catch {
    return defaults;
  }
}

export const weeklyMinutesFor = (
  value: Pick<GoalPreferences, "dailyMinutes" | "studyDays">,
) => value.dailyMinutes * value.studyDays;

export function saveGoalPreferences(value: GoalPreferences) {
  window.localStorage.setItem(KEY, JSON.stringify(value));
  window.dispatchEvent(new Event("unicore-goals-changed"));
}
