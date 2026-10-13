"use client";

import { motion } from "motion/react";
import { EASE } from "@/components/motion";
import { scaleMarks, type ScaleMark } from "@/lib/invest";

const FILL: Record<ScaleMark["fill"], string> = {
  profile: "bg-green-500", above: "bg-amber-400", calm: "bg-green-300", none: "bg-sand-200",
};
const CHIP: Record<NonNullable<ScaleMark["chip"]>["tone"], string> = {
  gain: "bg-green-50 text-green-700", caution: "bg-amber-50 text-amber-800", neutral: "bg-fill text-ink-700",
};
// The bands fill left to right, one after another, and each chip settles above its band once the band has filled.
const fillAt = (band: number) => 0.1 + 0.07 * (band - 1);

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
            <motion.span initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, delay: fillAt(m.band) + 0.22, ease: EASE }}
              className={`inline-flex min-h-6.5 max-w-full items-center rounded-[13px] px-2 py-1 text-[11px] font-semibold leading-3.5 sm:px-2.5 sm:text-xs sm:leading-4 ${CHIP[m.chip.tone]}`}>
              <span className="sm:hidden">{m.chip.short}</span><span className="hidden sm:inline">{m.chip.text}</span>
            </motion.span>
          )}
        </span>
      ))}
      {marks.map((m) => (
        <span key={`bar-${m.band}`} aria-hidden="true" className={`relative h-3 overflow-hidden rounded-md ${FILL.none}`}>
          {m.fill !== "none" && (
            <motion.span className={`absolute inset-0 origin-left rounded-md ${FILL[m.fill]}`}
              initial={{ opacity: 0, scaleX: 0 }} animate={{ opacity: 1, scaleX: 1 }}
              transition={{ duration: 0.34, delay: fillAt(m.band), ease: EASE }} />
          )}
        </span>
      ))}
      {marks.map((m) => (
        <span key={`name-${m.band}`} aria-hidden="true"
          className={`min-w-0 text-[11px] leading-4 wrap-anywhere sm:text-[13px] sm:leading-4.5 ${m.chip ? "font-semibold text-ink-900" : "text-ink-500"}`}>
          {m.chip ? m.label : <><span className="sm:hidden">{m.band}</span><span className="hidden sm:inline">{m.label}</span></>}
        </span>
      ))}
    </div>
  );
}
