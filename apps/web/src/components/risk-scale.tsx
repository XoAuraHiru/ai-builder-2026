import { scaleMarks, type ScaleMark } from "@/lib/invest";

const FILL: Record<ScaleMark["fill"], string> = {
  profile: "bg-green-500", above: "bg-amber-400", calm: "bg-green-300", none: "bg-sand-200",
};
const CHIP: Record<NonNullable<ScaleMark["chip"]>["tone"], string> = {
  gain: "bg-green-50 text-green-700", caution: "bg-amber-50 text-amber-800", neutral: "bg-fill text-ink-700",
};

/** One sand scale of the five risk bands. Green fills the profile's band, amber fills where the portfolio is now when
 *  it sits above the profile, and each marked band carries a chip above it, so the two never rest on colour alone.
 *  Three grid rows (chips, bars, names) keep the bars level when a chip wraps on a phone. */
export function RiskScale({ profile, portfolio }: { profile: number | null; portfolio: number }) {
  const marks = scaleMarks(profile, portfolio);
  const name = (band: number) => marks[band - 1].label.slice(2);
  const said = profile
    ? `Risk scale from 1 to 5: your profile is band ${profile}, ${name(profile)}; your portfolio behaves like band ${portfolio}, ${name(portfolio)}`
    : `Risk scale from 1 to 5: your portfolio behaves like band ${portfolio}, ${name(portfolio)}`;
  return (
    <div role="img" aria-label={said} className="grid grid-cols-5 gap-x-1.5 gap-y-2">
      {marks.map((m) => (
        <span key={`chip-${m.band}`} aria-hidden="true" className="flex min-h-6.5 min-w-0 items-end">
          {m.chip && (
            <span className={`inline-flex min-h-6.5 max-w-full items-center rounded-[13px] px-2 py-1 text-[11px] font-semibold leading-3.5 sm:px-2.5 sm:text-xs sm:leading-4 ${CHIP[m.chip.tone]}`}>
              {m.chip.text}
            </span>
          )}
        </span>
      ))}
      {marks.map((m) => <span key={`bar-${m.band}`} aria-hidden="true" className={`h-3 rounded-md ${FILL[m.fill]}`} />)}
      {marks.map((m) => (
        <span key={`name-${m.band}`} aria-hidden="true"
          className={`min-w-0 text-[11px] leading-4 wrap-anywhere sm:text-[13px] sm:leading-4.5 ${m.chip ? "font-semibold text-ink-900" : "text-ink-500"}`}>
          {m.chip ? m.label : <><span className="sm:hidden">{m.band}</span><span className="hidden sm:inline">{m.label}</span></>}
        </span>
      ))}
    </div>
  );
}
