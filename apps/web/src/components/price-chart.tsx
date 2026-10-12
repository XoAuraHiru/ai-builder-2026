"use client";

import { useRef, useState } from "react";
import { formatDate, formatMonth, formatUsd } from "@/lib/format";
import { areaPath, linear, linePath, nearestIndex, niceTicks, type Point } from "@/lib/scale";

const W = 720;
const H = 240;
const M = { top: 12, right: 12, bottom: 26, left: 60 };
const QUARTERS = ["01", "04", "07", "10"];

/** About a year of daily closes on a linear scale, with the close and the date under the pointer. */
export function PriceChart({ points, label }: { points: { day: string; close: number }[]; label: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) return <p className="text-sm text-muted">There is not enough price history to draw a chart.</p>;

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
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--color-line)" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-muted text-[11px]">{formatUsd(t, t >= 1000 ? 0 : 2)}</text>
          </g>
        ))}
        {marks.map(({ i, day }) => (
          <text key={day} x={x(i)} y={H - 8} textAnchor="middle" className="num fill-muted text-[11px]">{formatMonth(day.slice(0, 7))}</text>
        ))}
        <path d={areaPath(line, floor)} fill={up ? "var(--color-gain)" : "var(--color-loss)"} fillOpacity={0.06} />
        <path d={linePath(line)} fill="none" stroke="var(--color-ink)" strokeWidth={1.5} strokeLinejoin="round" />
        {point && hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} stroke="var(--color-line-strong)" />
            <circle cx={x(hover)} cy={y(point.close)} r={3.5} fill="var(--color-surface)" stroke="var(--color-ink)" strokeWidth={1.5} />
          </g>
        )}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom} fill="transparent"
          onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {point && hover !== null && (
        <div className="pointer-events-none absolute top-0 rounded-control border border-line bg-surface px-2 py-1 text-xs"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > points.length / 2 ? "-105%" : "5%"})` }}>
          <span className="num font-medium">{formatUsd(point.close)}</span> <span className="text-muted">{formatDate(point.day)}</span>
        </div>
      )}
    </div>
  );
}
