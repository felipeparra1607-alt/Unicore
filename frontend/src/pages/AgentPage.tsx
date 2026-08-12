import { ArrowUp, BrainCircuit, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { sendAgentMessage } from "../api";

type Message = { role: "user" | "agent"; text: string; job?: boolean };
const progress = ["Analizando tu contexto académico…", "Revisando tus prioridades…", "Consultando tu progreso…"];
const suggestions = ["¿Qué debería hacer ahora?", "Resume mi situación académica", "¿Dónde necesito más atención?"];

export default function AgentPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (!submitting) return; const timer = window.setInterval(() => setProgressIndex((value) => (value + 1) % progress.length), 1400); return () => window.clearInterval(timer); }, [submitting]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, submitting]);

  async function submit(text: string) {
    const clean = text.trim(); if (!clean || submitting) return;
    setMessages((current) => [...current, { role: "user", text: clean }]); setInput(""); setSubmitting(true); setError(null); setProgressIndex(0);
    try {
      const result = await sendAgentMessage(clean, conversationId); setConversationId(result.conversation_id);
      if (result.answer) { const answer = result.answer; setMessages((current) => [...current, { role: "agent", text: answer }]); }
      else if (result.status === "handoff_requested" && result.job) { const job = result.job; setMessages((current) => [...current, { role: "agent", job: true, text: `He preparado un análisis en segundo plano: ${job.objective}. Puedes seguir su estado en Jobs.` }]); }
      else setMessages((current) => [...current, { role: "agent", text: "UniCore terminó la consulta sin una respuesta visible." }]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo consultar UniCore Agent."); }
    finally { setSubmitting(false); }
  }
  function handleSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }

  return <div className="uc-page-shell uc-agent-page">
    <header className="uc-agent-header"><div><p className="uc-eyebrow">UniCore Agent</p><h1>Asistencia con contexto académico.</h1><p>Consulta prioridades, progreso y conocimiento sin salir de tu sistema universitario.</p></div><div className="uc-agent-policy"><ShieldCheck size={16} /><span><strong>Modo seguro</strong>Las escrituras están desactivadas</span></div></header>
    <section className="uc-agent-shell"><aside className="uc-agent-context"><BrainCircuit size={24} /><h2>Un agente dentro de UniCore</h2><p>Puede consultar tu actividad real, razonar sobre tus asignaturas y derivar análisis largos a Jobs.</p><div><span>Puede ayudarte con</span><ul><li>Prioridades y planificación</li><li>Rendimiento por asignatura</li><li>Repasos y conocimiento</li><li>Resultados de trabajos largos</li></ul></div><small>No se muestran herramientas internas ni datos técnicos.</small></aside>
      <div className="uc-conversation"><div className="uc-message-stream">{messages.length === 0 ? <div className="uc-agent-empty"><Sparkles size={22} /><h2>¿Qué quieres entender?</h2><p>Empieza con una pregunta concreta. UniCore consultará únicamente el contexto necesario.</p><div>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void submit(suggestion)}>{suggestion}</button>)}</div></div> : messages.map((message, index) => <article key={index} className={`uc-message is-${message.role} ${message.job ? "is-job" : ""}`}><span>{message.role === "user" ? "Tú" : "UniCore"}</span><p>{message.text}</p></article>)}{submitting && <article className="uc-message is-agent is-working"><span>UniCore</span><p>{progress[progressIndex]}</p><i /><i /><i /></article>}{error && <div className="uc-agent-error"><span>{error}</span><button onClick={() => setError(null)} aria-label="Cerrar error"><RefreshCw size={14} /></button></div>}<div ref={endRef} /></div>
        <form className="uc-agent-composer" onSubmit={handleSubmit}><label htmlFor="agent-message" className="sr-only">Mensaje para UniCore Agent</label><textarea id="agent-message" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Pregunta sobre tus tareas, asignaturas o progreso…" rows={2} disabled={submitting} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button type="submit" disabled={submitting || !input.trim()} aria-label="Enviar mensaje"><ArrowUp size={17} /></button><small>Enter para enviar · Shift + Enter para nueva línea</small></form>
      </div></section>
  </div>;
}
