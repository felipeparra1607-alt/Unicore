import Card from "./Card";
import { Goals as GoalsType } from "../types";

export default function Goals({ goals, onSave }: { goals: GoalsType; onSave: (goals: GoalsType) => void }) {
  const set = (key: keyof GoalsType, value: string) => onSave({ ...goals, [key]: value });
  return (
    <Card title="Objetivos hasta septiembre">
      <div className="grid gap-4 md:grid-cols-2">
        {(Object.keys(goals) as (keyof GoalsType)[]).map((key) => (
          <label key={key} className="space-y-2 text-sm text-slate-300">
            <span className="capitalize text-white">{key}</span>
            <textarea className="min-h-28 w-full rounded-lg border border-white/10 bg-black/25 p-3 text-white outline-none focus:border-teal-300" value={goals[key]} onChange={(e) => set(key, e.target.value)} />
          </label>
        ))}
      </div>
    </Card>
  );
}
