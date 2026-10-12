export type PriceSource = "live" | "close";
export type Session = { is_open: boolean; label: string; next_open: string };
export type Quote = {
  symbol: string; price: string; previous_close: string; change: string; change_pct: number; as_of: string; source: PriceSource;
};
export type MarketRow = {
  symbol: string; name: string; kind: "stock" | "etf"; sector: string | null; risk_band: number; price: string;
  change_pct: number; source: PriceSource; watched: boolean;
};
export type Markets = { session: Session; as_of: string | null; rows: MarketRow[] };
export type MarketDetail = {
  symbol: string; name: string; kind: "stock" | "etf"; sector: string | null; industry: string | null; summary: string;
  risk_band: number; volatility_pct: number; market_value: number | null; avg_volume: number | null;
  quote: Quote; session: Session; history: { day: string; close: number }[]; watched: boolean;
};
export type MarketFilter = "all" | "stock" | "etf" | "watchlist";

export function filterRows(rows: MarketRow[], query: string, filter: MarketFilter): MarketRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) =>
    (filter === "all" || (filter === "watchlist" ? r.watched : r.kind === filter)) &&
    (!q || r.symbol.toLowerCase().startsWith(q) || r.name.toLowerCase().includes(q)));
}

const NY_TIME = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
const NY_DAY = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric" });

const NY_MONTH_DAY = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric" });

/** Where a price came from, in words: a delayed live price (with its date when it was not read today), or the last
 *  close when live prices are unavailable. */
export function priceSource(source: PriceSource, asOf: string | null, now: Date = new Date()): string {
  if (!asOf) return "";
  const when = new Date(asOf);
  if (source === "live") {
    const day = NY_DAY.format(when) === NY_DAY.format(now) ? "" : ` on ${NY_MONTH_DAY.format(when)}`;
    return `Delayed price from Yahoo Finance, read at ${NY_TIME.format(when).replace(/\s+/g, " ").toLowerCase()} New York time${day}.`;
  }
  return `Last close, ${NY_DAY.format(when)}. Live prices are unavailable right now.`;
}

/** 15.9 million, 379 billion: big counts the way people say them. */
export function compactCount(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "Not available";
  const units: [number, string][] = [[1e12, "trillion"], [1e9, "billion"], [1e6, "million"], [1e3, "thousand"]];
  for (const [size, word] of units) {
    if (Math.abs(n) >= size) {
      const v = n / size;
      return `${v >= 100 ? Math.round(v) : v.toFixed(1)} ${word}`;
    }
  }
  return String(Math.round(n));
}
