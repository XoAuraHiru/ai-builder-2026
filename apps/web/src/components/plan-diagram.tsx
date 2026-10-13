import { ACTS, type Act } from "@/lib/personas";
import { Sparkle } from "@/components/ui";

const PLACE: Record<Act, string> = {
  acquire: "col-start-1 row-start-1", invest: "col-start-3 row-start-1",
  trade: "col-start-3 row-start-3", operate: "col-start-1 row-start-3",
};

function Arrow({ className, rotate }: { className: string; rotate: number }) {
  return (
    <div className={`flex items-center justify-center ${className}`} aria-hidden="true">
      <svg width="44" height="12" viewBox="0 0 44 12" style={{ transform: `rotate(${rotate}deg)` }}>
        <path d="M2 6h38M35 1.5l5 4.5-5 4.5" fill="none" stroke="var(--color-green-400)" strokeWidth="1.6"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

/** Atrium as a floor plan: four rooms, one per stage, around a lit well, which is the shared ledger and AI decision log.
 *  The rooms are outlined cards; the well is green, because it holds records (the ledger and the log), not Gemini's words. */
export function PlanDiagram() {
  return (
    <figure aria-label="How Atrium is laid out: four stages around one ledger" className="m-0">
      <div className="grid w-full grid-cols-[minmax(0,1fr)_52px_minmax(0,1fr)] grid-rows-[auto_52px_auto] sm:aspect-square sm:grid-cols-[minmax(0,1fr)_108px_minmax(0,1fr)] sm:grid-rows-[minmax(0,1fr)_108px_minmax(0,1fr)]">
        {ACTS.map((a) => (
          <div key={a.key} className={`${PLACE[a.key]} flex min-w-0 flex-col gap-2 rounded-panel border border-sand-200 bg-white p-3.5 sm:gap-2.5 sm:p-5`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[15px] font-semibold leading-5 sm:text-[17px] sm:leading-6">{a.label}</span>
              <span className="code text-ink-500">0{a.number}</span>
            </div>
            <p className="text-[12.5px] leading-4.5 text-ink-700 sm:text-sm sm:leading-5.25">{a.line}</p>
            <p className="mt-auto hidden items-start gap-1.5 pt-1 text-[13px] font-medium leading-4.5 text-ai-700 sm:flex">
              <span className="mt-0.5 shrink-0"><Sparkle size={12} /></span>{a.ai}
            </p>
          </div>
        ))}
        <Arrow className="col-start-2 row-start-1" rotate={0} />
        <Arrow className="col-start-3 row-start-2" rotate={90} />
        <Arrow className="col-start-2 row-start-3" rotate={180} />
        <div className="col-start-2 row-start-2 p-1 sm:p-2">
          <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-green-50 sm:rounded-[18px]">
            <div className="h-[34%] w-[34%] rounded-[5px] bg-green-500 shadow-[0_0_0_5px_var(--color-green-100),0_0_0_10px_var(--color-green-200)] sm:rounded-[7px] sm:shadow-[0_0_0_8px_var(--color-green-100),0_0_0_16px_var(--color-green-200)]" />
          </div>
        </div>
      </div>
      <figcaption className="mt-5 max-w-[40em] text-sm leading-5.25 text-ink-700">
        At the centre is one ledger and one log of every AI decision, with its model and its cost. Every figure Gemini writes is
        checked against the engine that produced it.
      </figcaption>
    </figure>
  );
}
