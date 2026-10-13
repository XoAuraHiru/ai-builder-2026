"use client";

import { useRef, useState } from "react";
import { unitStats, type UnitPoint } from "@/lib/analyzer";
import { formatDate, formatPct } from "@/lib/format";
import { linear, linePath, nearestIndex, niceTicks, type Point } from "@/lib/scale";

const W = 720;
const H = 260;
const M = { top: 16, right: 16, bottom: 28, left: 52 };

/** A fund's unit price over the range shown. Before launch the line is the backtest of its ETF mix, drawn dashed. */
export function UnitPriceChart({ points, inception }: { points: UnitPoint[]; inception: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) return null;
  const prices = points.map((p) => p.price);
  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  const pad = (hi - lo) * 0.08 || 1;
  const ticks = niceTicks(lo - pad, hi + pad, 4);
  // Time on x, so two years of daily prices take two years of width beside the monthly backtest.
  const times = points.map((p) => Date.parse(`${p.date}T00:00:00Z`));
  const tx = linear([times[0], times[times.length - 1]], [M.left, W - M.right]);
  const x = (i: number) => tx(times[i]);
  const y = linear([lo - pad, hi + pad], [H - M.bottom, M.top]);
  const line: Point[] = points.map((p, i) => [x(i), y(p.price)]);
  const split = points.findIndex((p) => !p.backtest);
  const before = split === -1 ? line : line.slice(0, split + 1);
  const after = split === -1 ? [] : line.slice(split);
  const span = Number(points[points.length - 1].date.slice(0, 4)) - Number(points[0].date.slice(0, 4));
  const every = span > 12 ? 4 : span > 5 ? 2 : 1;
  const yearMarks = points.map((p, i) => ({ i, year: p.date.slice(0, 4) }))
    .filter(({ i, year }) => i > 0 && points[i - 1].date.slice(0, 4) !== year && Number(year) % every === 0);
  const stats = unitStats(points);
  const point = hover === null ? null : points[hover];
  const first = points[0];
  const last = points[points.length - 1];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setHover(nearestIndex(line.map((p) => p[0]), ((e.clientX - box.left) / box.width) * W));
  }

  const summary = `Unit price from ${formatDate(first.date)} to ${formatDate(last.date)}: ${first.price.toFixed(2)} to `
    + `${last.price.toFixed(2)}${stats ? `, a change of ${formatPct(stats.changePct, 1, true)}, with a largest fall of `
    + `${formatPct(stats.fallPct)}` : ""}.${split !== 0 ? ` Prices before ${formatDate(inception)} are a backtest.` : ""}`;

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full touch-none select-none" role="img" aria-label={summary}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--color-sand-100)" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-500 text-[11px]">{t.toFixed(hi - lo < 10 ? 1 : 0)}</text>
          </g>
        ))}
        {yearMarks.map(({ i, year }) => (
          <text key={year} x={x(i)} y={H - 8} textAnchor="middle" className="num fill-ink-500 text-[11px]">{year}</text>
        ))}
        {split > 0 && (
          <g>
            <line x1={x(split)} x2={x(split)} y1={M.top} y2={H - M.bottom} stroke="var(--color-sand-300)" strokeDasharray="2 3" />
            <text x={x(split) - 6} y={M.top + 10} textAnchor="end" className="fill-ink-500 text-[11px]">Backtest</text>
            <text x={x(split) + 6} y={M.top + 10} className="fill-ink-700 text-[11px] font-medium">Published</text>
          </g>
        )}
        {before.length > 1 && (
          <path d={linePath(before)} fill="none" stroke="var(--color-green-300)" strokeWidth={1.5} strokeDasharray="4 3" />
        )}
        {after.length > 1 && <path d={linePath(after)} fill="none" stroke="var(--color-green-500)" strokeWidth={2} strokeLinejoin="round" />}
        {point && hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} stroke="var(--color-green-700)" strokeOpacity={0.3} />
            <circle cx={x(hover)} cy={y(point.price)} r={4} fill="var(--color-green-500)" stroke="white" strokeWidth={1.5} />
          </g>
        )}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {point && hover !== null && (
        <div className="pointer-events-none absolute top-2 rounded-control border border-sand-200 bg-white px-3 py-2 text-xs shadow-float"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: x(hover) > W * 0.6 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" }}>
          <p className="font-medium">{formatDate(point.date)}</p>
          <p className="num text-ink-700">{point.price.toFixed(2)} a unit{point.backtest ? " (backtest)" : ""}</p>
        </div>
      )}
    </div>
  );
}
