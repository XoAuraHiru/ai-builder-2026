"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { changeText, filterRows, priceSource, profileLegend, type MarketFilter, type MarketRow,
  type Markets } from "@/lib/markets";
import { SessionChip, TickerTile, WatchButton } from "@/components/market-bits";
import { EmptyState, inputClass, Loading, Notice, PageHeader, Panel, RiskBand, Segmented } from "@/components/ui";

const FILTERS: { value: MarketFilter; label: string }[] = [
  { value: "all", label: "All" }, { value: "stock", label: "Stocks" }, { value: "etf", label: "ETFs" }, { value: "watchlist", label: "Watchlist" },
];
const DESCRIPTION = "Thirty large US companies and seventeen ETFs, traded with paper money at real prices. Every order passes the Pre-trade Guardian before it goes anywhere.";
// Phones: star, name (with the meter under it), price and change stacked. md adds the risk band, today and the
// Trade action; xl adds the sector, as in the artboard.
const COLS = "grid grid-cols-[28px_minmax(0,1fr)_auto] gap-x-3 md:grid-cols-[32px_minmax(0,2fr)_minmax(0,1.5fr)_96px_88px_80px] md:gap-x-4 xl:grid-cols-[32px_minmax(0,2fr)_minmax(0,1.3fr)_minmax(0,1.5fr)_110px_100px_96px]";

/** The day's change with its arrow: green up, coral down. */
function Change({ pct, className = "" }: { pct: number; className?: string }) {
  const text = changeText(pct);
  const tone = text.startsWith("↑") ? "text-green-700" : text.startsWith("↓") ? "text-coral-700" : "text-ink-700";
  const said = text.startsWith("↑") ? `Up ${text.slice(2)}` : text.startsWith("↓") ? `Down ${text.slice(2)}` : "Unchanged";
  return (
    <span className={`num font-medium ${tone} ${className}`}>
      <span className="sr-only">{said}</span><span aria-hidden="true">{text}</span>
    </span>
  );
}

/** M4: a row that highlights in fill on hover or focus and shows a green Trade button; the whole row opens the symbol. */
function Row({ r, profile, onToggle }: { r: MarketRow; profile: number | null; onToggle: () => void }) {
  const href = `/investor/markets/${r.symbol}`;
  const kind = r.kind === "etf" ? "ETF" : "Stock";
  return (
    <div role="row" className={`${COLS} group relative -mx-3 items-center rounded-control px-3 py-3 hover:bg-fill focus-within:bg-fill before:absolute before:inset-x-3 before:bottom-0 before:h-px before:bg-sand-100 last:before:hidden hover:before:hidden focus-within:before:hidden`}>
      <span role="cell" className="relative z-10 -ml-1.5">
        <WatchButton symbol={r.symbol} watched={r.watched} onToggle={onToggle} />
      </span>
      <span role="cell" className="flex min-w-0 items-center gap-3">
        <TickerTile symbol={r.symbol} tone={r.kind === "etf" ? "etf" : "stock"} />
        <span className="flex min-w-0 flex-col">
          <Link href={href} className="truncate text-sm font-medium after:absolute after:inset-0 after:rounded-control focus-visible:shadow-none">
            {r.name}
          </Link>
          <span className="flex items-center gap-2 text-xs text-ink-500">
            <span className="truncate">{kind}{r.watched ? " · on your watchlist" : ""}</span>
            <span className="md:hidden"><RiskBand band={r.risk_band} profile={profile} showLabel={false} /></span>
          </span>
        </span>
      </span>
      <span role="cell" className="hidden min-w-0 truncate text-sm text-ink-700 xl:block">{r.sector ?? <span className="text-ink-500">ETF</span>}</span>
      <span role="cell" className="hidden md:flex"><RiskBand band={r.risk_band} profile={profile} /></span>
      <span role="cell" className="num text-right text-sm">
        {formatUsd(r.price)}
        <Change pct={r.change_pct} className="block text-xs md:hidden" />
      </span>
      <span role="cell" className="hidden text-right text-sm md:block"><Change pct={r.change_pct} /></span>
      <span role="cell" className="relative z-10 hidden justify-end md:flex">
        <Link href={href} tabIndex={-1} aria-hidden="true"
          className="inline-flex h-[34px] items-center whitespace-nowrap rounded-full bg-green-500 px-4 text-[13px] font-semibold text-white opacity-0 transition-opacity hover:bg-green-600 group-hover:opacity-100 group-focus-within:opacity-100">
          Trade
        </Link>
      </span>
    </div>
  );
}

export default function MarketsPage() {
  const [data, setData] = useState<Markets | null>(null);
  const [profile, setProfile] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MarketFilter>("all");

  useEffect(() => {
    api<Markets>("/markets").then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load market prices. Try again."));
    api<{ current_band: number | null }>("/me/risk-profile").then((p) => setProfile(p.current_band)).catch(() => setProfile(null));
  }, []);

  const rows = useMemo(() => (data ? filterRows(data.rows, query, filter) : []), [data, query, filter]);
  const legend = profileLegend(profile);

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

  if (error) return <><PageHeader title="Markets" description={DESCRIPTION} /><Notice tone="error" title="Prices are unavailable">{error}</Notice></>;
  if (!data) return <><PageHeader title="Markets" description={DESCRIPTION} /><Loading label="Loading prices" /></>;

  return (
    <>
      <PageHeader title="Markets" description={DESCRIPTION} badge={<SessionChip session={data.session} />} />
      <div className="space-y-4">
        <Panel className="flex flex-col gap-2 px-4 pb-2 pt-4 sm:px-6 sm:pt-5">
          {/* M3: search, the filter and the risk legend share one toolbar inside the table card. */}
          <div className="flex flex-wrap items-center gap-3 pb-2">
            <label className="relative w-full sm:w-80">
              <span className="sr-only">Search by symbol or name</span>
              <svg aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6F6C62" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
              </svg>
              <input className={`${inputClass} pl-10`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Symbol or company" />
            </label>
            <Segmented label="Show" value={filter} onChange={setFilter} options={FILTERS} />
            <span className="hidden flex-1 lg:block" />
            {legend ? (
              <span className="flex flex-wrap items-center gap-x-3.5 gap-y-1 text-xs text-ink-700">
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2 w-3.5 rounded-[3px] bg-green-500" />{legend.within}</span>
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2 w-3.5 rounded-[3px] bg-amber-400" />{legend.above}</span>
              </span>
            ) : (
              <Link href="/investor/profile" className="text-xs font-semibold text-green-600 hover:underline">Set your risk profile to compare each band</Link>
            )}
          </div>
          {rows.length === 0 ? (
            <div className="pb-4">
              {filter === "watchlist" && !query
                ? <EmptyState title="Your watchlist is empty">Star a share or an ETF to keep it here.</EmptyState>
                : <EmptyState title="Nothing matches">Try a symbol such as AAPL, or part of a company name.</EmptyState>}
            </div>
          ) : (
            <div role="table" aria-label="Shares and ETFs">
              <div role="row" className={`${COLS} border-b border-sand-100 py-2.5 text-xs font-medium text-ink-500`}>
                <span role="columnheader"><span className="sr-only">Watchlist</span></span>
                <span role="columnheader">Name</span>
                <span role="columnheader" className="hidden xl:block">Sector</span>
                <span role="columnheader" className="hidden md:block">Risk band</span>
                <span role="columnheader" className="text-right">Price</span>
                <span role="columnheader" className="hidden text-right md:block">Today</span>
                <span role="columnheader" className="hidden md:block"><span className="sr-only">Trade</span></span>
              </div>
              {rows.map((r) => <Row key={r.symbol} r={r} profile={profile} onToggle={() => toggle(r.symbol, r.watched)} />)}
            </div>
          )}
        </Panel>
        <p className="px-1 text-xs text-ink-500">{priceSource(data.rows[0]?.source ?? "close", data.as_of)} Risk bands come from each price&apos;s swings over the last five years, measured against your risk profile.</p>
      </div>
    </>
  );
}
