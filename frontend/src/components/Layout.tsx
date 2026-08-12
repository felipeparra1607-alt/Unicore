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

function getInitialTheme(): Theme {
  const savedTheme = window.localStorage.getItem("unicore-theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
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
  const [theme, setTheme] = React.useState<Theme>(getInitialTheme);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("unicore-theme", theme);
  }, [theme]);

  const selectSection = (section: SectionId) => {
    onSection(section);
    setMobileOpen(false);
  };

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
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
              <span>Nivel 3</span>
              <strong>58 XP</strong>
            </div>
            <div className="uc-progress-track compact">
              <div className="uc-progress-fill" style={{ width: "58%" }} />
            </div>
            <small>42 XP para el siguiente nivel</small>
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
            aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            <span>{theme === "dark" ? "Claro" : "Oscuro"}</span>
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
