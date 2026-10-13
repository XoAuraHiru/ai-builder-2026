"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, type Portfolio } from "@/lib/api";
import { formatPct, formatUsd } from "@/lib/format";
import { compactCount, priceSource, type MarketDetail } from "@/lib/markets";
import { useMe } from "@/lib/session-context";
import { SessionChip, TickerTile, WatchButton } from "@/components/market-bits";
import { OrderTicket } from "@/components/order-ticket";
import { readShareOrder } from "@/lib/analyzer";
import { PriceChart } from "@/components/price-chart";
import { CountUp } from "@/components/motion";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { ChangeChip, EmptyState, Notice, PageHeader, Panel, RiskBand, Section } from "@/components/ui";
import { LoadingRegion, SectionTitleSkeleton } from "../../_parts/shapes";

/** A symbol while its price loads: the price card, the order ticket beside it, the year's chart and the facts. */
function SymbolSkeleton() {
  return (
    <LoadingRegion label="Loading the price" className="grid gap-x-4 gap-y-10 xl:grid-cols-[minmax(0,1fr)_380px] xl:grid-rows-[auto_1fr]">
      <div className="flex min-w-0 flex-col gap-3 rounded-panel border border-sand-200 bg-white p-6 xl:col-start-1">
        <span className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-3"><Skeleton className="h-8 w-11 rounded-tile" /><Skeleton className="h-3.5 w-10" /></span>
          <Skeleton className="h-7 w-48 rounded-full" />
        </span>
        <Skeleton className="h-12 w-[min(280px,75%)] rounded-[12px] sm:h-[60px]" />
        <span className="flex flex-wrap items-center gap-2.5"><Skeleton className="h-[26px] w-36 rounded-full" /><Skeleton className="h-3.5 w-56 max-w-full" /></span>
      </div>
      <div className="min-w-0 max-w-[520px] xl:col-start-2 xl:row-span-2 xl:row-start-1 xl:max-w-none">
        <div className="flex flex-col gap-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
          <span className="flex flex-wrap gap-2"><Skeleton className="h-11 w-36 rounded-full" /><Skeleton className="h-11 w-40 rounded-full" /></span>
          <span className="flex flex-col gap-2"><Skeleton className="h-3.5 w-16" /><Skeleton className="h-3 w-28" /><Skeleton className="h-11 rounded-control" /></span>
          <Skeleton className="h-3.5 w-48" />
          <Skeleton className="h-11 rounded-full" />
        </div>
      </div>
      <div className="min-w-0 space-y-10 xl:col-start-1">
        <div>
          <SectionTitleSkeleton />
          <div className="rounded-panel border border-sand-200 bg-white p-4 sm:p-6"><Skeleton className="aspect-[3/1] w-full rounded-[10px]" /></div>
        </div>
        <div>
          <SectionTitleSkeleton description={false} />
          <div className="rounded-panel border border-sand-200 bg-white p-6"><SkeletonText lines={3} className="max-w-[68ch]" /></div>
        </div>
      </div>
    </LoadingRegion>
  );
}

export default function SymbolPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const me = useMe();
  const account = me.accounts[0];
  const [detail, setDetail] = useState<MarketDetail | null>(null);
  const [held, setHeld] = useState<{ units: number; value: string }>({ units: 0, value: "0" });
  const [error, setError] = useState("");
  const [fromAnalysis, setFromAnalysis] = useState<{ analysis: string; qty: number } | null>(null);
  const [profile, setProfile] = useState<number | null>(null);

  useEffect(() => {
    setFromAnalysis(readShareOrder(new URLSearchParams(window.location.search)));
  }, [symbol]);

  const loadHolding = useCallback(async () => {
    if (!account) return;
    const p = await api<Portfolio>(`/accounts/${account.id}/portfolio`);
    const h = p.holdings.find((x) => x.instrument === symbol.toUpperCase());
    setHeld(h ? { units: Number(h.units), value: h.value } : { units: 0, value: "0" });
  }, [account, symbol]);

  useEffect(() => {
    api<{ current_band: number | null }>("/me/risk-profile").then((p) => setProfile(p.current_band)).catch(() => setProfile(null));
  }, []);

  useEffect(() => {
    api<MarketDetail>(`/markets/${symbol}`).then(setDetail)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load this price. Try again."));
    loadHolding().catch(() => setHeld({ units: 0, value: "0" }));
  }, [symbol, loadHolding]);

  async function toggleWatch() {
    if (!detail) return;
    const watched = detail.watched;
    setDetail({ ...detail, watched: !watched });
    try {
      await api(`/me/watchlist/${detail.symbol}`, { method: watched ? "DELETE" : "PUT" });
    } catch {
      setDetail((d) => d && { ...d, watched });
    }
  }

  const back = { href: "/investor/markets", label: "Markets" };
  if (error) return <><PageHeader title="Markets" back={back} /><Notice tone="error" title="This price is unavailable">{error}</Notice></>;
  if (!detail) return <><PageHeader title={symbol.toUpperCase()} back={back} description={<Skeleton className="mt-1 h-3.5 w-64 max-w-full" />} /><SymbolSkeleton /></>;

  const q = detail.quote;
  const change = Number(q.change);
  const kindWords = detail.kind === "stock" ? detail.industry : `Exchange-traded fund${detail.industry ? `, ${detail.industry}` : ""}`;
  const facts: [string, ReactNode][] = [
    ["Risk band, against your profile", <RiskBand key="band" band={detail.risk_band} profile={profile} />],
    ["Price swings", `${formatPct(detail.volatility_pct)} a year, over five years`],
    [detail.kind === "stock" ? "Market value" : "Fund size", detail.market_value ? `$${compactCount(detail.market_value)}` : "Not available"],
    ["Typical daily volume", detail.avg_volume ? `${compactCount(detail.avg_volume)} shares` : "Not available"],
  ];
  return (
    <>
      <PageHeader title={detail.name} back={back} description={[detail.symbol, kindWords].filter(Boolean).join(". ") + "."}
        actions={<WatchButton symbol={detail.symbol} watched={detail.watched} onToggle={toggleWatch} withLabel />} />
      <div className="grid gap-x-4 gap-y-10 xl:grid-cols-[minmax(0,1fr)_380px] xl:grid-rows-[auto_1fr]">
        <Panel className="flex min-w-0 flex-col gap-3 p-6 xl:col-start-1">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="flex items-center gap-3">
              <TickerTile symbol={detail.symbol} tone={detail.kind === "etf" ? "etf" : "stock"} />
              <span className="text-sm font-medium text-ink-700">Price</span>
            </span>
            <SessionChip session={detail.session} />
          </div>
          <p className="num text-[44px] font-medium leading-[48px] tracking-[-0.03em] sm:text-[60px] sm:leading-[60px] sm:tracking-[-0.035em]"><CountUp text={formatUsd(q.price)} /></p>
          <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <ChangeChip size="md" value={change}>
              <span aria-hidden="true">{change > 0 ? "↑" : change < 0 ? "↓" : ""}</span>
              <span className="sr-only">{change > 0 ? "Up" : change < 0 ? "Down" : "Unchanged"} </span>
              {formatUsd(Math.abs(change))} · {formatPct(Math.abs(q.change_pct), 2)}
            </ChangeChip>
            <span className="text-sm text-ink-700">today</span>
            <span className="text-[13px] text-ink-500">· {priceSource(q.source, q.as_of)}</span>
          </p>
        </Panel>
        <div className="min-w-0 max-w-[520px] xl:col-start-2 xl:row-span-2 xl:row-start-1 xl:max-w-none">
          {account
            ? <OrderTicket key={`${detail.symbol}-${fromAnalysis?.analysis ?? ""}`} accountId={account.id} symbol={detail.symbol}
                price={q.price} held={held.units} onPlaced={() => { loadHolding().catch(() => {}); }}
                initialQuantity={fromAnalysis?.qty} analysisId={fromAnalysis?.analysis} />
            : <EmptyState title="No investment account yet">Choose an investor on the front page to trade.</EmptyState>}
          <p className="mt-4 text-xs text-ink-500">Paper trading at real prices: no real money moves. Nothing here is investment advice.</p>
        </div>
        <div className="min-w-0 space-y-10 xl:col-start-1">
          <Section title="The last year" description="Daily closing prices, adjusted for dividends and splits.">
            <Panel className="p-4 sm:p-6">
              <PriceChart points={detail.history} label={`${detail.name}: daily closes over the last year`} />
            </Panel>
          </Section>
          <Section title="About">
            <Panel className="p-6">
              {detail.summary && <p className="max-w-[68ch] text-[15px] leading-relaxed text-ink-700">{detail.summary}</p>}
              <dl className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                {facts.map(([k, v]) => (
                  <div key={k} className="border-t border-sand-100 pt-3">
                    <dt className="text-xs text-ink-500">{k}</dt>
                    <dd className="num mt-1 text-sm font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
              {held.units > 0 && (
                <p className="mt-5 text-sm text-ink-700">You hold {held.units} {held.units === 1 ? "share" : "shares"}, worth {formatUsd(held.value)}.</p>
              )}
            </Panel>
          </Section>
        </div>
      </div>
    </>
  );
}
