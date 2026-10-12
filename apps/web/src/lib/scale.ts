export type Point = [number, number];

export function linear(domain: [number, number], range: [number, number]): (v: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  return (v) => r0 + (v - d0) * k;
}

function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}

/** Round tick values covering [min, max], about `count` intervals. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!(max > min)) return [min];
  const step = niceStep(max - min, count);
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

const fmt = (v: number) => String(Math.round(v * 100) / 100);

export function linePath(points: Point[]): string {
  return points.map(([x, y], i) => `${i ? "L" : "M"}${fmt(x)},${fmt(y)}`).join("");
}

/** A closed band: along `upper`, then back along `lower`. */
export function areaPath(upper: Point[], lower: Point[]): string {
  if (!upper.length) return "";
  const back = [...lower].reverse().map(([x, y]) => `L${fmt(x)},${fmt(y)}`).join("");
  return `${linePath(upper)}${back}Z`;
}

export function nearestIndex(xs: number[], x: number): number {
  let best = 0;
  for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - x) < Math.abs(xs[best] - x)) best = i;
  return best;
}
