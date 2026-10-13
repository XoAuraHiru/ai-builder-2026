"use client";

import { motion, useReducedMotion } from "motion/react";
import { useRef, useState } from "react";
import { EASE } from "@/components/motion";
import { formatDate, formatMonth, formatUsd } from "@/lib/format";
import { areaPath, linear, linePath, nearestIndex, niceTicks, type Point } from "@/lib/scale";

const W = 720;
const H = 240;
const M = { top: 12, right: 12, bottom: 26, left: 60 };
const QUARTERS = ["01", "04", "07", "10"];

/** About a year of daily closes on a linear scale, with the close and the date under the pointer. The line draws
 *  itself once, left to right, when the chart appears; the shading under it follows. */
export function PriceChart({ points, label }: { points: { day: string; close: number }[]; label: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const reduce = useReducedMotion();
  if (points.length < 2) return <p className="text-sm text-ink-500">There is not enough price history to draw a chart.</p>;

  const closes = points.map((p) => p.close);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  const pad = (hi - lo) * 0.08 || hi * 0.02;
  const x = linear([0, points.length - 1], [M.left, W - M.right]);
  const y = linear([lo - pad, hi + pad], [H - M.bottom, M.top]);
  const ticks = niceTicks(lo - pad, hi + pad, 4);
  const line: Point[] = points.map((p, i) => [x(i), y(p.close)]);
  const floor: Point[] = points.map((_, i) => [x(i), H - M.bottom]);
  const marks = points.map((p, i) => ({ i, day: p.day }))
    .filter(({ day }, k, all) => k > 0 && day.slice(5, 7) !== all[k - 1].day.slice(5, 7) && QUARTERS.includes(day.slice(5, 7)));
  const up = closes[closes.length - 1] >= closes[0];
  const point = hover === null ? null : points[hover];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setHover(nearestIndex(line.map((p) => p[0]), ((e.clientX - box.left) / box.width) * W));
  }

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full touch-none select-none" role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--color-sand-200)" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-500 text-[11px]">{formatUsd(t, t >= 1000 ? 0 : 2)}</text>
          </g>
        ))}
        {marks.map(({ i, day }) => (
          <text key={day} x={x(i)} y={H - 8} textAnchor="middle" className="num fill-ink-500 text-[11px]">{formatMonth(day.slice(0, 7))}</text>
        ))}
        <motion.path d={areaPath(line, floor)} fill={up ? "var(--color-green-500)" : "var(--color-coral-500)"} fillOpacity={0.08}
          initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.35, ease: EASE }} />
        <motion.path d={linePath(line)} fill="none" stroke={up ? "var(--color-green-500)" : "var(--color-coral-500)"} strokeWidth={2} strokeLinejoin="round"
          initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.6, ease: EASE }} />
        {point && hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} stroke="var(--color-sand-300)" />
            <circle cx={x(hover)} cy={y(point.close)} r={3.5} fill="var(--color-canvas)" stroke={up ? "var(--color-green-500)" : "var(--color-coral-500)"} strokeWidth={2} />
          </g>
        )}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom} fill="transparent"
          onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {point && hover !== null && (
        <div className="pointer-events-none absolute top-0 rounded-control border border-sand-200 bg-white px-2.5 py-1.5 text-xs shadow-float"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > points.length / 2 ? "-105%" : "5%"})` }}>
          <span className="num font-medium">{formatUsd(point.close)}</span> <span className="text-ink-500">{formatDate(point.day)}</span>
        </div>
      )}
    </div>
  );
}
