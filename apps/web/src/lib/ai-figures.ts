/** Dollar and percentage figures inside text Gemini wrote, marked by whether an engine produced them. */
export type FigureSpan = { text: string; kind: "text" | "checked" | "unchecked" };

// $1,234.56, −18.5%, 7.78%, $9,000. A plain number (a year, a count) is not a figure the engines are checked on.
const FIGURE = /[−-]?\$[\d,]+(?:\.\d+)?|[−-]?\d[\d,]*(?:\.\d+)?%/g;

function same(a: string, b: string): boolean {
  const norm = (s: string) => s.replace(/[−]/g, "-").replace(/,/g, "").trim();
  return norm(a) === norm(b);
}

export function figureSpans(text: string, unsupported: string[]): FigureSpan[] {
  const out: FigureSpan[] = [];
  let at = 0;
  for (const m of text.matchAll(FIGURE)) {
    const start = m.index ?? 0;
    if (start > at) out.push({ text: text.slice(at, start), kind: "text" });
    out.push({ text: m[0], kind: unsupported.some((u) => same(u, m[0])) ? "unchecked" : "checked" });
    at = start + m[0].length;
  }
  if (at < text.length || out.length === 0) out.push({ text: text.slice(at), kind: "text" });
  return out;
}
