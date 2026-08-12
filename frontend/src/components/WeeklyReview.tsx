import Card from "./Card";
import { AppData } from "../types";
import { areaDone, areaLabels, calculateDailyPoints, calculateWeeklyPoints, generateWeeklySummary, weeklyEntries, weeklyLevel } from "../utils/analytics";

export default function WeeklyReview({ data }: { data: AppData }) {
  const week = weeklyEntries(data.entries);
  const summary = generateWeeklySummary(data.entries, data.chapters);
  const points = calculateWeeklyPoints(data.entries);
  return (
    <div className="space-y-5">
      <Card title={`Semana actual: ${points}/35 puntos (${weeklyLevel(points)})`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-slate-400"><tr><th className="p-2">Dia</th><th>Puntos</th><th>Energia</th><th>Areas cumplidas</th><th>Avance</th><th>Bloqueo</th></tr></thead>
            <tbody>
              {week.map((entry) => {
                const done = areaDone(entry);
                return (
                  <tr key={entry.id} className="border-t border-white/10">
                    <td className="p-2 text-white">{entry.date}</td>
                    <td>{calculateDailyPoints(entry)}</td>
                    <td>{entry.energy}/5</td>
                    <td>{Object.entries(done).filter(([, value]) => value).map(([key]) => areaLabels[key as keyof typeof areaLabels]).join(", ") || "Nada"}</td>
                    <td>{entry.bestProgress || "-"}</td>
                    <td>{entry.mainBlocker || "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Analisis automatico">
          <div className="space-y-3 text-sm text-slate-300">
            <p><strong className="text-white">Destacaste:</strong> {summary.standout}</p>
            <p><strong className="text-white">Descuidaste:</strong> {summary.neglected}</p>
            <p><strong className="text-white">Patron:</strong> {summary.pattern}</p>
            <p><strong className="text-white">Mejora:</strong> {summary.improve}</p>
            <p><strong className="text-white">Accion:</strong> {summary.action}</p>
            <p><strong className="text-white">Prioridad:</strong> {summary.priority}</p>
          </div>
        </Card>
        <Card title="Resumen coach">
          <p className="text-slate-300">{summary.coachText}</p>
        </Card>
      </div>
    </div>
  );
}
