"use client";

import { motion } from "motion/react";
import { EASE } from "@/components/motion";
import { linear, niceTicks } from "@/lib/scale";

const W = 720;
const H = 190;
const M = { top: 12, right: 8, bottom: 26, left: 40 };

/** Calendar-year returns around a zero line. A partial first or last year is drawn lighter. Each bar grows out of the
 *  zero line, up for a gain and down for a loss, one year after another. */
export function YearBars({ years }: { years: { year: number; return_pct: number; months: number }[] }) {
  const values = years.map((y) => y.return_pct);
  const lo = Math.min(...values, 0) * 1.12;
  const hi = Math.max(...values, 0) * 1.12;
  const y = linear([lo, hi], [H - M.bottom, M.top]);
  const band = (W - M.left - M.right) / years.length;
  const step = Math.min(0.025, 0.4 / Math.max(1, years.length));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img"
      aria-label={years.map((r) => `${r.year}: ${r.return_pct}%`).join("; ")}>
      {niceTicks(lo, hi, 3).map((t) => (
        <g key={t}>
          <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--color-ink-400)" : "var(--color-sand-200)"} />
          <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-500 text-[10.5px]">{t}%</text>
        </g>
      ))}
      {years.map((r, i) => {
        const top = y(Math.max(r.return_pct, 0));
        const bottom = y(Math.min(r.return_pct, 0));
        const gain = r.return_pct >= 0;
        return (
          <g key={r.year}>
            <motion.rect x={M.left + i * band + band * 0.18} width={band * 0.64} y={top} height={Math.max(1, bottom - top)} rx={2}
              fill={gain ? "var(--color-green-500)" : "var(--color-coral-500)"} fillOpacity={r.months === 12 ? 1 : 0.45}
              style={{ transformBox: "fill-box", transformOrigin: gain ? "50% 100%" : "50% 0%" }}
              initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ duration: 0.4, delay: 0.1 + step * i, ease: EASE }}>
              <title>{`${r.year}${r.months < 12 ? ` (${r.months} months)` : ""}: ${r.return_pct > 0 ? "+" : ""}${r.return_pct}%`}</title>
            </motion.rect>
            {i % 2 === 0 && (
              <text x={M.left + i * band + band / 2} y={H - 8} textAnchor="middle" className="num fill-ink-500 text-[10.5px]">
                {`'${String(r.year).slice(2)}`}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
