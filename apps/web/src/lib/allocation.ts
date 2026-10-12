export { formatUsd } from "./format";

export type AllocationPoint = { name: string; value: number; pct: number };

export function toAllocationSeries(byKey: Record<string, string>): AllocationPoint[] {
  const entries = Object.entries(byKey).map(([name, v]) => ({ name, value: Number(v) }));
  const total = entries.reduce((s, e) => s + e.value, 0);
  return entries
    .sort((a, b) => b.value - a.value)
    .map((e) => ({ ...e, pct: total === 0 ? 0 : Math.round((e.value / total) * 1000) / 10 }));
}
