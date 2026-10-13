import { useId, type ReactNode } from "react";

/** A page section as one outlined card: the card title (16/22, 600) and its description inside, then the content.
 *  Used by the advisor's lead pages, where every section is its own card. */
export function CardSection({ id, title, description, actions, className = "", children }:
  { id?: string; title: string; description?: ReactNode; actions?: ReactNode; className?: string; children: ReactNode }) {
  const heading = useId();
  return (
    <section id={id} aria-labelledby={heading}
      className={`min-w-0 scroll-mt-24 rounded-panel border border-sand-200 bg-white p-5 sm:p-6 ${className}`}>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <h2 id={heading} className="text-base font-semibold leading-[22px]">{title}</h2>
          {description && <p className="mt-1 max-w-[72ch] text-[13px] leading-5 text-ink-500">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
