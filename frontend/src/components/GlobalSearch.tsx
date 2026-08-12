import { Search, X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { getDashboard, getKnowledge, getTasks, type KnowledgeConcept } from "../api";

export type SearchDestination =
  | { kind: "subject"; subjectId: number }
  | { kind: "task" }
  | { kind: "knowledge"; subjectId: number };

type SearchResult = { id: string; group: "Asignaturas" | "Tareas" | "Conceptos"; title: string; detail: string; destination: SearchDestination };

export default function GlobalSearch({ onNavigate }: { onNavigate: (destination: SearchDestination) => void }) {
  const root = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const normalized = query.trim().toLocaleLowerCase();
  const isOpen = normalized.length >= 2;

  useEffect(() => {
    const closeWhenOutside = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setQuery(""); };
    document.addEventListener("mousedown", closeWhenOutside);
    return () => document.removeEventListener("mousedown", closeWhenOutside);
  }, []);

  useEffect(() => {
    if (!isOpen) { setResults([]); setActiveIndex(-1); return; }
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const [dashboard, tasks] = await Promise.all([getDashboard(), getTasks()]);
          const knowledge = await Promise.all(dashboard.subjects.map(async (subject) => {
            try { const data = await getKnowledge(subject.id); return { subject, concepts: data.concepts }; }
            catch { return { subject, concepts: [] as KnowledgeConcept[] }; }
          }));
          if (cancelled) return;
          const next: SearchResult[] = [
            ...dashboard.subjects.filter((subject) => subject.name.toLocaleLowerCase().includes(normalized)).map((subject) => ({ id: `subject-${subject.id}`, group: "Asignaturas" as const, title: subject.name, detail: "Abrir estado de la asignatura", destination: { kind: "subject" as const, subjectId: subject.id } })),
            ...tasks.tasks.filter(({ task }) => [task.title, task.description, task.subject_name].some((value) => value?.toLocaleLowerCase().includes(normalized))).map(({ task }) => ({ id: `task-${task.id}`, group: "Tareas" as const, title: task.title, detail: task.subject_name ?? "Tarea académica", destination: { kind: "task" as const } })),
            ...knowledge.flatMap(({ subject, concepts }) => concepts.filter((concept) => concept.name.toLocaleLowerCase().includes(normalized)).map((concept) => ({ id: `concept-${concept.id}`, group: "Conceptos" as const, title: concept.name, detail: subject.name, destination: { kind: "knowledge" as const, subjectId: subject.id } }))),
          ];
          setResults(next); setActiveIndex(next.length ? 0 : -1);
        } catch { if (!cancelled) { setResults([]); setActiveIndex(-1); } }
        finally { if (!cancelled) setLoading(false); }
      })();
    }, 180);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [isOpen, normalized]);

  const choose = (result: SearchResult) => { onNavigate(result.destination); setQuery(""); };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") setQuery("");
    else if (event.key === "ArrowDown" && results.length) { event.preventDefault(); setActiveIndex((current) => Math.min(current + 1, results.length - 1)); }
    else if (event.key === "ArrowUp" && results.length) { event.preventDefault(); setActiveIndex((current) => Math.max(current - 1, 0)); }
    else if (event.key === "Enter" && activeIndex >= 0) { event.preventDefault(); choose(results[activeIndex]); }
  };
  const groups = ["Asignaturas", "Tareas", "Conceptos"] as const;

  return <div className="uc-global-search" ref={root}><div className="uc-search"><Search size={16} /><label className="uc-sr-only" htmlFor="global-search">Buscar en UniCore</label><input id="global-search" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={onKeyDown} placeholder="Buscar asignaturas, tareas o conceptos" autoComplete="off" />{query && <button type="button" onClick={() => setQuery("")} aria-label="Limpiar búsqueda"><X size={14} /></button>}</div>{isOpen && <div className="uc-search-panel" role="listbox">{loading ? <p className="uc-search-state">Buscando en UniCore…</p> : results.length === 0 ? <p className="uc-search-state">No hay resultados para “{query.trim()}”.</p> : groups.map((group) => { const groupResults = results.filter((result) => result.group === group); return groupResults.length ? <section key={group} className="uc-search-group"><p>{group}</p>{groupResults.slice(0, 6).map((result) => { const index = results.indexOf(result); return <button key={result.id} className={index === activeIndex ? "is-active" : ""} onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(result)}><strong>{result.title}</strong><span>{result.detail}</span></button>; })}</section> : null; })}</div>}</div>;
}
