"use client";

import { motion, useReducedMotion } from "motion/react";
import { EASE } from "@/components/motion";
import { formatUsd } from "@/lib/format";

export type Slice = { key: string; label: string; value: number; color: string };

/** Shares of a whole as one bar on a sand track, with hairline gaps, and a legend that carries the exact figures. The
 *  shares draw in from the left when the bar appears (the track stays put), so the proportions read as they arrive. */
export function AllocationBar({ slices, total, title }: { slices: Slice[]; total?: number; title?: string }) {
  const reduce = useReducedMotion();
  const rows = [...slices].filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
  const sum = total ?? rows.reduce((s, x) => s + x.value, 0);
  const pct = (v: number) => (sum ? (v / sum) * 100 : 0);
  return (
    <figure className="min-w-0">
      {title && <figcaption className="mb-3 text-base font-semibold">{title}</figcaption>}
      <div className="h-3 w-full overflow-hidden rounded-full bg-sand-100" aria-hidden="true">
        <motion.div className="flex h-full w-full gap-[2px]"
          initial={reduce ? false : { clipPath: "inset(0% 100% 0% 0%)" }} animate={{ clipPath: "inset(0% 0% 0% 0%)" }}
          transition={{ duration: 0.6, ease: EASE }}>
          {rows.map((s) => <span key={s.key} className="h-full first:rounded-l-full last:rounded-r-full" style={{ flexGrow: s.value, flexBasis: 0, background: s.color }} />)}
        </motion.div>
      </div>
      <ul className="mt-3 divide-y divide-sand-100 text-sm">
        {rows.map((s) => (
          <li key={s.key} className="flex items-center gap-3 py-2">
            <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            <span className="num w-12 text-right text-ink-500 sm:w-14">{pct(s.value).toFixed(1)}%</span>
            <span className="num w-24 text-right sm:w-28">{formatUsd(s.value)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
