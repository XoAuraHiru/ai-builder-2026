"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type Me, type Portfolio } from "@/lib/api";
import { formatUsd, toAllocationSeries } from "@/lib/allocation";
import { isSignedIn } from "@/lib/session";
import { AllocationChart } from "@/components/allocation-chart";
import { WhyPanel } from "@/components/why-panel";

export default function InvestorPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      if (!(await isSignedIn())) {
        router.push("/login");
        return;
      }
      try {
        const m = await api<Me>("/me");
        setMe(m);
        if (m.accounts.length) setPortfolio(await api<Portfolio>(`/accounts/${m.accounts[0].id}/portfolio`));
      } catch (e) {
        setError(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
      }
    })();
  }, [router]);

  if (error) return <p className="text-red-600">Could not load your portfolio. {error}</p>;
  if (!me) return <p>Loading…</p>;
  if (!me.accounts.length) return <p>{me.email} has no investment account. Pick an investor persona to see a portfolio.</p>;
  if (!portfolio) return <p>Valuing your portfolio…</p>;

  const pnlUp = Number(portfolio.pnl) >= 0;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Your portfolio</h1>
        <span className="text-sm text-slate-500">
          as of {portfolio.as_of} · {me.accounts[0].number}
        </span>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Total value" value={formatUsd(portfolio.total_value)} />
        <Stat label="Invested" value={formatUsd(portfolio.total_cost)} />
        <Stat
          label="Gain / loss"
          value={`${formatUsd(portfolio.pnl)} (${portfolio.pnl_pct}%)`}
          tone={pnlUp ? "up" : "down"}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <AllocationChart title="By fund" data={toAllocationSeries(portfolio.by_fund)} />
        <AllocationChart title="By asset class" data={toAllocationSeries(portfolio.by_asset_class)} />
        <AllocationChart title="By region" data={toAllocationSeries(portfolio.by_region)} />
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="px-3 py-2">Fund</th>
              <th className="px-3 py-2 text-right">Units</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Value</th>
              <th className="px-3 py-2 text-right">Gain / loss</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.holdings.map((h) => (
              <tr key={h.instrument} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  {h.name} <span className="text-slate-500">{h.instrument}</span>
                </td>
                <td className="px-3 py-2 text-right">{Number(h.units).toFixed(4)}</td>
                <td className="px-3 py-2 text-right">
                  {formatUsd(h.price)} <span className="text-xs text-slate-500">{h.price_as_of}</span>
                </td>
                <td className="px-3 py-2 text-right">{formatUsd(h.value)}</td>
                <td className={`px-3 py-2 text-right ${Number(h.pnl) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  {formatUsd(h.pnl)} ({h.pnl_pct}%)
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <WhyPanel
        title="how this valuation was computed"
        evidence={[
          { label: "Prices", detail: "Each fund is valued at its last published NAV on or before the as-of date." },
          { label: "Cost basis", detail: "Sum of remaining FIFO lots at their purchase price; realised gains are excluded." },
          {
            label: "Look-through",
            detail: "Asset class and region slices multiply each fund's value by its constituent weights.",
          },
        ]}
        model="deterministic valuation engine (no model)"
      />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  const color = tone === "up" ? "text-emerald-700" : tone === "down" ? "text-red-600" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}
