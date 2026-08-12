const STUDY_GOAL_KEY = "unicore-weekly-study-goal-minutes";

export function getWeeklyStudyGoal(): number | null {
  const value = Number(window.localStorage.getItem(STUDY_GOAL_KEY));
  return Number.isFinite(value) && value >= 30 && value <= 10000 ? value : null;
}

export function saveWeeklyStudyGoal(minutes: number) {
  window.localStorage.setItem(STUDY_GOAL_KEY, String(minutes));
  window.dispatchEvent(new Event("unicore-study-goal-changed"));
}
