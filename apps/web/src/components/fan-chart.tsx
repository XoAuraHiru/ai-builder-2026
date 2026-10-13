"use client";

import { motion, useReducedMotion } from "motion/react";
import { useId, useMemo, useRef, useState } from "react";
import { compactUsd, formatUsd } from "@/lib/format";
import type { ScenarioOut, YearPoint } from "@/lib/invest";
import { areaPath, linear, linePath, nearestIndex, niceTicks, type Point } from "@/lib/scale";

const W = 720;
const H = 340;
const M = { top: 18, right: 112, bottom: 30, left: 58 };
const EASE = [0.22, 1, 0.36, 1] as const;

/** Push end labels apart so none overlap, keeping them inside the plot. */
function spread(items: { key: string; y: number }[], gap: number, min: number, max: number): Record<string, number> {
  const sorted = [...items].sort((a, b) => a.y - b.y).map((s) => ({ ...s }));
  for (let i = 1; i < sorted.length; i++) if (sorted[i].y - sorted[i - 1].y < gap) sorted[i].y = sorted[i - 1].y + gap;
  const overflow = sorted.length ? sorted[sorted.length - 1].y - max : 0;
  if (overflow > 0) sorted.forEach((s) => (s.y -= overflow));
  return Object.fromEntries(sorted.map((s) => [s.key, Math.max(min, s.y)]));
}

/**
 * The What-if fan: 10,000 simulated futures as bands spreading out from today. On first load the fan draws outward
 * from "Now", which is the page's one orchestrated moment. After that it morphs in answer to the inputs.
 */
export function FanChart({ scenarios, active, goal, colors }:
  { scenarios: ScenarioOut[]; active: number; goal: number | null; colors: string[] }) {
  const reduce = useReducedMotion();
  const clip = `fan-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const focus = scenarios[active] ?? scenarios[0];
  const years = focus.yearly.length - 1;
  const color = colors[active] ?? colors[0];
  const morph = reduce ? { duration: 0 } : { duration: 0.45, ease: EASE };

  const geo = useMemo(() => {
    const top = Math.max(...scenarios.flatMap((s) => s.yearly.map((p) => p.p90)), goal ?? 0) * 1.06;
    const x = linear([0, years], [M.left, W - M.right]);
    const y = linear([0, top], [H - M.bottom, M.top]);
    const pts = (key: keyof YearPoint): Point[] => focus.yearly.map((p) => [x(p.year), y(p[key])]);
    return {
      x, y, ticks: niceTicks(0, top, 4),
      outer: areaPath(pts("p90"), pts("p10")), inner: areaPath(pts("p75"), pts("p25")),
      median: linePath(pts("p50")), paid: linePath(pts("contributed")),
      others: scenarios.map((s, i) => (i === active ? null : linePath(s.yearly.map((p) => [x(p.year), y(p.p50)])))),
    };
  }, [scenarios, focus, years, goal, active]);

  const last = focus.yearly[years];
  const labels = spread([{ key: "p90", y: geo.y(last.p90) }, { key: "p50", y: geo.y(last.p50) }, { key: "p10", y: geo.y(last.p10) }],
    30, M.top + 8, H - M.bottom - 14);
  const step = years <= 6 ? 1 : years <= 12 ? 2 : years <= 25 ? 5 : 10;
  const xTicks = Array.from({ length: years + 1 }, (_, i) => i).filter((i) => i % step === 0 || i === years);
  const plotWidth = W - M.left - M.right;
  const point = hover === null ? null : focus.yearly[hover];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setHover(nearestIndex(focus.yearly.map((p) => geo.x(p.year)), ((e.clientX - box.left) / box.width) * W));
  }

  const summary = `${focus.label}: after ${years} years the middle outcome is ${formatUsd(last.p50, 0)}. One in ten `
    + `outcomes is below ${formatUsd(last.p10, 0)} and one in ten above ${formatUsd(last.p90, 0)}. You pay in `
    + `${formatUsd(last.contributed, 0)}.`;

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full touch-none select-none" role="img" aria-label={summary}>
        <defs>
          <clipPath id={clip}>
            <motion.rect key={years} x={M.left - 2} y={0} height={H} initial={{ width: reduce ? plotWidth + 4 : 0 }}
              animate={{ width: plotWidth + 4 }} transition={{ duration: reduce ? 0 : 1.1, ease: EASE }} />
          </clipPath>
        </defs>
        {geo.ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={geo.y(t)} y2={geo.y(t)} stroke="var(--color-sand-200)" strokeWidth={1} />
            <text x={M.left - 8} y={geo.y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-500 text-[11px]">{compactUsd(t)}</text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={geo.x(t)} y={H - 8} textAnchor="middle" className="num fill-ink-500 text-[11px]">{t === 0 ? "Now" : `${t}y`}</text>
        ))}
        <g key={years} clipPath={`url(#${clip})`}>
          <motion.path initial={false} d={geo.outer} animate={{ d: geo.outer }} transition={morph} fill={color} fillOpacity={0.1} />
          <motion.path initial={false} d={geo.inner} animate={{ d: geo.inner }} transition={morph} fill={color} fillOpacity={0.2} />
          {geo.others.map((d, i) => d && (
            <motion.path key={i} initial={false} d={d} animate={{ d }} transition={morph} fill="none" stroke={colors[i]} strokeWidth={1.25} strokeOpacity={0.8} />
          ))}
          <motion.path initial={false} d={geo.paid} animate={{ d: geo.paid }} transition={morph} fill="none" stroke="var(--color-ink-700)" strokeWidth={1} strokeDasharray="3 4" />
          <motion.path initial={false} d={geo.median} animate={{ d: geo.median }} transition={morph} fill="none" stroke={color} strokeWidth={2.25} strokeLinejoin="round" />
        </g>
        {goal !== null && geo.y(goal) > M.top && (
          <g>
            <line x1={M.left} x2={W - M.right} y1={geo.y(goal)} y2={geo.y(goal)} stroke="var(--color-green-700)" strokeWidth={1} strokeDasharray="6 4" />
            <text x={M.left + 6} y={geo.y(goal) - 6} className="num fill-green-700 text-[11px] font-medium">Goal {compactUsd(goal)}</text>
          </g>
        )}
        <motion.g key={`labels-${years}`} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ delay: reduce ? 0 : 0.9, duration: 0.3 }}>
          {([["p90", "Upper 10%"], ["p50", "Middle"], ["p10", "Lower 10%"]] as const).map(([key, name]) => (
            <g key={key} transform={`translate(${W - M.right + 12}, ${labels[key]})`}>
              <text className="fill-ink-500 text-[10.5px]" dy="-0.25em">{name}</text>
              <text className={`num wide text-[13.5px] font-semibold ${key === "p50" ? "fill-ink-900" : "fill-ink-700"}`} dy="1em">{compactUsd(last[key])}</text>
            </g>
          ))}
        </motion.g>
        {point && <line x1={geo.x(point.year)} x2={geo.x(point.year)} y1={M.top} y2={H - M.bottom} stroke="var(--color-sand-300)" />}
        <rect x={M.left} y={M.top} width={plotWidth} height={H - M.top - M.bottom} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {point && (
        <div className="pointer-events-none absolute top-2 z-10 rounded-control border border-sand-200 bg-white px-3 py-2 text-xs shadow-float"
          style={{ left: `${(geo.x(point.year) / W) * 100}%`, transform: geo.x(point.year) > W * 0.55 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" }}>
          <p className="font-medium">{point.year === 0 ? "Today" : `After ${point.year} year${point.year === 1 ? "" : "s"}`}</p>
          <p className="num mt-1 text-ink-900">Middle {formatUsd(point.p50, 0)}</p>
          <p className="num text-ink-700">Range {formatUsd(point.p10, 0)} to {formatUsd(point.p90, 0)}</p>
          <p className="num text-ink-500">Paid in {formatUsd(point.contributed, 0)}</p>
        </div>
      )}
    </div>
  );
}
