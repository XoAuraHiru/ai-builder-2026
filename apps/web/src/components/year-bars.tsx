import { linear, niceTicks } from "@/lib/scale";

const W = 720;
const H = 190;
const M = { top: 12, right: 8, bottom: 26, left: 40 };

/** Calendar-year returns around a zero line. A partial first or last year is drawn lighter. */
export function YearBars({ years }: { years: { year: number; return_pct: number; months: number }[] }) {
  const values = years.map((y) => y.return_pct);
  const lo = Math.min(...values, 0) * 1.12;
  const hi = Math.max(...values, 0) * 1.12;
  const y = linear([lo, hi], [H - M.bottom, M.top]);
  const band = (W - M.left - M.right) / years.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img"
      aria-label={years.map((r) => `${r.year}: ${r.return_pct}%`).join("; ")}>
      {niceTicks(lo, hi, 3).map((t) => (
        <g key={t}>
          <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--color-ink-2)" : "var(--color-line)"} />
          <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-muted text-[10.5px]">{t}%</text>
        </g>
      ))}
      {years.map((r, i) => {
        const top = y(Math.max(r.return_pct, 0));
        const bottom = y(Math.min(r.return_pct, 0));
        return (
          <g key={r.year}>
            <rect x={M.left + i * band + band * 0.18} width={band * 0.64} y={top} height={Math.max(1, bottom - top)}
              fill={r.return_pct >= 0 ? "var(--color-gain)" : "var(--color-loss)"} fillOpacity={r.months === 12 ? 0.85 : 0.4}>
              <title>{`${r.year}${r.months < 12 ? ` (${r.months} months)` : ""}: ${r.return_pct > 0 ? "+" : ""}${r.return_pct}%`}</title>
            </rect>
            {i % 2 === 0 && (
              <text x={M.left + i * band + band / 2} y={H - 8} textAnchor="middle" className="num fill-muted text-[10.5px]">
                {`'${String(r.year).slice(2)}`}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
