import { Copy, Save, Sparkles, Trash2 } from "lucide-react";
import Card from "./Card";
import { DailyEntry } from "../types";
import { calculateDailyPoints, duplicateForToday, emptyEntryForDate } from "../utils/analytics";
import { isoToday } from "../utils/date";

const input = "w-full rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-white outline-none focus:border-teal-300";
const label = "space-y-1 text-sm text-slate-300";

export default function DailyEntryForm({
  entries,
  draft,
  setDraft,
  onSave,
  onDelete,
}: {
  entries: DailyEntry[];
  draft: DailyEntry;
  setDraft: (entry: DailyEntry) => void;
  onSave: (entry: DailyEntry) => void;
  onDelete: (id: string) => void;
}) {
  const todayEntry = entries.find((entry) => entry.date === isoToday());
  const previous = [...entries].sort((a, b) => b.date.localeCompare(a.date)).find((entry) => entry.date !== isoToday());
  const update = <K extends keyof DailyEntry>(key: K, value: DailyEntry[K]) => setDraft({ ...draft, [key]: value });
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_0.85fr]">
      <Card
        title="Registro diario"
        action={<span className="rounded-lg bg-teal-400/15 px-3 py-1 text-sm text-teal-100">{calculateDailyPoints(draft)} / 5 puntos</span>}
      >
        <div className="grid gap-3 md:grid-cols-3">
          <label className={label}>Fecha<input className={input} type="date" value={draft.date} onChange={(e) => update("date", e.target.value)} /></label>
          <label className={label}>Energia 1-5<input className={input} type="number" min="1" max="5" value={draft.energy} onChange={(e) => update("energy", Number(e.target.value))} /></label>
          <label className={label}>Sueno horas<input className={input} type="number" step="0.5" value={draft.sleepHours} onChange={(e) => update("sleepHours", Number(e.target.value))} /></label>
          <label className={label}>Peso opcional<input className={input} type="number" step="0.1" value={draft.weight ?? ""} onChange={(e) => update("weight", e.target.value ? Number(e.target.value) : undefined)} /></label>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <fieldset className="rounded-lg border border-white/10 p-4">
            <legend className="px-2 text-sm text-white">Fisico</legend>
            <label className="mb-2 flex gap-2 text-sm"><input type="checkbox" checked={draft.gymCardio} onChange={(e) => update("gymCardio", e.target.checked)} /> Gym/cardio</label>
            <label className="mb-3 flex gap-2 text-sm"><input type="checkbox" checked={draft.boxing} onChange={(e) => update("boxing", e.target.checked)} /> Boxeo</label>
            <textarea className={input} placeholder="Comentario fisico" value={draft.physicalComment} onChange={(e) => update("physicalComment", e.target.value)} />
          </fieldset>
          <fieldset className="rounded-lg border border-white/10 p-4">
            <legend className="px-2 text-sm text-white">Idiomas</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={label}>Portugues min<input className={input} type="number" value={draft.portugueseMinutes} onChange={(e) => update("portugueseMinutes", Number(e.target.value))} /></label>
              <label className={label}>Frances min<input className={input} type="number" value={draft.frenchMinutes} onChange={(e) => update("frenchMinutes", Number(e.target.value))} /></label>
            </div>
            <label className="mt-3 flex gap-2 text-sm"><input type="checkbox" checked={draft.sundayPortugueseVideo} onChange={(e) => update("sundayPortugueseVideo", e.target.checked)} /> Video portugues domingo</label>
            <label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={draft.sundayFrenchVideo} onChange={(e) => update("sundayFrenchVideo", e.target.checked)} /> Video frances domingo</label>
          </fieldset>
          <fieldset className="rounded-lg border border-white/10 p-4">
            <legend className="px-2 text-sm text-white">IA</legend>
            <label className={label}>Minutos<input className={input} type="number" value={draft.aiMinutes} onChange={(e) => update("aiMinutes", Number(e.target.value))} /></label>
            <label className={label}>Tipo<select className={input} value={draft.aiType} onChange={(e) => update("aiType", e.target.value as DailyEntry["aiType"])}>
              {["curso", "practica", "lectura", "proyecto", "investigacion"].map((v) => <option key={v}>{v}</option>)}
            </select></label>
            <textarea className={input} placeholder="Que aprendi" value={draft.aiLearned} onChange={(e) => update("aiLearned", e.target.value)} />
          </fieldset>
          <fieldset className="rounded-lg border border-white/10 p-4">
            <legend className="px-2 text-sm text-white">Historia</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={label}>Minutos<input className={input} type="number" value={draft.historyMinutes} onChange={(e) => update("historyMinutes", Number(e.target.value))} /></label>
              <label className={label}>Avance %<input className={input} type="number" value={draft.historyProgress} onChange={(e) => update("historyProgress", Number(e.target.value))} /></label>
            </div>
            <input className={`${input} mt-3`} placeholder="Capitulo actual" value={draft.historyChapter} onChange={(e) => update("historyChapter", e.target.value)} />
            <label className="mt-3 flex gap-2 text-sm"><input type="checkbox" checked={draft.historyPresentation} onChange={(e) => update("historyPresentation", e.target.checked)} /> Presentacion hecha</label>
          </fieldset>
        </div>
        <fieldset className="mt-4 rounded-lg border border-white/10 p-4">
          <legend className="px-2 text-sm text-white">Practicas / proyectos / vida</legend>
          <div className="grid gap-3 md:grid-cols-3">
            <label className={label}>Solicitudes<input className={input} type="number" value={draft.applicationsSent} onChange={(e) => update("applicationsSent", Number(e.target.value))} /></label>
            <label className={label}>Ofertas revisadas<input className={input} type="number" value={draft.offersReviewed} onChange={(e) => update("offersReviewed", Number(e.target.value))} /></label>
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={draft.importantAction} onChange={(e) => update("importantAction", e.target.checked)} /> Accion importante</label>
          </div>
          <textarea className={`${input} mt-3`} placeholder="Comentario" value={draft.lifeComment} onChange={(e) => update("lifeComment", e.target.value)} />
        </fieldset>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <textarea className={input} placeholder="Mejor avance del dia" value={draft.bestProgress} onChange={(e) => update("bestProgress", e.target.value)} />
          <textarea className={input} placeholder="Bloqueo principal" value={draft.mainBlocker} onChange={(e) => update("mainBlocker", e.target.value)} />
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <button className="flex items-center gap-2 rounded-lg bg-teal-400 px-4 py-2 font-semibold text-slate-950" onClick={() => onSave(draft)}><Save size={17} /> Guardar</button>
          <button className="flex items-center gap-2 rounded-lg bg-blue-400/15 px-4 py-2 text-blue-100" onClick={() => onSave({ ...emptyEntryForDate(isoToday()), gymCardio: true, portugueseMinutes: 30, frenchMinutes: 30, aiMinutes: 45, importantAction: true, bestProgress: "Dia rapido completado." })}><Sparkles size={17} /> Dia rapido</button>
          <button disabled={!previous} className="flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2 text-white disabled:opacity-40" onClick={() => previous && setDraft(duplicateForToday(previous, isoToday()))}><Copy size={17} /> Duplicar ayer</button>
        </div>
      </Card>
      <Card title="Registros">
        <div className="space-y-3">
          {entries.map((entry) => (
            <div key={entry.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <button className="text-left" onClick={() => setDraft(entry)}>
                  <strong className="text-white">{entry.date}</strong>
                  <p className="text-sm text-slate-400">{calculateDailyPoints(entry)} puntos · energia {entry.energy}/5</p>
                </button>
                <button className="rounded-lg bg-red-400/15 p-2 text-red-200" onClick={() => confirm("Borrar este registro?") && onDelete(entry.id)}><Trash2 size={17} /></button>
              </div>
            </div>
          ))}
          {!entries.length && <p className="text-sm text-slate-400">Aun no hay registros.</p>}
          {todayEntry && <p className="text-sm text-teal-200">Hoy ya esta registrado. Puedes editarlo desde la lista.</p>}
        </div>
      </Card>
    </div>
  );
}
