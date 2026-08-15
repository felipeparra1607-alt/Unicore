import test from "node:test";
import assert from "node:assert/strict";

test("guarda y recupera preferencias globales y por asignatura", async () => {
  const storage = new Map<string, string>();
  Object.assign(globalThis, { window: { localStorage: { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) }, dispatchEvent: () => true }, Event: class { type: string; constructor(type: string) { this.type = type; } } });
  const { getGoalPreferences, saveGoalPreferences } = await import("../src/utils/goalPreferences.ts");
  const value = { weeklyMinutes: 480, dailyMinutes: 90, studyDays: 5, readinessTarget: 80, subjects: { "4": { weeklyMinutes: 180, readinessTarget: 85 } } };
  saveGoalPreferences(value);
  assert.deepEqual(getGoalPreferences(), value);
});
