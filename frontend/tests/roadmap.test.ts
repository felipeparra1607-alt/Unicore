import test from "node:test";
import assert from "node:assert/strict";
import { roadmapItems } from "../src/roadmap.ts";

test("la hoja de ruta es frontend-only y contiene las capacidades previstas", () => {
  assert.deepEqual(roadmapItems.map((item) => item.title), [
    "Quiz avanzado",
    "Transcripción automática de clases",
    "Análisis del profesor desde transcripciones",
    "Recursos externos",
    "Gamificación académica",
  ]);
  assert.equal(roadmapItems.every((item) => !Object.keys(item).some((key) => /endpoint|api|url/i.test(key))), true);
});
