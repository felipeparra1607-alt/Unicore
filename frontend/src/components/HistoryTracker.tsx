import Card from "./Card";
import { HistoryChapter } from "../types";

const empty = (): HistoryChapter => ({ id: crypto.randomUUID(), name: "", period: "", estimatedHours: 5, completedHours: 0, status: "pendiente", presentationDone: false, notes: "" });
const input = "w-full rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-white outline-none focus:border-teal-300";

export default function HistoryTracker({ chapters, onSave }: { chapters: HistoryChapter[]; onSave: (chapter: HistoryChapter) => void }) {
  const [draft, setDraft] = React.useState<HistoryChapter>(empty());
  const finished = chapters.filter((c) => c.status === "terminado").length;
  const hours = chapters.reduce((sum, c) => sum + c.completedHours, 0);
  const current = chapters.find((c) => c.status === "en progreso") || chapters[0];
  const set = <K extends keyof HistoryChapter>(key: K, value: HistoryChapter[K]) => setDraft({ ...draft, [key]: value });
  return (
    <div className="grid gap-5 lg:grid-cols-[0.85fr_1fr]">
      <Card title="Historia">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-lg bg-white/5 p-3"><div className="text-2xl font-bold">{finished}</div><p className="text-xs text-slate-400">terminados</p></div>
          <div className="rounded-lg bg-white/5 p-3"><div className="text-2xl font-bold">{hours.toFixed(1)}</div><p className="text-xs text-slate-400">horas</p></div>
          <div className="rounded-lg bg-white/5 p-3"><div className="text-2xl font-bold">{current ? Math.round((current.completedHours / current.estimatedHours) * 100) : 0}%</div><p className="text-xs text-slate-400">actual</p></div>
        </div>
        <div className="mt-4 space-y-3">
          <input className={input} placeholder="Nombre del capitulo" value={draft.name} onChange={(e) => set("name", e.target.value)} />
          <input className={input} placeholder="Periodo historico" value={draft.period} onChange={(e) => set("period", e.target.value)} />
          <div className="grid gap-3 sm:grid-cols-2">
            <input className={input} type="number" value={draft.estimatedHours} onChange={(e) => set("estimatedHours", Number(e.target.value))} />
            <input className={input} type="number" value={draft.completedHours} onChange={(e) => set("completedHours", Number(e.target.value))} />
          </div>
          <select className={input} value={draft.status} onChange={(e) => set("status", e.target.value as HistoryChapter["status"])}>
            <option>pendiente</option><option>en progreso</option><option>terminado</option>
          </select>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={draft.presentationDone} onChange={(e) => set("presentationDone", e.target.checked)} /> Presentacion hecha</label>
          <input className={input} type="date" value={draft.completedDate || ""} onChange={(e) => set("completedDate", e.target.value)} />
          <textarea className={input} placeholder="Notas" value={draft.notes} onChange={(e) => set("notes", e.target.value)} />
          <button className="rounded-lg bg-teal-400 px-4 py-2 font-semibold text-slate-950" onClick={() => { onSave(draft); setDraft(empty()); }}>Guardar capitulo</button>
        </div>
      </Card>
      <Card title="Capitulos">
        <div className="space-y-3">
          {chapters.map((chapter) => (
            <button key={chapter.id} onClick={() => setDraft(chapter)} className="w-full rounded-lg border border-white/10 bg-black/20 p-3 text-left">
              <div className="flex justify-between gap-3"><strong>{chapter.name || "Sin nombre"}</strong><span className="text-teal-200">{chapter.status}</span></div>
              <p className="text-sm text-slate-400">{chapter.period} · {chapter.completedHours}/{chapter.estimatedHours} h · presentacion {chapter.presentationDone ? "si" : "no"}</p>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}

import React from "react";
