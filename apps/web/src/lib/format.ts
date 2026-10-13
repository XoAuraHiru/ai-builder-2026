const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function formatUsd(value: string | number, digits: 0 | 2 = 2): string {
  return (digits === 0 ? usd0 : usd2).format(Number(value));
}

function trim(x: number): string {
  return x.toFixed(1).replace(/\.0$/, "");
}

/** Short money for chart labels: $950, $9.5k, $250k, $1.2M. */
export function compactUsd(value: number): string {
  const n = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (n >= 1e9) return `${sign}$${trim(n / 1e9)}B`;
  if (n >= 999_500) return `${sign}$${trim(n / 1e6)}M`;  // $999,710 reads $1M, not $1000k
  if (n >= 1e4) return `${sign}$${Math.round(n / 1e3)}k`;
  if (n >= 1e3) return `${sign}$${trim(n / 1e3)}k`;
  return `${sign}$${Math.round(n)}`;
}

/** Percentages with a true minus sign for negatives, so they align with money figures. */
export function formatPct(value: string | number, digits = 1, signed = false): string {
  const n = Number(value);
  const text = `${Math.abs(n).toFixed(digits)}%`;
  if (n < 0 && Number(Math.abs(n).toFixed(digits)) !== 0) return `−${text}`;
  return signed && n > 0 ? `+${text}` : text;
}

/** Gains and losses: +$10.00 or −$1,234.50 (a true minus sign, so columns of numbers align). */
export function formatSignedUsd(value: string | number): string {
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${usd2.format(Math.abs(n))}`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

export function formatMonth(yearMonth: string): string {
  const d = new Date(`${yearMonth}-01T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
