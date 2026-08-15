import type { DecisionAction } from "./api";

export const workDurations = [15, 30, 45, 60, 90] as const;

export type WorkSessionSeed = {
  actions: DecisionAction[];
  durationMinutes: number;
};

export type StoredWorkSession = WorkSessionSeed & {
  startedAt: string;
  deadline: number | null;
  remainingMs: number;
  running: boolean;
  activeIndex: number;
  actionDeadline: number | null;
  actionRemainingMs: number;
  conversationId?: string;
  activeDocumentId?: number | null;
};

export type LegacyWorkSession = Omit<StoredWorkSession, "actions" | "activeIndex" | "actionDeadline" | "actionRemainingMs"> & { action: DecisionAction };

export function normalizeStoredWorkSession(value: StoredWorkSession | LegacyWorkSession): StoredWorkSession {
  if ("actions" in value) return value;
  const actionRemainingMs = Math.min(value.remainingMs, value.action.allocated_minutes * 60_000);
  return { ...value, actions: [value.action], activeIndex: 0, actionDeadline: value.running ? Date.now() + actionRemainingMs : null, actionRemainingMs };
}

export const WORK_SESSION_STORAGE_KEY = "unicore-active-work-session";

export function suggestedDuration(minutes: number) {
  return workDurations.reduce((closest, candidate) => (
    Math.abs(candidate - minutes) < Math.abs(closest - minutes) ? candidate : closest
  ), workDurations[0]);
}
