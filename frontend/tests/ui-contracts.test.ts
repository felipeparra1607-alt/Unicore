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
  assert.match(work, /filter\(\(document\) => ids\.includes\(document\.id\)\)/);
  assert.match(work, /Pregunta a UniCore cuando necesites ayuda con este bloque/);
  assert.match(work, /<AcademicMarkdown/);
  assert.equal(/useEffect\([^]*sendAgentMessage/.test(work.slice(0, work.indexOf("async function askAgent"))), false);
});
