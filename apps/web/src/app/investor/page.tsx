"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type Portfolio } from "@/lib/api";
import { formatDate, formatPct, formatSignedUsd, formatUsd } from "@/lib/format";
import { BAND_COLOR, CATEGORY, verdictText, type Fund, type RiskReport, type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar, type Slice } from "@/components/allocation-bar";
import { WhyPanel } from "@/components/why-panel";
import { ButtonLink, EmptyState, Figure, Loading, Notice, PageHeader, Section, tableStyles } from "@/components/ui";

const ASSET: Record<string, string> = { equity: "Stocks", bond: "Bonds", cash: "Cash and T-bills" };
const REGION: Record<string, string> = { US: "United States", DM_ex_US: "Developed outside the US", EM: "Emerging markets", Global: "Global" };

type Insight = { href: string; title: string; text: string; caution: boolean };

function slices(map: Record<string, string>, names: Record<string, string>): Slice[] {
  return Object.entries(map).map(([k, v], i) => ({ key: k, label: names[k] ?? k, value: Number(v), color: CATEGORY[i % CATEGORY.length] }));
}

export default function InvestorOverview() {
  const me = useMe();
  const account = me.accounts[0];
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [funds, setFunds] = useState<Record<string, Fund>>({});
  const [insights, setInsights] = useState<Insight[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!account) return;
    (async () => {
      try {
        const [p, f] = await Promise.all([api<Portfolio>(`/accounts/${account.id}/portfolio`), api<Fund[]>("/funds")]);
        setPortfolio(p);
        setFunds(Object.fromEntries(f.map((x) => [x.code, x])));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Atrium could not value your portfolio. Try again.");
        return;
      }
      const [risk, xray, profile] = await Promise.allSettled([
        api<RiskReport>(`/accounts/${account.id}/risk`), api<XRay>(`/accounts/${account.id}/xray`),
        api<{ profile: unknown }>("/me/risk-profile")]);
      const found: Insight[] = [];
      if (risk.status === "fulfilled") {
        const r = risk.value;
        found.push({ href: "/investor/risk", title: "Risk", text: verdictText(r.verdict, r.portfolio_band, r.profile_band), caution: r.verdict === "above" });
      }
      if (xray.status === "fulfilled") {
        const w = xray.value.warnings;
        found.push({ href: "/investor/xray", title: "Portfolio X-ray", caution: w.some((x) => x.severity === "caution"),
          text: w.length ? `${w.length} thing${w.length > 1 ? "s" : ""} to look at, starting with: ${w[0].title.toLowerCase()}.`
            : "No concentration or overlap warnings." });
      }
      if (profile.status === "fulfilled" && !profile.value.profile)
        found.push({ href: "/investor/profile", title: "Risk profile", caution: false,
          text: "Your band was set when the account opened. Five questions show the reasoning behind it." });
      setInsights(found);
    })();
  }, [account]);

  if (!account) return <EmptyState title="No investment account yet">Choose an investor persona to see a portfolio.</EmptyState>;
  if (error) return <Notice tone="error" title="Could not load your portfolio">{error}</Notice>;
  if (!portfolio) return <Loading label="Valuing your portfolio" />;

  const total = Number(portfolio.total_value);
  const fundSlices = Object.entries(portfolio.by_fund).map(([code, v]) => ({
    key: code, label: funds[code]?.name ?? code, value: Number(v), color: BAND_COLOR[funds[code]?.risk_band ?? 3] }));
  const up = Number(portfolio.pnl) >= 0;
  const pricedOn = portfolio.holdings.map((h) => h.price_as_of).sort().at(-1) ?? portfolio.as_of;

  return (
    <>
      <PageHeader title="Your portfolio"
        description={`Account ${account.number}. Valued at the latest published fund prices, from ${formatDate(pricedOn)}.`}
        actions={<><ButtonLink href="/investor/orders">Invest or withdraw</ButtonLink><ButtonLink href="/investor/what-if" variant="secondary">Run a what-if</ButtonLink></>} />
      <div className="space-y-12">
        <div className="grid gap-x-10 gap-y-6 sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <Figure size="lg" label="Total value" value={formatUsd(portfolio.total_value)} />
          <Figure label="Paid in" value={formatUsd(portfolio.total_cost)} detail="Cost of the units you hold" />
          <Figure label="Gain or loss" value={formatSignedUsd(portfolio.pnl)} tone={up ? "gain" : "loss"}
            detail={`${formatPct(portfolio.pnl_pct, 2, true)} on what you paid in`} />
        </div>
        {insights.length > 0 && (
          <Section title="Worth a look">
            <ul className="divide-y divide-line border-y border-line">
              {insights.map((i) => (
                <li key={i.href}>
                  <Link href={i.href} className="group flex items-start justify-between gap-6 py-3">
                    <span className="min-w-0">
                      <span className="flex items-center gap-2 font-medium">
                        {i.caution && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-caution" />}{i.title}
                      </span>
                      <span className="block text-sm text-ink-2">{i.text}</span>
                    </span>
                    <span className="shrink-0 text-sm text-muted group-hover:text-ink">Open</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        )}
        <Section title="Where your money is" description="Each fund's colour shows its risk band, from 1 (calmest) to 5 (most volatile).">
          <AllocationBar slices={fundSlices} total={total} />
          <div className="mt-8 grid gap-8 md:grid-cols-2">
            <AllocationBar title="By asset class" slices={slices(portfolio.by_asset_class, ASSET)} total={total} />
            <AllocationBar title="By region" slices={slices(portfolio.by_region, REGION)} total={total} />
          </div>
        </Section>
        <Section title="Holdings">
          <div className={tableStyles.wrap}>
            <table className={tableStyles.table}>
              <thead className={tableStyles.head}>
                <tr>
                  <th className={tableStyles.th}>Fund</th>
                  <th className={`${tableStyles.th} text-right`}>Units</th>
                  <th className={`${tableStyles.th} text-right`}>Price</th>
                  <th className={`${tableStyles.th} text-right`}>Value</th>
                  <th className={`${tableStyles.th} text-right`}>Gain or loss</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h) => (
                  <tr key={h.instrument} className={tableStyles.row}>
                    <td className={tableStyles.td}>
                      <Link href={`/investor/funds/${h.instrument}`} className="font-medium hover:underline">{h.name}</Link>
                      <span className="ml-2 text-xs text-muted">{h.instrument}</span>
                    </td>
                    <td className={`${tableStyles.td} num text-right`}>{Number(h.units).toFixed(4)}</td>
                    <td className={`${tableStyles.td} num text-right`}>{formatUsd(h.price)}<span className="block text-xs text-muted">{formatDate(h.price_as_of)}</span></td>
                    <td className={`${tableStyles.td} num text-right`}>{formatUsd(h.value)}</td>
                    <td className={`${tableStyles.td} num text-right ${Number(h.pnl) >= 0 ? "text-gain" : "text-loss"}`}>
                      {formatSignedUsd(h.pnl)}<span className="block text-xs">{formatPct(h.pnl_pct, 2, true)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
        <WhyPanel title="how this valuation was computed" model="deterministic valuation engine (no AI)"
          evidence={[
            { label: "Prices", detail: "Each fund is valued at its last published price on or before the valuation date." },
            { label: "Paid in", detail: "The purchase cost of the units you still hold, first in, first out. Realised gains are excluded." },
            { label: "Asset class and region", detail: "Each fund's value is split across the ETFs it holds, using their fixed weights." },
          ]} />
      </div>
    </>
  );
}
