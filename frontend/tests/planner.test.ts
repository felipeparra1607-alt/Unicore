import assert from "node:assert/strict";
import test from "node:test";
import type { DecisionAction } from "../src/api.ts";
import { allocatedMinutes, changeActionMinutes, mergeDuplicateActions, movePlanAction, orderPlanActions } from "../src/utils/planner.ts";

const action = (title: string, minutes: number, subject: number, priority: DecisionAction["priority"] = "high"): DecisionAction => ({
  type: "review", source_id: Math.random(), subject_id: subject, subject_name: `S${subject}`, title,
  score: 10, priority, suggested_minutes: minutes, allocated_minutes: minutes, reasons: [title], action: "review", metadata: {},
});

test("fusiona acciones duplicadas y conserva minutos", () => {
  const result = mergeDuplicateActions([action("Mission", 15, 1), action("Mission", 15, 1), action("Mission", 15, 1)]);
  assert.equal(result.length, 1);
  assert.equal(result[0].allocated_minutes, 45);
});

test("priority conserva orden y balanced diversifica asignaturas", () => {
  const input = [action("A", 15, 1), action("B", 15, 1), action("C", 15, 2)];
  assert.deepEqual(orderPlanActions(input, "priority").map((item) => item.title), ["A", "B", "C"]);
  assert.deepEqual(orderPlanActions(input, "balanced").map((item) => item.title), ["A", "C", "B"]);
});

test("respeta total disponible y permite reordenar", () => {
  const input = [action("A", 30, 1), action("B", 30, 2)];
  assert.equal(changeActionMinutes(input, 0, 15, 60).error, "El plan no puede superar 60 minutos.");
  const reduced = changeActionMinutes(input, 0, -15, 60).actions;
  assert.equal(allocatedMinutes(reduced), 45);
  assert.deepEqual(movePlanAction(reduced, 0, 1).map((item) => item.title), ["B", "A"]);
});
