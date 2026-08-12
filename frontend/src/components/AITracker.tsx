import React from "react";
import Card from "./Card";
import { AIItem, AICategory } from "../types";

const categories: AICategory[] = ["Prompting", "Agentes", "APIs", "Workflows", "Automatizaciones", "RAG", "Evaluacion", "Herramientas", "Fundamentos", "Otros"];
const empty = (): AIItem => ({ id: crypto.randomUUID(), title: "", lesson: "", concept: "", miniProject: "", category: "Prompting", mastery: 3, appliedToBusiness: false, date: new Date().toISOString().slice(0, 10) });
const input = "w-full rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-white outline-none focus:border-teal-300";

export default function AITracker({ items, onSave }: { items: AIItem[]; onSave: (item: AIItem) => void }) {
  const [draft, setDraft] = React.useState<AIItem>(empty());
  const set = <K extends keyof AIItem>(key: K, value: AIItem[K]) => setDraft({ ...draft, [key]: value });
  return (
    <div className="grid gap-5 lg:grid-cols-[0.85fr_1fr]">
      <Card title="Registro IA">
        <div className="space-y-3">
          <input className={input} placeholder="Curso o recurso" value={draft.title} onChange={(e) => set("title", e.target.value)} />
          <input className={input} placeholder="Leccion" value={draft.lesson} onChange={(e) => set("lesson", e.target.value)} />
          <input className={input} placeholder="Concepto aprendido" value={draft.concept} onChange={(e) => set("concept", e.target.value)} />
          <input className={input} placeholder="Mini-proyecto" value={draft.miniProject} onChange={(e) => set("miniProject", e.target.value)} />
          <select className={input} value={draft.category} onChange={(e) => set("category", e.target.value as AICategory)}>{categories.map((c) => <option key={c}>{c}</option>)}</select>
          <label className="text-sm text-slate-300">Dominio {draft.mastery}/5<input className="w-full accent-teal-300" type="range" min="1" max="5" value={draft.mastery} onChange={(e) => set("mastery", Number(e.target.value))} /></label>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={draft.appliedToBusiness} onChange={(e) => set("appliedToBusiness", e.target.checked)} /> Aplicado a negocio</label>
          <button className="rounded-lg bg-teal-400 px-4 py-2 font-semibold text-slate-950" onClick={() => { onSave(draft); setDraft(empty()); }}>Guardar IA</button>
        </div>
      </Card>
      <Card title="Aprendizajes">
        <div className="space-y-3">
          {items.map((item) => (
            <button key={item.id} onClick={() => setDraft(item)} className="w-full rounded-lg border border-white/10 bg-black/20 p-3 text-left">
              <div className="flex justify-between gap-3"><strong>{item.concept || item.title}</strong><span className="text-blue-200">{item.category}</span></div>
              <p className="text-sm text-slate-400">{item.lesson} · dominio {item.mastery}/5 · {item.appliedToBusiness ? "negocio" : "general"}</p>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
