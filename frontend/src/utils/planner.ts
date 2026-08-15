import type { CurriculumData, DecisionAction } from "../api";

export type PlannerMode = "priority" | "balanced";

const normalize = (value: string) => value
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLocaleLowerCase()
  .replace(/[^a-z0-9]+/g, " ")
  .trim();

const tokens = (value: string) => new Set(normalize(value).split(" ").filter((item) => item.length > 2));

function similarity(first: string, second: string) {
  const a = tokens(first); const b = tokens(second);
  if (!a.size || !b.size) return 0;
  const overlap = [...a].filter((item) => b.has(item)).length;
  return overlap / Math.min(a.size, b.size);
}

export function promoteReviewsToUnits(actions: DecisionAction[], curricula: CurriculumData[]) {
  return actions.map((action) => {
    if (action.type !== "review" || action.subject_id == null) return action;
    const curriculum = curricula.find((item) => item.subject.id === action.subject_id);
    if (!curriculum) return action;
    const candidates = curriculum.units.flatMap((unit) => unit.topics.flatMap((topic) => [
      { unit, item: topic },
      ...topic.subtopics.map((subtopic) => ({ unit, item: subtopic })),
    ]));
    const match = candidates
      .map((candidate) => ({ ...candidate, score: similarity(action.title, candidate.item.name) }))
      .sort((a, b) => b.score - a.score)[0];
    if (!match || match.score < 0.5) return action;
    const documentIds = [...new Set(match.unit.topics.flatMap((topic) => [
      ...topic.sources.map((source) => source.document_id),
      ...topic.subtopics.flatMap((subtopic) => subtopic.sources.map((source) => source.document_id)),
    ]))];
    return {
      ...action,
      title: `Repasar ${match.unit.name}`,
      metadata: {
        ...action.metadata,
        unit_id: match.unit.id,
        unit_name: match.unit.name,
        focus_topic_ids: [match.item.id],
        document_ids: documentIds,
      },
    };
  });
}

function mergeMetadata(first: Record<string, unknown>, second: Record<string, unknown>) {
  const merged = { ...first, ...second };
  for (const key of ["focus_topic_ids", "document_ids"]) {
    const values = [...(Array.isArray(first[key]) ? first[key] as unknown[] : []), ...(Array.isArray(second[key]) ? second[key] as unknown[] : [])];
    if (values.length) merged[key] = [...new Set(values)];
  }
  return merged;
}

export function mergeDuplicateActions(actions: DecisionAction[]) {
  const merged = new Map<string, DecisionAction>();
  for (const action of actions) {
    const unitId = typeof action.metadata.unit_id === "number" ? action.metadata.unit_id : null;
    const key = `${action.type}:${action.subject_id ?? "general"}:${unitId ?? normalize(action.title)}`;
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, { ...action, reasons: [...new Set(action.reasons)], metadata: { ...action.metadata } });
      continue;
    }
    existing.allocated_minutes += action.allocated_minutes;
    existing.suggested_minutes += action.suggested_minutes;
    existing.score = Math.max(existing.score, action.score);
    existing.reasons = [...new Set([...existing.reasons, ...action.reasons])];
    existing.metadata = mergeMetadata(existing.metadata, action.metadata);
  }
  return [...merged.values()];
}

export function orderPlanActions(actions: DecisionAction[], mode: PlannerMode) {
  if (mode === "priority") return actions;
  const critical = actions.filter((action) => action.priority === "critical");
  const remaining = actions.filter((action) => action.priority !== "critical");
  const ordered: DecisionAction[] = [...critical];
  while (remaining.length) {
    const previous = ordered.at(-1);
    const nextIndex = remaining.findIndex((action) => action.subject_id !== previous?.subject_id);
    ordered.push(...remaining.splice(nextIndex >= 0 ? nextIndex : 0, 1));
  }
  return ordered;
}

export function composePlan(actions: DecisionAction[], mode: PlannerMode, curricula: CurriculumData[] = []) {
  return orderPlanActions(mergeDuplicateActions(promoteReviewsToUnits(actions, curricula)), mode);
}

export function movePlanAction(actions: DecisionAction[], index: number, direction: -1 | 1) {
  const target = index + direction;
  if (target < 0 || target >= actions.length) return actions;
  const next = [...actions];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function changeActionMinutes(actions: DecisionAction[], index: number, delta: number, availableMinutes: number) {
  const current = actions[index];
  if (!current) return { actions, error: "La actividad ya no está disponible." };
  const nextMinutes = current.allocated_minutes + delta;
  if (nextMinutes < 15) return { actions, error: "Cada actividad necesita al menos 15 minutos." };
  const allocated = actions.reduce((sum, action) => sum + action.allocated_minutes, 0);
  if (allocated + delta > availableMinutes) return { actions, error: `El plan no puede superar ${availableMinutes} minutos.` };
  const next = actions.map((action, actionIndex) => actionIndex === index ? { ...action, allocated_minutes: nextMinutes } : action);
  return { actions: next, error: null };
}

export function allocatedMinutes(actions: DecisionAction[]) {
  return actions.reduce((sum, action) => sum + action.allocated_minutes, 0);
}
