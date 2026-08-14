import { Clock3, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { DecisionAction } from "../api";
import { suggestedDuration, workDurations } from "../workSession";

export default function WorkBlockDialog({
  action,
  onClose,
  onStart,
}: {
  action: DecisionAction;
  onClose: () => void;
  onStart: (duration: number) => void;
}) {
  const [duration, setDuration] = useState(suggestedDuration(action.allocated_minutes || action.suggested_minutes));

  useEffect(() => {
    setDuration(suggestedDuration(action.allocated_minutes || action.suggested_minutes));
  }, [action]);

  return (
    <div className="uc-form-backdrop" onMouseDown={onClose}>
      <section className="uc-form-modal uc-work-start-modal" role="dialog" aria-modal="true" aria-labelledby="work-start-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div>
            <p className="uc-eyebrow">Bloque de trabajo</p>
            <h2 id="work-start-title">Elige cuánto tiempo vas a dedicar.</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar"><X size={18} /></button>
        </header>
        <div className="uc-work-start-context">
          <span>{action.subject_name ?? "Trabajo académico"}</span>
          <strong>{action.title}</strong>
          {action.reasons.length > 0 && <p>{action.reasons.join(" ")}</p>}
        </div>
        <div className="uc-work-duration-options" aria-label="Duración del bloque">
          {workDurations.map((minutes) => (
            <button key={minutes} className={duration === minutes ? "is-active" : ""} onClick={() => setDuration(minutes)}>
              <strong>{minutes}</strong><span>min</span>
            </button>
          ))}
        </div>
        <footer>
          <button type="button" onClick={onClose}>Cancelar</button>
          <button type="button" className="uc-primary-action" onClick={() => onStart(duration)}>
            Empezar <Clock3 size={16} />
          </button>
        </footer>
      </section>
    </div>
  );
}
