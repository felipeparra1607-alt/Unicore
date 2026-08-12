import { Check, Info, LayoutList, Settings2 } from "lucide-react";
import { useState } from "react";

type Density = "comfortable" | "compact";
function initialDensity(): Density { return window.localStorage.getItem("unicore-density") === "compact" ? "compact" : "comfortable"; }

export default function SettingsPage() {
  const [density, setDensity] = useState<Density>(initialDensity); const [saved, setSaved] = useState(false);
  function save() { window.localStorage.setItem("unicore-density", density); window.dispatchEvent(new Event("unicore-preferences-changed")); setSaved(true); window.setTimeout(() => setSaved(false), 1800); }
  return <div className="uc-page-shell uc-settings-page"><header className="uc-page-intro"><div><p className="uc-eyebrow">Preferencias</p><h1>Un espacio de trabajo a tu ritmo.</h1><p className="uc-page-subtitle">Solo configuraciones que cambian de forma útil cómo trabajas en UniCore.</p></div><div className="uc-date-chip"><Settings2 size={16} /> Preferencias locales</div></header><section className="uc-settings-minimal"><article><div><LayoutList size={18} /><div><p className="uc-eyebrow">Interfaz</p><h2>Densidad de información</h2><p>Compacta reduce los espacios verticales sin ocultar información académica.</p></div></div><div className="uc-density-options"><button className={density === "comfortable" ? "is-active" : ""} onClick={() => setDensity("comfortable")}><span>Cómoda</span><small>Más aire entre bloques</small></button><button className={density === "compact" ? "is-active" : ""} onClick={() => setDensity("compact")}><span>Compacta</span><small>Más información visible</small></button></div><footer><button className="uc-primary-action" onClick={save}>{saved ? <><Check size={16} /> Guardado</> : "Guardar preferencia"}</button></footer></article><aside><Info size={18} /><div><p className="uc-eyebrow">UniCore</p><h2>Academic Performance OS</h2><p>Las nuevas preferencias se incorporarán cuando aporten una mejora concreta al flujo académico.</p></div></aside></section></div>;
}
