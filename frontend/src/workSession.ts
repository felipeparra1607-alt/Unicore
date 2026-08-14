import type { DecisionAction } from "./api";

export const workDurations = [15, 30, 45, 60, 90] as const;

export type WorkSessionSeed = {
  action: DecisionAction;
  durationMinutes: number;
};

export type StoredWorkSession = WorkSessionSeed & {
  startedAt: string;
  deadline: number | null;
  remainingMs: number;
  running: boolean;
  conversationId?: string;
  activeDocumentId?: number | null;
};

export const WORK_SESSION_STORAGE_KEY = "unicore-active-work-session";

export function suggestedDuration(minutes: number) {
  return workDurations.reduce((closest, candidate) => (
    Math.abs(candidate - minutes) < Math.abs(closest - minutes) ? candidate : closest
  ), workDurations[0]);
}
