import { ArrowUp, BrainCircuit, Check, Copy, FileText, MessageSquarePlus, RefreshCw, ShieldCheck, Sparkles, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  buildAcademicPrompt,
  deleteConversation,
  getDashboard,
  getConversation,
  getConversations,
  getSubjectDocuments,
  getTasks,
  sendAgentMessage,
  type AcademicTask,
  type AgentSource,
  type ConversationSummary,
  type DashboardData,
  type SubjectDocumentsData,
  type TokenUsage,
} from "../api";
import AcademicMarkdown from "../components/AcademicMarkdown";
import TokenUsageNote from "../components/TokenUsageNote";

type Message = { role: "user" | "assistant"; text: string; sources?: AgentSource[]; usage?: TokenUsage; job?: boolean };
type LaunchContext = { subjectId: number; subjectName: string; documentId?: number; documentTitle?: string; topic?: string; explanation?: string; sources?: unknown[] } | null;
const ACTIVE_CONVERSATION_KEY = "unicore-active-conversation";
const progress = ["Analizando la pregunta…", "Consultando solo el contexto necesario…", "Preparando una respuesta…"];
const suggestions = ["¿Qué debería hacer ahora?", "Resume mi situación académica", "¿Dónde necesito más atención?"];

export default function AgentPage({ launchContext }: { launchContext?: LaunchContext }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [subjectId, setSubjectId] = useState<number | null>(launchContext?.subjectId ?? null);
  const [documentId, setDocumentId] = useState<number | null>(launchContext?.documentId ?? null);
  const [documents, setDocuments] = useState<SubjectDocumentsData["documents"]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tasks, setTasks] = useState<AcademicTask[]>([]);
  const [promptBuilderOpen, setPromptBuilderOpen] = useState(false);
  const [promptObjective, setPromptObjective] = useState("");
  const [promptTaskId, setPromptTaskId] = useState<number | null>(null);
  const [generatedPrompt, setGeneratedPrompt] = useState("");
  const [buildingPrompt, setBuildingPrompt] = useState(false);
  const [promptCopied, setPromptCopied] = useState(false);
  const [promptContext, setPromptContext] = useState({ professor: true, rubric: true, academicMemory: false, improvements: false, strengths: false });
  const [submitting, setSubmitting] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  async function refreshHistory(openStored = false) {
    setHistoryLoading(true);
    try {
      const result = await getConversations();
      setConversations(result.conversations);
      if (openStored && !launchContext) {
        const stored = window.localStorage.getItem(ACTIVE_CONVERSATION_KEY);
        if (stored && result.conversations.some((item) => item.id === stored)) await openConversation(stored);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el historial."); }
    finally { setHistoryLoading(false); }
  }

  async function openConversation(id: string) {
    setError(null);
    try {
      const result = await getConversation(id);
      const conversation = result.conversation;
      setConversationId(conversation.id);
      setSubjectId(conversation.subject_id);
      setDocumentId(conversation.document_id);
      setMessages(conversation.messages.map((item) => ({ role: item.role, text: item.content, sources: item.sources })));
      window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo abrir la conversación."); }
  }

  useEffect(() => {
    void refreshHistory(true);
    Promise.all([getDashboard(), getTasks()]).then(([nextDashboard, nextTasks]) => {
      setDashboard(nextDashboard);
      setTasks(nextTasks.tasks.map((item) => item.task));
    }).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!launchContext) return;
    setConversationId(undefined); setMessages([]); setSubjectId(launchContext.subjectId); setDocumentId(launchContext.documentId ?? null);
    window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }, [launchContext]);
  useEffect(() => {
    if (subjectId == null) { setDocuments([]); return; }
    getSubjectDocuments(subjectId).then((result) => setDocuments(result.documents)).catch(() => setDocuments([]));
  }, [subjectId]);
  useEffect(() => { if (!submitting) return; const timer = window.setInterval(() => setProgressIndex((value) => (value + 1) % progress.length), 1400); return () => window.clearInterval(timer); }, [submitting]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, submitting]);

  function newConversation() {
    setConversationId(undefined); setMessages([]); setError(null);
    setSubjectId(launchContext?.subjectId ?? null); setDocumentId(launchContext?.documentId ?? null);
    window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }

  async function removeConversation(id: string) {
    if (!window.confirm("¿Eliminar esta conversación y su memoria? Esta acción no afecta a tus datos académicos.")) return;
    try {
      await deleteConversation(id);
      if (conversationId === id) newConversation();
      await refreshHistory();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo eliminar la conversación."); }
  }

  async function submit(text: string) {
    const clean = text.trim(); if (!clean || submitting) return;
    setMessages((current) => [...current, { role: "user", text: clean }]); setInput(""); setSubmitting(true); setError(null); setProgressIndex(0);
    try {
      const result = await sendAgentMessage(clean, {
        conversationId,
        subjectId,
        documentId,
        contextType: documentId != null ? "document" : subjectId != null ? "subject" : "general",
        workContext: launchContext?.topic ? { topic: launchContext.topic, explanation: launchContext.explanation, sources: launchContext.sources } : undefined,
      });
      setConversationId(result.conversation_id);
      window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, result.conversation_id);
      if (result.answer) setMessages((current) => [...current, { role: "assistant", text: result.answer!, sources: result.sources, usage: result.usage }]);
      else setMessages((current) => [...current, { role: "assistant", text: "UniCore terminó la consulta sin una respuesta visible." }]);
      await refreshHistory();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo consultar UniCore Agent."); }
    finally { setSubmitting(false); }
  }

  function handleSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }
  async function createPrompt(event: FormEvent) {
    event.preventDefault();
    if (!promptObjective.trim() || buildingPrompt) return;
    setBuildingPrompt(true); setError(null); setPromptCopied(false);
    try {
      const result = await buildAcademicPrompt({
        objective: promptObjective,
        subject_id: subjectId,
        task_id: promptTaskId,
        document_id: documentId,
        include_professor: promptContext.professor,
        include_rubric: promptContext.rubric,
        include_academic_memory: promptContext.academicMemory,
        include_improvements: promptContext.improvements,
        include_strengths: promptContext.strengths,
      });
      setGeneratedPrompt(result.prompt);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo preparar el prompt."); }
    finally { setBuildingPrompt(false); }
  }
  async function copyPrompt() {
    if (!generatedPrompt) return;
    await navigator.clipboard.writeText(generatedPrompt);
    setPromptCopied(true);
    window.setTimeout(() => setPromptCopied(false), 1800);
  }
  const activeDocument = documents.find((item) => item.id === documentId);
  const availableTasks = tasks.filter((item) => subjectId == null || item.subject_id === subjectId);

  return <div className="uc-page-shell uc-agent-page">
    <header className="uc-agent-header"><div><p className="uc-eyebrow">UniCore Agent</p><h1>Asistencia con memoria académica.</h1><p>Las conversaciones persisten y los materiales se consultan mediante fragmentos relevantes.</p></div><div className="uc-agent-header-actions"><button className="uc-prompt-launch" onClick={() => setPromptBuilderOpen((value) => !value)}><Sparkles size={15} /> {promptBuilderOpen ? "Cerrar creador" : "Crear prompt"}</button><div className="uc-agent-policy"><ShieldCheck size={16} /><span><strong>Modo seguro</strong>Las escrituras están desactivadas</span></div></div></header>
    {promptBuilderOpen && <section className="uc-prompt-builder"><form onSubmit={createPrompt}><div className="uc-prompt-builder-copy"><p className="uc-eyebrow">Preparar prompt para ChatGPT</p><h2>Convierte contexto académico en instrucciones precisas.</h2><p>Selecciona solo el contexto que aporta valor; nunca se adjuntan documentos completos.</p></div><label><span>Objetivo</span><textarea value={promptObjective} onChange={(event) => setPromptObjective(event.target.value)} placeholder="Ej. Revisar mis conclusiones según la rúbrica" rows={4} /></label><div className="uc-prompt-fields"><label><span>Asignatura</span><select value={subjectId ?? ""} onChange={(event) => { const value = event.target.value ? Number(event.target.value) : null; setSubjectId(value); setPromptTaskId(null); setDocumentId(null); }}><option value="">Sin asignatura</option>{dashboard?.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label><label><span>Tarea</span><select value={promptTaskId ?? ""} onChange={(event) => setPromptTaskId(event.target.value ? Number(event.target.value) : null)}><option value="">Sin tarea concreta</option>{availableTasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label><label><span>Material</span><select value={documentId ?? ""} disabled={subjectId == null || documents.length === 0} onChange={(event) => setDocumentId(event.target.value ? Number(event.target.value) : null)}><option value="">{documents.length ? "Toda la asignatura" : "Sin materiales"}</option>{documents.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}</select></label></div><fieldset className="uc-prompt-context"><legend>¿Qué contexto quieres utilizar?</legend>{[["professor", "Profesor"], ["rubric", "Rúbrica"], ["academicMemory", "Academic Memory / asignaturas anteriores"], ["improvements", "Mis áreas de mejora"], ["strengths", "Mis fortalezas"]].map(([key, label]) => <label key={key}><input type="checkbox" checked={promptContext[key as keyof typeof promptContext]} onChange={(event) => setPromptContext((current) => ({ ...current, [key]: event.target.checked }))} /> {label}</label>)}<small>Contexto estimado: <strong>{promptContext.academicMemory && (promptContext.professor || promptContext.rubric) ? "Alto" : Object.values(promptContext).some(Boolean) ? "Medio" : "Bajo"}</strong></small></fieldset><button type="submit" className="uc-primary-action" disabled={buildingPrompt || !promptObjective.trim()}>{buildingPrompt ? "Preparando…" : "Crear prompt"}</button></form>{generatedPrompt && <div className="uc-prompt-result"><div><span>Prompt editable</span><button onClick={() => void copyPrompt()}>{promptCopied ? <Check size={14} /> : <Copy size={14} />}{promptCopied ? "Prompt copiado" : "Copiar prompt"}</button></div><textarea value={generatedPrompt} onChange={(event) => setGeneratedPrompt(event.target.value)} rows={16} aria-label="Prompt generado editable" /></div>}</section>}
    <section className="uc-agent-shell uc-agent-shell-persistent"><aside className="uc-agent-history"><button className="uc-new-conversation" onClick={newConversation}><MessageSquarePlus size={16} /> Nueva conversación</button><div className="uc-agent-history-heading"><span>Historial</span><small>{conversations.length}</small></div>{historyLoading ? <p>Cargando…</p> : conversations.length === 0 ? <div className="uc-agent-history-empty">Sin conversaciones previas.</div> : <div className="uc-agent-history-list">{conversations.map((item) => <div key={item.id} className={conversationId === item.id ? "is-active" : ""}><button onClick={() => void openConversation(item.id)}><strong>{item.title}</strong><span>{item.message_count} mensaje(s)</span></button><button onClick={() => void removeConversation(item.id)} aria-label={`Eliminar ${item.title}`}><Trash2 size={14} /></button></div>)}</div>}</aside>
      <div className="uc-conversation"><div className="uc-agent-scope"><BrainCircuit size={16} /><span>{activeDocument ? <>Documento: <strong>{activeDocument.title}</strong></> : subjectId != null ? <>Contexto: <strong>{launchContext?.subjectName ?? "Asignatura seleccionada"}</strong></> : <>Contexto: <strong>General</strong></>}</span>{subjectId != null && documents.length > 0 && <select value={documentId ?? ""} onChange={(event) => setDocumentId(event.target.value ? Number(event.target.value) : null)} aria-label="Alcance documental"><option value="">Toda la asignatura</option>{documents.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>}</div><div className="uc-message-stream">{messages.length === 0 ? <div className="uc-agent-empty"><Sparkles size={22} /><h2>¿Qué quieres entender?</h2><p>Empieza con una pregunta concreta. UniCore recuperará únicamente el contexto necesario.</p><div>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void submit(suggestion)}>{suggestion}</button>)}</div></div> : messages.map((message, index) => <article key={index} className={`uc-message is-${message.role === "assistant" ? "agent" : "user"}`}><span>{message.role === "user" ? "Tú" : "UniCore"}</span>{message.role === "assistant" ? <AcademicMarkdown content={message.text} sources={message.sources} /> : <p>{message.text}</p>}{message.sources?.length ? <div className="uc-message-sources">{message.sources.map((source) => <span key={`${source.source_number}-${source.document_id}`}><FileText size={12} /> {source.document_title}{source.source_label ? ` · ${source.source_label}` : ""}</span>)}</div> : null}{message.role === "assistant" && <TokenUsageNote usage={message.usage} sources={message.sources?.length ?? 0} />}</article>)}{submitting && <article className="uc-message is-agent is-working"><span>UniCore</span><p>{progress[progressIndex]}</p><i /><i /><i /></article>}{error && <div className="uc-agent-error"><span>{error}</span><button onClick={() => setError(null)} aria-label="Cerrar error"><RefreshCw size={14} /></button></div>}<div ref={endRef} /></div>
        <form className="uc-agent-composer" onSubmit={handleSubmit}><label htmlFor="agent-message" className="sr-only">Mensaje para UniCore Agent</label><textarea id="agent-message" value={input} onChange={(event) => setInput(event.target.value)} onInput={(event) => { event.currentTarget.style.height = "auto"; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 104)}px`; }} placeholder={activeDocument ? `Pregunta sobre ${activeDocument.title}…` : "Pregunta sobre tus tareas, asignaturas o progreso…"} rows={1} disabled={submitting} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button type="submit" disabled={submitting || !input.trim()} aria-label="Enviar mensaje"><ArrowUp size={17} /></button><small>Memoria reciente + resumen compacto · Enter para enviar</small></form>
      </div></section>
  </div>;
}
