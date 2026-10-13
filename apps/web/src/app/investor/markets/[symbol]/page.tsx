"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, type Portfolio } from "@/lib/api";
import { formatPct, formatSignedUsd, formatUsd } from "@/lib/format";
import { compactCount, priceSource, type MarketDetail } from "@/lib/markets";
import { useMe } from "@/lib/session-context";
import { SessionDot, WatchButton } from "@/components/market-bits";
import { OrderTicket } from "@/components/order-ticket";
import { readShareOrder } from "@/lib/analyzer";
import { PriceChart } from "@/components/price-chart";
import { EmptyState, Figure, Loading, Notice, PageHeader, RiskBand, Section } from "@/components/ui";

export default function SymbolPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const me = useMe();
  const account = me.accounts[0];
  const [detail, setDetail] = useState<MarketDetail | null>(null);
  const [held, setHeld] = useState<{ units: number; value: string }>({ units: 0, value: "0" });
  const [error, setError] = useState("");
  const [fromAnalysis, setFromAnalysis] = useState<{ analysis: string; qty: number } | null>(null);

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
  if (!detail) return <><PageHeader title={symbol.toUpperCase()} back={back} /><Loading label="Loading the price" /></>;

  const q = detail.quote;
  const change = Number(q.change);
  const kindWords = detail.kind === "stock" ? detail.industry : `Exchange-traded fund${detail.industry ? `, ${detail.industry}` : ""}`;
  const facts: [string, ReactNode][] = [
    ["Risk band", <RiskBand key="band" band={detail.risk_band} />],
    ["Price swings", `${formatPct(detail.volatility_pct)} a year, over five years`],
    [detail.kind === "stock" ? "Market value" : "Fund size", detail.market_value ? `$${compactCount(detail.market_value)}` : "Not available"],
    ["Typical daily volume", detail.avg_volume ? `${compactCount(detail.avg_volume)} shares` : "Not available"],
  ];
  return (
    <>
      <PageHeader title={detail.name} back={back} description={[detail.symbol, kindWords].filter(Boolean).join(". ") + "."}
        actions={<WatchButton symbol={detail.symbol} watched={detail.watched} onToggle={toggleWatch} withLabel />} />
      <div className="grid gap-10 2xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 2xl:col-start-1">
            <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
              <Figure size="lg" label="Price" value={formatUsd(q.price)} />
              <p className={`num pb-1 text-[17px] font-medium ${change > 0 ? "text-gain" : change < 0 ? "text-loss" : "text-ink-2"}`}>
                {formatSignedUsd(q.change)} ({formatPct(q.change_pct, 2, true)}) today
              </p>
            </div>
            <p className="mt-2 text-xs text-muted">{priceSource(q.source, q.as_of)}</p>
            <div className="mt-3"><SessionDot session={detail.session} /></div>
        </div>
        <div className="min-w-0 max-w-[460px] 2xl:col-start-2 2xl:row-span-2 2xl:row-start-1 2xl:max-w-none">
          {account
            ? <OrderTicket key={`${detail.symbol}-${fromAnalysis?.analysis ?? ""}`} accountId={account.id} symbol={detail.symbol}
                price={q.price} held={held.units} onPlaced={() => { loadHolding().catch(() => {}); }}
                initialQuantity={fromAnalysis?.qty} analysisId={fromAnalysis?.analysis} />
            : <EmptyState title="No investment account yet">Choose an investor on the front page to trade.</EmptyState>}
          <p className="mt-4 text-xs text-muted">Paper trading at real prices: no real money moves. Nothing here is investment advice.</p>
        </div>
        <div className="min-w-0 space-y-10 2xl:col-start-1">
          <Section title="The last year" description="Daily closing prices, adjusted for dividends and splits.">
            <PriceChart points={detail.history} label={`${detail.name}: daily closes over the last year`} />
          </Section>
          <Section title="About">
            {detail.summary && <p className="max-w-[68ch] text-[15px] leading-relaxed text-ink-2">{detail.summary}</p>}
            <dl className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
              {facts.map(([k, v]) => (
                <div key={k} className="border-t border-line pt-2">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="num mt-0.5 text-sm font-medium">{v}</dd>
                </div>
              ))}
            </dl>
            {held.units > 0 && (
              <p className="mt-5 text-sm text-ink-2">You hold {held.units} {held.units === 1 ? "share" : "shares"}, worth {formatUsd(held.value)}.</p>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}
