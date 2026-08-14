import type { TokenUsage } from "../api";

const format = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("es-ES").format(value);

export default function TokenUsageNote({ usage, sources = 0 }: { usage?: TokenUsage; sources?: number }) {
  const available = Boolean(usage?.available && usage.total_tokens != null);
  return (
    <details className="uc-token-usage">
      <summary>{available ? `${format(usage?.total_tokens)} tokens` : "Uso de tokens no disponible"}{sources ? ` · ${sources} fuentes` : ""}</summary>
      <div>
        <span>Input <strong>{format(usage?.input_tokens)}</strong></span>
        <span>Output <strong>{format(usage?.output_tokens)}</strong></span>
        <span>Total <strong>{format(usage?.total_tokens)}</strong></span>
        <span>Fuentes <strong>{sources}</strong></span>
      </div>
    </details>
  );
}
