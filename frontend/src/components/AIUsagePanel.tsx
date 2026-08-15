import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAIUsage, type AIUsageData } from "../api";

const compact = (value: number) => value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : String(value);

export default function AIUsagePanel() {
  const [data, setData] = useState<AIUsageData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getAIUsage().then(setData).catch((caught) => setError(caught instanceof Error ? caught.message : "No disponible")); }, []);
  if (error) return <section className="uc-ai-usage"><header><p className="uc-eyebrow">Actividad del Agent</p><h2>Tokens usados</h2></header><p>{error}</p></section>;
  if (!data) return <section className="uc-ai-usage"><header><p className="uc-eyebrow">Actividad del Agent</p><h2>Cargando tokens…</h2></header></section>;
  return <section className="uc-ai-usage"><header><div><p className="uc-eyebrow">Actividad del Agent</p><h2>Tokens usados</h2></div><div><span>Hoy <strong>{compact(data.today)}</strong></span><span>Esta semana <strong>{compact(data.this_week)}</strong></span></div></header><div className="uc-token-legend"><span><i className="is-input" /> Entrada</span><span><i className="is-output" /> Salida</span></div><div className="uc-ai-usage-grid"><article><h3>Uso diario</h3><ResponsiveContainer width="100%" height={220}><BarChart data={data.daily.slice(-7)}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" tickFormatter={(value) => new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", { weekday: "short" })} /><YAxis tickFormatter={compact} width={42} /><Tooltip formatter={(value, name) => [`${Number(value).toLocaleString("es-ES")} tokens`, name === "input_tokens" ? "Entrada" : "Salida"]} /><Bar dataKey="input_tokens" stackId="tokens" fill="var(--chart-blue)" name="input_tokens" /><Bar dataKey="output_tokens" stackId="tokens" fill="var(--chart-amber)" name="output_tokens" /></BarChart></ResponsiveContainer></article><article><h3>Uso por asignatura</h3>{data.by_subject.length ? <div className="uc-token-subject-bars">{data.by_subject.slice(0, 7).map((item) => { const maximum = Math.max(...data.by_subject.map((row) => row.total_tokens), 1); return <div key={item.subject_id ?? "general"}><span>{item.subject_name}</span><div><i style={{ width: `${item.total_tokens / maximum * 100}%` }} /></div><strong>{compact(item.total_tokens)}</strong></div>; })}</div> : <p className="uc-empty-inline">Todavía no hay consumo registrado.</p>}</article></div></section>;
}
