import { ReactNode } from "react";

export default function Card({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`uc-panel ${className}`.trim()}>
      {(title || eyebrow || action) && (
        <header className="uc-panel-head">
          <div>
            {eyebrow && <p className="uc-eyebrow">{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {action && <div className="uc-panel-action">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
