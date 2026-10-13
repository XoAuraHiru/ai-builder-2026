/** A figure as text ("$45,635.00", "7.78%", "6.2 / 10") read into a number and the format to write it back in, so an
 *  engine figure can count up to itself without changing how it reads. */
export type FigureSpec = { prefix: string; value: number; decimals: number; suffix: string; grouped: boolean };

// An optional sign and currency, one number, then a short unit (%, " / 10", " pts"). Anything else is not one figure.
const FIGURE = /^([−-]?\$?)(\d[\d,]*)(?:\.(\d+))?(%|\s*\/\s*\d+|\s*pts?)?$/;

export function parseFigure(text: string): FigureSpec | null {
  const m = FIGURE.exec((text ?? "").trim());
  if (!m) return null;
  const [, prefix, whole, fraction = "", suffix = ""] = m;
  return {
    prefix, suffix, decimals: fraction.length, grouped: whole.includes(","),
    value: Number(`${whole.replace(/,/g, "")}${fraction ? `.${fraction}` : ""}`),
  };
}

export function formatLike(value: number, spec: FigureSpec): string {
  const body = value.toLocaleString("en-US", {
    minimumFractionDigits: spec.decimals, maximumFractionDigits: spec.decimals, useGrouping: spec.grouped,
  });
  return `${spec.prefix}${body}${spec.suffix}`;
}
