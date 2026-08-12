import React from "react";
import Card from "./Card";
import { InternshipApplication } from "../types";

const empty = (): InternshipApplication => ({ id: crypto.randomUUID(), company: "", role: "", applicationDate: new Date().toISOString().slice(0, 10), status: "guardada", link: "", notes: "" });
const input = "w-full rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-white outline-none focus:border-teal-300";

export default function InternshipTracker({ items, onSave }: { items: InternshipApplication[]; onSave: (item: InternshipApplication) => void }) {
  const [draft, setDraft] = React.useState<InternshipApplication>(empty());
  const set = <K extends keyof InternshipApplication>(key: K, value: InternshipApplication[K]) => setDraft({ ...draft, [key]: value });
  const sent = items.filter((i) => i.status !== "guardada").length;
  const responses = items.filter((i) => ["respuesta", "entrevista", "oferta"].includes(i.status)).length;
  const interviews = items.filter((i) => i.status === "entrevista").length;
  const open = items.filter((i) => !["rechazada", "oferta"].includes(i.status)).length;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        {[["Solicitudes", sent], ["Respuestas", responses], ["Entrevistas", interviews], ["Procesos abiertos", open]].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-white/10 bg-white/[0.055] p-4"><div className="text-2xl font-bold">{value}</div><p className="text-sm text-slate-400">{label}</p></div>
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-[0.85fr_1fr]">
        <Card title={`Practicas · ratio respuesta ${sent ? Math.round((responses / sent) * 100) : 0}%`}>
          <div className="space-y-3">
            <input className={input} placeholder="Empresa" value={draft.company} onChange={(e) => set("company", e.target.value)} />
            <input className={input} placeholder="Puesto" value={draft.role} onChange={(e) => set("role", e.target.value)} />
            <input className={input} type="date" value={draft.applicationDate} onChange={(e) => set("applicationDate", e.target.value)} />
            <select className={input} value={draft.status} onChange={(e) => set("status", e.target.value as InternshipApplication["status"])}>
              {["guardada", "aplicada", "respuesta", "entrevista", "rechazada", "oferta"].map((s) => <option key={s}>{s}</option>)}
            </select>
            <input className={input} placeholder="Link oferta" value={draft.link} onChange={(e) => set("link", e.target.value)} />
            <input className={input} type="date" value={draft.nextFollowUp || ""} onChange={(e) => set("nextFollowUp", e.target.value)} />
            <textarea className={input} placeholder="Notas" value={draft.notes} onChange={(e) => set("notes", e.target.value)} />
            <button className="rounded-lg bg-teal-400 px-4 py-2 font-semibold text-slate-950" onClick={() => { onSave(draft); setDraft(empty()); }}>Guardar oferta</button>
          </div>
        </Card>
        <Card title="Procesos">
          <div className="space-y-3">
            {items.map((item) => (
              <button key={item.id} onClick={() => setDraft(item)} className="w-full rounded-lg border border-white/10 bg-black/20 p-3 text-left">
                <div className="flex justify-between gap-3"><strong>{item.company || "Empresa"}</strong><span className="text-teal-200">{item.status}</span></div>
                <p className="text-sm text-slate-400">{item.role} · {item.applicationDate} · seguimiento {item.nextFollowUp || "-"}</p>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
