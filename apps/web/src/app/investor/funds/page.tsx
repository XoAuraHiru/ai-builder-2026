"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth, formatPct } from "@/lib/format";
import type { Fund } from "@/lib/invest";
import { TickerTile } from "@/components/market-bits";
import { Stagger, StaggerItem } from "@/components/motion";
import { Skeleton } from "@/components/skeleton";
import { Notice, PageHeader, Panel, RiskBand } from "@/components/ui";
import { LoadingRegion } from "../_parts/shapes";

/** The funds while they load: seven rows of tile, name and objective, risk meter and three figures. */
function FundsSkeleton() {
  return (
    <LoadingRegion label="Loading the funds">
      <div className="rounded-panel border border-sand-200 bg-white px-3 py-2 sm:px-4">
        {Array.from({ length: 7 }, (_, i) => (
          <div key={i} className="flex flex-col gap-3 border-b border-sand-100 px-3 py-4 last:border-b-0 xl:grid xl:grid-cols-[minmax(0,1fr)_11.5rem_7.5rem_8.5rem_6.5rem] xl:items-center xl:gap-x-8">
            <span className="flex min-w-0 items-center gap-3">
              <Skeleton className="h-8 w-11 shrink-0 rounded-tile" />
              <span className="flex min-w-0 flex-1 flex-col gap-2"><Skeleton className="h-4 w-44" /><Skeleton className="h-3.5 w-[min(420px,90%)]" /></span>
            </span>
            <span className="flex items-center gap-2.5">
              <span className="flex gap-[3px]">{[0, 1, 2, 3, 4].map((j) => <Skeleton key={j} className="h-2 w-3.5 rounded-[3px]" />)}</span>
              <Skeleton className="h-3 w-20" />
            </span>
            <span className="grid grid-cols-3 gap-4 xl:contents">
              {[0, 1, 2].map((j) => <span key={j} className="flex flex-col gap-1.5"><Skeleton className="h-3 w-16" /><Skeleton className="h-3.5 w-14" /></span>)}
            </span>
          </div>
        ))}
      </div>
    </LoadingRegion>
  );
}

type Stats = {
  code: string; name: string; risk_band: number; annual_return_pct: number; annual_volatility_pct: number;
  max_drawdown_pct: number; worst_year: { year: number; return_pct: number }; total_fee_pct: number; window_start: string;
};

export default function FundsPage() {
  const [funds, setFunds] = useState<Record<string, Fund>>({});
  const [stats, setStats] = useState<Stats[] | null>(null);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api<Fund[]>("/funds"), api<Stats[]>("/funds/stats")])
      .then(([f, s]) => { setFunds(Object.fromEntries(f.map((x) => [x.code, x]))); setStats(s); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load its funds."));
    // Each fund's band is measured against the investor's own profile: green at or below it, amber above.
    api<{ current_band: number | null }>("/me/risk-profile").then((p) => setProfile(p.current_band)).catch(() => setProfile(null));
  }, []);

  return (
    <>
      <PageHeader title="Funds" description="Seven house funds, each a fixed mix of low-cost US-listed ETFs, from a Treasury-bill reserve to a technology fund." />
      {error && <Notice tone="error">{error}</Notice>}
      {!stats ? !error && <FundsSkeleton /> : (
        <Panel className="px-3 py-2 sm:px-4">
        <Stagger as="ul">
          {stats.map((s) => (
            <StaggerItem as="li" key={s.code} className="relative before:absolute before:inset-x-3 before:bottom-0 before:h-px before:bg-sand-100 last:before:hidden">
              <Link href={`/investor/funds/${s.code}`}
                className="group flex flex-col gap-3 rounded-control px-3 py-4 hover:bg-fill xl:grid xl:grid-cols-[minmax(0,1fr)_11.5rem_7.5rem_8.5rem_6.5rem] xl:items-center xl:gap-x-8">
                <span className="flex flex-col gap-2 xl:contents">
                  <span className="flex min-w-0 items-center gap-3">
                    <TickerTile symbol={s.code.replace(/^ATR-/, "")} tone="fund" />
                    <span className="min-w-0">
                      <span className="block font-semibold">{s.name}</span>
                      <span className="block truncate text-sm text-ink-700">{funds[s.code]?.objective}</span>
                    </span>
                  </span>
                  <RiskBand band={s.risk_band} profile={profile} />
                </span>
                <span className="grid grid-cols-3 gap-4 xl:contents">
                  <span className="num text-sm"><span className="block text-xs text-ink-500">Average a year</span>{formatPct(s.annual_return_pct)}</span>
                  <span className="num text-sm"><span className="block text-xs text-ink-500">Worst year</span>
                    <span className={s.worst_year.return_pct < 0 ? "text-coral-700" : ""}>{formatPct(s.worst_year.return_pct, 1, true)}</span> in {s.worst_year.year}</span>
                  <span className="num text-sm"><span className="block text-xs text-ink-500">Yearly cost</span>{formatPct(s.total_fee_pct, 2)}</span>
                </span>
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
        </Panel>
      )}
      {stats && stats.length > 0 && (
        <p className="mt-4 px-1 text-xs text-ink-500">
          Averages and worst years from {formatMonth(stats[0].window_start)}, a backtest of each fund&apos;s mix before it launched in
          October 2024, before the Atrium fee. Past performance does not predict future returns.
        </p>
      )}
    </>
  );
}
