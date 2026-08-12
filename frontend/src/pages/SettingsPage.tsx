import { Check, Monitor, Moon, Settings2, Sun } from "lucide-react";
import { useState } from "react";

type ThemePreference = "light" | "dark" | "system";
type Density = "comfortable" | "compact";

function initialTheme(): ThemePreference { const value = window.localStorage.getItem("unicore-theme"); return value === "light" || value === "dark" || value === "system" ? value : "system"; }
function initialDuration() { const value = Number(window.localStorage.getItem("unicore-plan-duration")); return [15,30,45,60,90].includes(value) ? value : 60; }
function initialDensity(): Density { return window.localStorage.getItem("unicore-density") === "compact" ? "compact" : "comfortable"; }

export default function SettingsPage() {
  const [theme, setTheme] = useState<ThemePreference>(initialTheme);
  const [duration, setDuration] = useState(initialDuration);
  const [density, setDensity] = useState<Density>(initialDensity);
  const [saved, setSaved] = useState(false);

  function save() {
    window.localStorage.setItem("unicore-theme", theme);
    window.localStorage.setItem("unicore-plan-duration", String(duration));
    window.localStorage.setItem("unicore-density", density);
    window.dispatchEvent(new Event("unicore-preferences-changed"));
    setSaved(true); window.setTimeout(() => setSaved(false), 1800);
  }

  return <div className="uc-page-shell uc-settings-page"><header className="uc-page-intro"><div><p className="uc-eyebrow">Preferencias locales</p><h1>Ajusta tu espacio de trabajo.</h1><p className="uc-page-subtitle">Configuración visual y de planificación guardada únicamente en este navegador.</p></div><div className="uc-date-chip"><Settings2 size={16} />Sincronización local</div></header><section className="uc-settings-layout"><nav><p className="uc-eyebrow">Ajustes</p><span className="is-active">Apariencia y trabajo</span><small>No se exponen claves, secretos ni configuración interna del backend.</small></nav><div className="uc-settings-form"><section><div><p className="uc-eyebrow">Apariencia</p><h2>Tema de interfaz</h2><p>Elige una preferencia fija o sigue el tema configurado en tu sistema.</p></div><div className="uc-theme-options">{([{value:"light",label:"Claro",icon:Sun},{value:"dark",label:"Oscuro",icon:Moon},{value:"system",label:"Sistema",icon:Monitor}] as const).map(({value,label,icon:Icon}) => <button key={value} className={theme === value ? "is-active" : ""} onClick={() => setTheme(value)}><Icon size={17} /><span>{label}</span>{theme === value && <Check size={14} />}</button>)}</div></section><section><div><p className="uc-eyebrow">Planificación</p><h2>Duración predeterminada</h2><p>Se utilizará como punto de partida en “Planifica tu tiempo”.</p></div><div className="uc-setting-durations">{[15,30,45,60,90].map((value) => <button key={value} className={duration === value ? "is-active" : ""} onClick={() => setDuration(value)}>{value}<span>min</span></button>)}</div></section><section><div><p className="uc-eyebrow">Densidad</p><h2>Ritmo visual</h2><p>Compacta reduce espacios verticales sin ocultar información académica.</p></div><div className="uc-density-options"><button className={density === "comfortable" ? "is-active" : ""} onClick={() => setDensity("comfortable")}><span>Cómoda</span><small>Más aire entre bloques</small></button><button className={density === "compact" ? "is-active" : ""} onClick={() => setDensity("compact")}><span>Compacta</span><small>Más información visible</small></button></div></section><footer><button className="uc-primary-action" onClick={save}>{saved ? <><Check size={16} /> Preferencias guardadas</> : "Guardar cambios"}</button><span>Estas preferencias no modifican tu información académica.</span></footer></div></section></div>;
}
