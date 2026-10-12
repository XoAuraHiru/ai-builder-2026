"use client";

import { useRef, useState } from "react";
import { compactUsd, formatMonth, formatUsd } from "@/lib/format";
import { areaPath, linear, linePath, logTicks, nearestIndex, niceTicks, type Point } from "@/lib/scale";

const W = 720;
const H = 260;
const M = { top: 16, right: 16, bottom: 28, left: 56 };

/** Growth of $10,000 on a log scale (equal percentage moves look the same size), with the largest fall shaded. */
export function GrowthChart({ points, shade }:
  { points: { month: string; value: number }[]; shade?: { from: string; to: string; label: string } }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const values = points.map((p) => p.value);
  const lo = Math.min(...values) * 0.9;
  const hi = Math.max(...values) * 1.08;
  const x = linear([0, points.length - 1], [M.left, W - M.right]);
  const ly = linear([Math.log10(lo), Math.log10(hi)], [H - M.bottom, M.top]);
  const y = (v: number) => ly(Math.log10(v));
  const decades = logTicks(lo, hi);
  const ticks = decades.length >= 3 ? decades : niceTicks(lo, hi, 4).filter((t) => t > 0);
  const line: Point[] = points.map((p, i) => [x(i), y(p.value)]);
  const floor: Point[] = points.map((_, i) => [x(i), H - M.bottom]);
  const yearMarks = points.map((p, i) => ({ i, month: p.month }))
    .filter(({ month }) => month.endsWith("-01") && Number(month.slice(0, 4)) % 4 === 0);
  const from = shade ? points.findIndex((p) => p.month === shade.from) : -1;
  const to = shade ? points.findIndex((p) => p.month === shade.to) : -1;
  const point = hover === null ? null : points[hover];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setHover(nearestIndex(line.map((p) => p[0]), ((e.clientX - box.left) / box.width) * W));
  }

  const first = points[0];
  const last = points[points.length - 1];
  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full touch-none select-none" role="img"
        aria-label={`$10,000 invested in ${formatMonth(first.month)} grew to ${formatUsd(last.value, 0)} by ${formatMonth(last.month)}.`}>
        {from >= 0 && to >= from && (
          <g>
            <rect x={x(from)} y={M.top} width={Math.max(2, x(to) - x(from))} height={H - M.top - M.bottom} fill="var(--color-caution-wash)" />
            <text x={x(from) + 4} y={M.top + 12} className="fill-caution text-[11px] font-medium">{shade?.label}</text>
          </g>
        )}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--color-line)" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-muted text-[11px]">{compactUsd(t)}</text>
          </g>
        ))}
        {yearMarks.map(({ i, month }) => (
          <text key={month} x={x(i)} y={H - 8} textAnchor="middle" className="num fill-muted text-[11px]">{month.slice(0, 4)}</text>
        ))}
        <path d={areaPath(line, floor)} fill="var(--color-ink)" fillOpacity={0.05} />
        <path d={linePath(line)} fill="none" stroke="var(--color-ink)" strokeWidth={1.75} strokeLinejoin="round" />
        {point && hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} stroke="var(--color-ink)" strokeOpacity={0.3} />
            <circle cx={x(hover)} cy={y(point.value)} r={3.5} fill="var(--color-ink)" />
          </g>
        )}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {point && hover !== null && (
        <div className="pointer-events-none absolute top-2 rounded-control border border-line bg-surface px-3 py-2 text-xs shadow-[0_8px_24px_-12px_rgba(23,32,42,0.35)]"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: x(hover) > W * 0.6 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" }}>
          <p className="font-medium">{formatMonth(point.month)}</p>
          <p className="num text-ink-2">{formatUsd(point.value, 0)}</p>
        </div>
      )}
    </div>
  );
}
