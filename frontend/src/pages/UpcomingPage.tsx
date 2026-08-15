import { ArrowUpRight } from "lucide-react";
import { roadmapItems } from "../roadmap";

export default function UpcomingPage() {
  return <div className="uc-page-shell uc-upcoming-page"><header className="uc-page-intro"><div><p className="uc-eyebrow">Próximamente</p><h1>Lo que viene después.</h1><p className="uc-page-subtitle">Capacidades previstas, separadas del trabajo académico que ya puedes usar.</p></div></header><section className="uc-roadmap-ledger"><header><span>Capacidad</span><span>Área</span><span>Estado</span></header>{roadmapItems.map((item) => <article key={item.title}><div><ArrowUpRight size={15} /><span><strong>{item.title}</strong><p>{item.description}</p></span></div><span>{item.area}</span><em>{item.status}</em></article>)}</section></div>;
}
