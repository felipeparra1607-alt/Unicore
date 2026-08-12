import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  BriefcaseBusiness,
  CheckSquare2,
  GraduationCap,
  LayoutDashboard,
  Menu,
  Moon,
  Search,
  Settings,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import React from "react";
import { getDashboard, type DashboardData } from "../api";

const sections = [
  { id: "dashboard", label: "Inicio", icon: LayoutDashboard },
  { id: "subjects", label: "Asignaturas", icon: GraduationCap },
  { id: "tasks", label: "Tareas", icon: CheckSquare2 },
  { id: "study", label: "Estudio", icon: BookOpen },
  { id: "knowledge", label: "Conocimiento", icon: BarChart3 },
  { id: "agent", label: "Agent", icon: BrainCircuit },
  { id: "jobs", label: "Jobs", icon: BriefcaseBusiness },
  { id: "settings", label: "Ajustes", icon: Settings },
] as const;

export type SectionId = (typeof sections)[number]["id"];
type Theme = "light" | "dark";
type ThemePreference = Theme | "system";

function getInitialTheme(): ThemePreference {
  const savedTheme = window.localStorage.getItem("unicore-theme");
  if (savedTheme === "light" || savedTheme === "dark" || savedTheme === "system") {
    return savedTheme;
  }
  return "system";
}

export default function Layout({
  active,
  onSection,
  children,
}: {
  active: SectionId;
  onSection: (section: SectionId) => void;
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [theme, setTheme] = React.useState<ThemePreference>(getInitialTheme);
  const [resolvedTheme, setResolvedTheme] = React.useState<Theme>("light");
  const [profile, setProfile] = React.useState<DashboardData["hero"] | null>(null);

  React.useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      setResolvedTheme(resolved);
    };
    applyTheme();
    window.localStorage.setItem("unicore-theme", theme);
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [theme]);

  React.useEffect(() => {
    const applyPreferences = () => {
      setTheme(getInitialTheme());
      document.documentElement.dataset.density = window.localStorage.getItem("unicore-density") === "compact" ? "compact" : "comfortable";
    };
    applyPreferences();
    window.addEventListener("unicore-preferences-changed", applyPreferences);
    return () => window.removeEventListener("unicore-preferences-changed", applyPreferences);
  }, []);

  React.useEffect(() => { getDashboard().then((data) => setProfile(data.hero)).catch(() => setProfile(null)); }, []);

  const selectSection = (section: SectionId) => {
    onSection(section);
    setMobileOpen(false);
  };

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  return (
    <div className="uc-app">
      <aside className={`uc-sidebar ${mobileOpen ? "is-open" : ""}`}>
        <div className="uc-brand">
          <div className="uc-brand-mark">U</div>
          <div>
            <strong>UniCore</strong>
            <span>Academic OS</span>
          </div>
          <button className="uc-mobile-close" onClick={() => setMobileOpen(false)} aria-label="Cerrar menú">
            <X size={18} />
          </button>
        </div>

        <nav className="uc-nav" aria-label="Navegación principal">
          <p className="uc-nav-label">Espacio académico</p>
          {sections.map((section) => {
            const Icon = section.icon;
            const selected = active === section.id;
            return (
              <button
                key={section.id}
                className={`uc-nav-item ${selected ? "is-active" : ""}`}
                onClick={() => selectSection(section.id)}
              >
                <Icon size={17} strokeWidth={1.8} />
                <span>{section.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="uc-sidebar-foot">
          <div className="uc-mini-level">
            <div className="uc-mini-level-row">
              <span>{profile ? `Nivel ${profile.level}` : "Nivel —"}</span>
              <strong>{profile ? `${profile.total_xp} XP` : "— XP"}</strong>
            </div>
            <div className="uc-progress-track compact">
              <div className="uc-progress-fill" style={{ width: `${profile?.level_progress_percentage ?? 0}%` }} />
            </div>
            <small>{profile ? `${profile.xp_until_next_level} XP para el siguiente nivel` : "Progreso no disponible"}</small>
          </div>
          <button className="uc-agent-shortcut" onClick={() => selectSection("agent")}>
            <Sparkles size={16} />
            Preguntar a UniCore
          </button>
        </div>
      </aside>

      {mobileOpen && <button className="uc-overlay" aria-label="Cerrar menú" onClick={() => setMobileOpen(false)} />}

      <div className="uc-main-column">
        <header className="uc-topbar">
          <button className="uc-mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Abrir menú">
            <Menu size={19} />
          </button>
          <div className="uc-search">
            <Search size={16} />
            <span>Buscar asignaturas, tareas o conceptos</span>
            <kbd>⌘ K</kbd>
          </div>
          <button
            className="uc-theme-toggle"
            onClick={toggleTheme}
            aria-label={resolvedTheme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            title={resolvedTheme === "dark" ? "Modo claro" : "Modo oscuro"}
          >
            {resolvedTheme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            <span>{resolvedTheme === "dark" ? "Claro" : "Oscuro"}</span>
          </button>
          <div className="uc-topbar-status">
            <span className="uc-status-dot" />
            Backend listo
          </div>
        </header>
        <main className="uc-content">{children}</main>
      </div>
    </div>
  );
}
