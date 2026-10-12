import { ACTS, type Act } from "@/lib/personas";

const PLACE: Record<Act, string> = {
  acquire: "col-start-1 row-start-1", invest: "col-start-3 row-start-1",
  trade: "col-start-3 row-start-3", operate: "col-start-1 row-start-3",
};

function Arrow({ className, rotate }: { className: string; rotate: number }) {
  return (
    <div className={`flex items-center justify-center ${className}`} aria-hidden="true">
      <svg width="48" height="12" viewBox="0 0 48 12" style={{ transform: `rotate(${rotate}deg)` }}>
        <path d="M2 6h42M38 1l7 5-7 5" fill="none" stroke="#8c979f" strokeWidth="1.4" />
      </svg>
    </div>
  );
}

/** Atrium as a floor plan: four rooms, one per stage, around a lit well, which is the shared ledger and AI decision log. */
export function PlanDiagram() {
  return (
    <figure aria-label="How Atrium is laid out: four stages around one ledger" className="m-0">
      <div className="grid w-full grid-cols-[minmax(0,1fr)_56px_minmax(0,1fr)] grid-rows-[auto_56px_auto] sm:aspect-square sm:grid-cols-[minmax(0,1fr)_112px_minmax(0,1fr)] sm:grid-rows-[minmax(0,1fr)_112px_minmax(0,1fr)]">
        {ACTS.map((a) => (
          <div key={a.key} className={`${PLACE[a.key]} flex min-w-0 flex-col gap-2 rounded-panel border border-line bg-surface p-3.5 sm:p-5`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="wide text-[16px] font-semibold sm:text-[21px]">{a.label}</span>
              <span className="num text-[13px] text-muted">{a.number}</span>
            </div>
            <p className="text-[12.5px] leading-snug text-ink-2 sm:text-sm">{a.line}</p>
            <p className="mt-auto hidden items-center gap-2 text-[13px] text-daylight-ink sm:flex">
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />{a.ai}
            </p>
          </div>
        ))}
        <Arrow className="col-start-2 row-start-1" rotate={0} />
        <Arrow className="col-start-3 row-start-2" rotate={90} />
        <Arrow className="col-start-2 row-start-3" rotate={180} />
        <div className="col-start-2 row-start-2 p-1.5 sm:p-2.5">
          <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-ink">
            <div className="h-[44%] w-[44%] rounded-[4px] bg-daylight shadow-[0_0_36px_10px_rgba(227,167,47,0.35)]" />
          </div>
        </div>
      </div>
      <figcaption className="mt-4 max-w-[38em] text-sm text-ink-2">
        At the centre is one ledger and one log of every AI decision, with its model and its cost. Every figure Gemini writes is
        checked against the engine that produced it.
      </figcaption>
    </figure>
  );
}
