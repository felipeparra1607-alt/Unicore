import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = (path: string) => readFile(new URL(`../src/${path}`, import.meta.url), "utf8");

test("la UI principal no presenta gamificación", async () => {
  const files = await Promise.all(["components/Layout.tsx", "components/Dashboard.tsx", "pages/SubjectsPage.tsx", "pages/SubjectDetailPage.tsx"].map(source));
  assert.equal(/\b(XP|Nivel académico|Misiones de hoy|recompensa)\b/i.test(files.join("\n")), false);
});

test("Work Mode filtra documentos relacionados y no inicia IA automáticamente", async () => {
  const work = await source("pages/WorkSessionPage.tsx");
  assert.match(work, /relatedDocumentIds\.includes\(document\.id\)/);
  assert.match(work, /Pregunta a UniCore cuando necesites ayuda con este bloque/);
  assert.match(work, /<AcademicMarkdown/);
  assert.equal(/useEffect\([^]*sendAgentMessage/.test(work.slice(0, work.indexOf("async function askAgent"))), false);
  assert.match(work, /getCurriculum/);
  assert.match(work, /Temas para repasar/);
});

test("Home no duplica el planner y Goals no presenta preparación", async () => {
  const dashboard = await source("components/Dashboard.tsx");
  const goals = await source("pages/GoalsPage.tsx");
  assert.doesNotMatch(dashboard, /getDecisionPlan|Cómo reparto|Empezar bloque/);
  assert.match(dashboard, /Tareas pendientes/);
  assert.doesNotMatch(goals, /preparación|readiness/i);
  assert.match(goals, /weeklyMinutesFor/);
});

test("Tareas delega la planificación al Session Builder y Flashcards mantiene modos", async () => {
  const tasks = await source("pages/TasksPage.tsx");
  const builder = await source("pages/SessionBuilderPage.tsx");
  const cards = await source("pages/EvaluationPage.tsx");
  assert.match(tasks, /Empezar sesión/);
  assert.match(builder, /Crear manualmente/);
  assert.match(builder, /Usar recomendación/);
  assert.match(builder, /getDecisionPlan/);
  assert.match(builder, /unit_id/);
  assert.match(cards, /No la sabía/);
  assert.match(cards, /La sabía/);
  assert.match(cards, /La dominaba/);
  assert.match(cards, /Rechazar pregunta/);
  assert.match(cards, /answerMode === "mixed" && cardIndex % 2 === 1/);
});

test("Materiales exige clasificación, permite unidad y no ofrece preguntar al Agent", async () => {
  const materials = await source("components/MaterialLibrary.tsx");
  assert.match(materials, /Tipo de material · obligatorio/);
  assert.match(materials, /Unidad relacionada · opcional/);
  assert.match(materials, /updateDocumentClassification/);
  assert.match(materials, /deleteSubjectMaterial/);
  assert.doesNotMatch(materials, /Preguntar (a UniCore|sobre este material)/);
});
