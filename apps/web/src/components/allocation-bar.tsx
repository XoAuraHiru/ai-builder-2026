import { formatUsd } from "@/lib/format";

export type Slice = { key: string; label: string; value: number; color: string };

/** Shares of a whole as one bar with hairline gaps, and a legend that carries the exact figures. */
export function AllocationBar({ slices, total, title }: { slices: Slice[]; total?: number; title?: string }) {
  const rows = [...slices].filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
  const sum = total ?? rows.reduce((s, x) => s + x.value, 0);
  const pct = (v: number) => (sum ? (v / sum) * 100 : 0);
  return (
    <figure className="min-w-0">
      {title && <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>}
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-[3px] bg-line" aria-hidden="true">
        {rows.map((s) => <span key={s.key} className="h-full" style={{ flexGrow: s.value, flexBasis: 0, background: s.color }} />)}
      </div>
      <ul className="mt-3 divide-y divide-line text-sm">
        {rows.map((s) => (
          <li key={s.key} className="flex items-center gap-3 py-1.5">
            <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            <span className="num w-14 text-right text-muted">{pct(s.value).toFixed(1)}%</span>
            <span className="num w-28 text-right">{formatUsd(s.value)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
