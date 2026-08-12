import { AlertTriangle, BrainCircuit, Clock3, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDashboard, getKnowledge, type DashboardData, type KnowledgeConcept, type KnowledgeData } from "../api";

const statusCopy = {
  strong: { label: "Dominado", note: "Evidencia sólida" },
  developing: { label: "En desarrollo", note: "Consolidación activa" },
  weak: { label: "Débil", note: "Necesita atención" },
  unassessed: { label: "No evaluado", note: "Falta evidencia" },
};

function mastery(concept: KnowledgeConcept) { return concept.mastery_percentage == null ? "—" : `${concept.mastery_percentage.toFixed(0)}%`; }

export default function KnowledgePage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [data, setData] = useState<KnowledgeData | null>(null);
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [selected, setSelected] = useState<KnowledgeConcept | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadSubject(id: number) { setSubjectId(id); setLoading(true); setError(null); try { const knowledge = await getKnowledge(id); setData(knowledge); setSelected(knowledge.priority_concepts[0] ?? knowledge.concepts[0] ?? null); } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el mapa."); } finally { setLoading(false); } }
  async function load() { setLoading(true); setError(null); try { const nextDashboard = await getDashboard(); setDashboard(nextDashboard); const first = nextDashboard.subjects[0]; if (first) { setSubjectId(first.id); const knowledge = await getKnowledge(first.id); setData(knowledge); setSelected(knowledge.priority_concepts[0] ?? knowledge.concepts[0] ?? null); } } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el mapa."); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, []);
  const filtered = useMemo(() => (data?.concepts ?? []).filter((concept) => concept.name.toLocaleLowerCase("es").includes(query.toLocaleLowerCase("es"))), [data, query]);

  if (loading && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Conocimiento</p><h1>Construyendo tu mapa de dominio…</h1><p>Analizando conceptos y evidencias académicas reales.</p></section>;
  if (error && !data) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Conocimiento</p><h1>No se pudo conectar con UniCore.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={16} /></button></section>;
  if (!dashboard?.subjects.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Conocimiento</p><h1>No hay asignaturas que cartografiar.</h1><p>El mapa aparecerá cuando exista una asignatura registrada.</p></section>;

  return <div className="uc-page-shell uc-knowledge-page">
    <header className="uc-page-intro"><div><p className="uc-eyebrow">Knowledge Map</p><h1>Tu conocimiento, visible.</h1><p className="uc-page-subtitle">Una lectura operativa de lo que dominas, lo que está creciendo y lo que conviene estudiar después.</p></div><label className="uc-subject-select"><span>Asignatura</span><select value={subjectId ?? ""} onChange={(event) => void loadSubject(Number(event.target.value))}>{dashboard.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label></header>
    {data?.concepts.length === 0 ? <section className="uc-knowledge-empty"><BrainCircuit size={25} /><h2>Aún no hay conceptos registrados.</h2><p>El mapa se poblará con evidencias reales de estudio, quizzes y repasos.</p></section> : <>
      <section className="uc-knowledge-summary"><div className="uc-knowledge-overall"><span>Dominio global</span><strong>{data?.summary.overall_mastery_percentage != null ? `${data.summary.overall_mastery_percentage.toFixed(0)}%` : "—"}</strong><small>{data?.summary.assessed_concept_count ?? 0} de {data?.summary.concept_count ?? 0} conceptos evaluados</small></div>{(["strong","developing","weak","unassessed"] as const).map((status) => <div className={`uc-knowledge-count is-${status}`} key={status}><span>{statusCopy[status].label}</span><strong>{data?.summary[`${status}_count` as keyof KnowledgeData["summary"]] ?? 0}</strong><small>{statusCopy[status].note}</small></div>)}</section>
      <section className="uc-knowledge-workspace"><div className="uc-concept-map"><div className="uc-concept-map-head"><div><p className="uc-eyebrow">Distribución</p><h2>Conceptos por estado</h2></div><label className="uc-concept-search"><Search size={14} /><span className="sr-only">Buscar concepto</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar concepto" /></label></div><div className="uc-concept-columns">{(["weak","developing","unassessed","strong"] as const).map((status) => { const concepts = filtered.filter((concept) => concept.status === status); return <section key={status} className={`uc-concept-column is-${status}`}><header><strong>{statusCopy[status].label}</strong><span>{concepts.length}</span></header>{concepts.length ? concepts.map((concept) => <button key={concept.id} className={selected?.id === concept.id ? "is-active" : ""} onClick={() => setSelected(concept)}><span>{concept.name}</span><strong>{mastery(concept)}</strong><small><span className="uc-progress-track"><span className="uc-progress-fill" style={{ width: `${concept.mastery_percentage ?? 0}%` }} /></span>{concept.evidence_count} evidencia{concept.evidence_count === 1 ? "" : "s"}</small></button>) : <p>Sin conceptos</p>}</section>; })}</div></div>
        <aside className="uc-concept-detail"><p className="uc-eyebrow">Lectura del concepto</p>{selected ? <><span className={`uc-concept-state is-${selected.status}`}>{statusCopy[selected.status].label}</span><h2>{selected.name}</h2><div className="uc-concept-score"><strong>{mastery(selected)}</strong><span>dominio estimado</span></div><dl><div><dt><Clock3 size={14} /> Exposición</dt><dd>{selected.exposure_minutes} min</dd></div><div><dt>Evidencias</dt><dd>{selected.evidence_count}</dd></div><div><dt>Evaluadas</dt><dd>{selected.assessed_evidence_count}</dd></div></dl>{selected.status === "weak" || selected.status === "unassessed" ? <div className="uc-concept-next"><AlertTriangle size={15} /><span><strong>Próximo foco sugerido</strong>Prioriza este concepto en tu siguiente bloque de estudio.</span></div> : <p className="uc-concept-guidance">Mantén el concepto activo mediante repasos periódicos.</p>}</> : <div className="uc-empty-inline">Selecciona un concepto para ver su evidencia.</div>}</aside></section>
    </>}
  </div>;
}
