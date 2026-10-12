"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth, formatPct } from "@/lib/format";
import type { Fund } from "@/lib/invest";
import { Loading, Notice, PageHeader, RiskBand } from "@/components/ui";

type Stats = {
  code: string; name: string; risk_band: number; annual_return_pct: number; annual_volatility_pct: number;
  max_drawdown_pct: number; worst_year: { year: number; return_pct: number }; total_fee_pct: number; window_start: string;
};

export default function FundsPage() {
  const [funds, setFunds] = useState<Record<string, Fund>>({});
  const [stats, setStats] = useState<Stats[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<Fund[]>("/funds"), api<Stats[]>("/funds/stats")])
      .then(([f, s]) => { setFunds(Object.fromEntries(f.map((x) => [x.code, x]))); setStats(s); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load its funds."));
  }, []);

  return (
    <>
      <PageHeader title="Funds" description="Seven house funds, each a fixed mix of low-cost US-listed ETFs, from a Treasury-bill reserve to a technology fund." />
      {error && <Notice tone="error">{error}</Notice>}
      {!stats ? !error && <Loading label="Loading the funds" /> : (
        <ul className="divide-y divide-line border-y border-line">
          {stats.map((s) => (
            <li key={s.code}>
              <Link href={`/investor/funds/${s.code}`}
                className="flex flex-col gap-3 px-2 py-4 hover:bg-surface 2xl:grid 2xl:grid-cols-[minmax(0,1fr)_11.5rem_7.5rem_8.5rem_6.5rem] 2xl:items-center 2xl:gap-x-8">
                <span className="flex flex-col gap-2 2xl:contents">
                  <span className="min-w-0">
                    <span className="font-semibold">{s.name}</span>
                    <span className="block truncate text-sm text-ink-2">{funds[s.code]?.objective}</span>
                  </span>
                  <RiskBand band={s.risk_band} />
                </span>
                <span className="grid grid-cols-3 gap-4 2xl:contents">
                  <span className="num text-sm"><span className="block text-xs text-muted">Average a year</span>{formatPct(s.annual_return_pct)}</span>
                  <span className="num text-sm"><span className="block text-xs text-muted">Worst year</span>
                    <span className={s.worst_year.return_pct < 0 ? "text-loss" : ""}>{formatPct(s.worst_year.return_pct, 1, true)}</span> in {s.worst_year.year}</span>
                  <span className="num text-sm"><span className="block text-xs text-muted">Yearly cost</span>{formatPct(s.total_fee_pct, 2)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {stats && stats.length > 0 && (
        <p className="mt-4 text-xs text-muted">
          Averages and worst years from {formatMonth(stats[0].window_start)}, a backtest of each fund&apos;s mix before it launched in
          October 2024, before the Atrium fee. Past performance does not predict future returns.
        </p>
      )}
    </>
  );
}
