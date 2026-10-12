"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatPct, formatUsd } from "@/lib/format";
import { filterRows, priceSource, type MarketFilter, type Markets } from "@/lib/markets";
import { SessionDot, WatchButton } from "@/components/market-bits";
import { EmptyState, inputClass, Loading, Notice, PageHeader, RiskBand, Segmented, tableStyles } from "@/components/ui";

const FILTERS: { value: MarketFilter; label: string }[] = [
  { value: "all", label: "All" }, { value: "stock", label: "Stocks" }, { value: "etf", label: "ETFs" }, { value: "watchlist", label: "Watchlist" },
];

export default function MarketsPage() {
  const [data, setData] = useState<Markets | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MarketFilter>("all");

  useEffect(() => {
    api<Markets>("/markets").then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load market prices. Try again."));
  }, []);

  const rows = useMemo(() => (data ? filterRows(data.rows, query, filter) : []), [data, query, filter]);

  function mark(symbol: string, watched: boolean) {
    setData((d) => d && { ...d, rows: d.rows.map((r) => (r.symbol === symbol ? { ...r, watched } : r)) });
  }

  async function toggle(symbol: string, watched: boolean) {
    mark(symbol, !watched);
    try {
      await api(`/me/watchlist/${symbol}`, { method: watched ? "DELETE" : "PUT" });
    } catch {
      mark(symbol, watched);
    }
  }

  const header = (
    <PageHeader title="Markets"
      description="Thirty large US companies and seventeen ETFs, traded with paper money at real prices. Every order passes the Pre-trade Guardian before it goes anywhere." />
  );
  if (error) return <>{header}<Notice tone="error" title="Prices are unavailable">{error}</Notice></>;
  if (!data) return <>{header}<Loading label="Loading prices" /></>;

  return (
    <>
      {header}
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <SessionDot session={data.session} />
          <div className="flex flex-wrap items-center gap-3">
            <label className="w-56">
              <span className="sr-only">Search by symbol or name</span>
              <input className={inputClass} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Symbol or company" />
            </label>
            <Segmented label="Show" value={filter} onChange={setFilter} options={FILTERS} />
          </div>
        </div>
        {rows.length === 0 ? (
          filter === "watchlist" && !query
            ? <EmptyState title="Your watchlist is empty">Star a share or an ETF to keep it here.</EmptyState>
            : <EmptyState title="Nothing matches">Try a symbol such as AAPL, or part of a company name.</EmptyState>
        ) : (
          <div className={tableStyles.wrap}>
            <table className={tableStyles.table}>
              <thead className={tableStyles.head}>
                <tr>
                  <th className={`${tableStyles.th} w-10`}><span className="sr-only">Watchlist</span></th>
                  <th className={tableStyles.th}>Name</th>
                  <th className={`${tableStyles.th} hidden md:table-cell`}>Sector</th>
                  <th className={`${tableStyles.th} hidden sm:table-cell`}>Risk band</th>
                  <th className={`${tableStyles.th} text-right`}>Price</th>
                  <th className={`${tableStyles.th} text-right`}>Today</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.symbol} className={`${tableStyles.row} hover:bg-ground/60`}>
                    <td className={tableStyles.td}><WatchButton symbol={r.symbol} watched={r.watched} onToggle={() => toggle(r.symbol, r.watched)} /></td>
                    <td className={tableStyles.td}>
                      <Link href={`/investor/markets/${r.symbol}`} className="group block">
                        <span className="font-medium group-hover:underline">{r.symbol}</span>
                        <span className="block text-xs text-muted">{r.name}</span>
                      </Link>
                    </td>
                    <td className={`${tableStyles.td} hidden text-ink-2 md:table-cell`}>{r.sector ?? (r.kind === "etf" ? "ETF" : "")}</td>
                    <td className={`${tableStyles.td} hidden sm:table-cell`}><RiskBand band={r.risk_band} showLabel={false} /></td>
                    <td className={`${tableStyles.td} num text-right`}>{formatUsd(r.price)}</td>
                    <td className={`${tableStyles.td} num text-right ${r.change_pct > 0 ? "text-gain" : r.change_pct < 0 ? "text-loss" : "text-ink-2"}`}>
                      {formatPct(r.change_pct, 2, true)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-muted">{priceSource(data.rows[0]?.source ?? "close", data.as_of)} Risk bands come from each price&apos;s swings over the last five years.</p>
      </div>
    </>
  );
}
