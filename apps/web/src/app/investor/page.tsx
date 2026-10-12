"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type Holding, type Portfolio } from "@/lib/api";
import { formatDate, formatPct, formatSignedUsd, formatUsd } from "@/lib/format";
import { BAND_COLOR, CATEGORY, verdictText, type RiskReport, type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar, type Slice } from "@/components/allocation-bar";
import { RiskScale } from "@/components/risk-scale";
import { WhyPanel } from "@/components/why-panel";
import { ButtonLink, EmptyState, KeyMoment, Loading, Notice, Section, tableStyles } from "@/components/ui";

const ASSET: Record<string, string> = { equity: "Stocks", bond: "Bonds", cash: "Cash and T-bills" };
const REGION: Record<string, string> = { US: "United States", DM_ex_US: "Developed outside the US", EM: "Emerging markets", Global: "Global" };
const CASH_GREY = "#9aa3aa";

function slices(map: Record<string, string>, names: Record<string, string>): Slice[] {
  return Object.entries(map).map(([k, v], i) => ({ key: k, label: names[k] ?? k, value: Number(v), color: CATEGORY[i % CATEGORY.length] }));
}

function holdingHref(h: Holding): string | null {
  if (h.kind === "fund") return `/investor/funds/${h.instrument}`;
  if (h.kind === "cash") return "/investor/trades";
  return `/investor/markets/${h.instrument}`;
}

const MOMENT = {
  above: { tone: "attention", label: "One thing needs your attention", title: "Your mix has drifted above the risk you chose." },
  below: { tone: "info", label: "Worth knowing", title: "Your mix is calmer than the risk you chose." },
  within: { tone: "good", label: "All in order", title: "Your mix matches the risk you chose." },
  no_profile: { tone: "attention", label: "One thing to do", title: "Set your risk profile, so Atrium can check your mix against it." },
} as const;

function RiskMoment({ risk }: { risk: RiskReport }) {
  const m = MOMENT[risk.verdict];
  const actions = risk.verdict === "no_profile"
    ? <ButtonLink href="/investor/profile">Set your risk profile</ButtonLink>
    : risk.verdict === "within"
      ? <ButtonLink href="/investor/risk" variant="secondary">Open your risk report</ButtonLink>
      : <><ButtonLink href="/investor/what-if">See what it means for your future</ButtonLink><ButtonLink href="/investor/risk" variant="secondary">Open your risk report</ButtonLink></>;
  return (
    <KeyMoment tone={m.tone} label={m.label} title={m.title} actions={actions}>
      <RiskScale profile={risk.profile_band} portfolio={risk.portfolio_band} />
      <p className="max-w-[60ch] text-[15px] text-ink-2">{verdictText(risk.verdict, risk.portfolio_band, risk.profile_band)}</p>
    </KeyMoment>
  );
}

export default function InvestorHome() {
  const me = useMe();
  const account = me.accounts[0];
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [xray, setXray] = useState<XRay | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!account) return;
    (async () => {
      try {
        setPortfolio(await api<Portfolio>(`/accounts/${account.id}/portfolio`));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Atrium could not value your portfolio. Try again.");
        return;
      }
      const [r, x] = await Promise.allSettled([api<RiskReport>(`/accounts/${account.id}/risk`), api<XRay>(`/accounts/${account.id}/xray`)]);
      if (r.status === "fulfilled") setRisk(r.value);
      if (x.status === "fulfilled") setXray(x.value);
    })();
  }, [account]);

  if (!account) return <EmptyState title="No investment account yet">Choose an investor on the front page to see a portfolio.</EmptyState>;
  if (error) return <Notice tone="error" title="Could not load your portfolio">{error}</Notice>;
  if (!portfolio) return <Loading label="Valuing your portfolio" />;

  const total = Number(portfolio.total_value);
  const up = Number(portfolio.pnl) >= 0;
  const pricedOn = portfolio.holdings.map((h) => h.price_as_of).sort().at(-1) ?? portfolio.as_of;
  const holdingSlices = portfolio.holdings.map((h) => ({
    key: h.instrument, label: h.name, value: Number(h.value), color: h.kind === "cash" ? CASH_GREY : BAND_COLOR[h.risk_band ?? 3] }));
  const warnings = xray?.warnings ?? [];

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[15px] font-semibold text-muted">Your portfolio</h1>
          <p className="num wide mt-1.5 text-[44px] font-semibold leading-none tracking-[-0.03em] sm:text-[54px]">{formatUsd(portfolio.total_value)}</p>
          <p className="num mt-2 text-[15px]">
            <span className={`font-semibold ${up ? "text-gain" : "text-loss"}`}>{formatSignedUsd(portfolio.pnl)}, {up ? "up" : "down"} {formatPct(Math.abs(Number(portfolio.pnl_pct)), 2)}</span>
            <span className="text-muted"> on what you paid in. Account {account.number}, priced {formatDate(pricedOn)}.</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href="/investor/orders" variant="secondary">Invest or withdraw</ButtonLink>
          <ButtonLink href="/investor/markets" variant="secondary">Trade shares</ButtonLink>
        </div>
      </div>

      {risk ? <RiskMoment risk={risk} /> : <Loading label="Checking your mix against your risk profile" />}

      {warnings.length > 0 && (
        <Notice tone="caution" title={`The Portfolio X-ray found ${warnings.length} thing${warnings.length > 1 ? "s" : ""} to look at`}
          action={<ButtonLink href="/investor/xray" variant="secondary" size="sm">Open the X-ray</ButtonLink>}>
          Starting with: {warnings[0].title.charAt(0).toLowerCase()}{warnings[0].title.slice(1)}.
        </Notice>
      )}

      <Section title="What you hold" description="Each holding's colour shows its risk band, from 1 (calmest) to 5 (most volatile). Cash for trading is grey.">
        <AllocationBar slices={holdingSlices} total={total} />
        <div className={`${tableStyles.wrap} mt-6 rounded-panel border border-line bg-surface px-5`}>
          <table className={tableStyles.table}>
            <thead className={tableStyles.head}>
              <tr>
                <th className={tableStyles.th}>Holding</th>
                <th className={`${tableStyles.th} text-right`}>Units</th>
                <th className={`${tableStyles.th} text-right`}>Price</th>
                <th className={`${tableStyles.th} text-right`}>Value</th>
                <th className={`${tableStyles.th} text-right`}>Gain or loss</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.holdings.map((h) => {
                const href = holdingHref(h);
                const cash = h.kind === "cash";
                return (
                  <tr key={h.instrument} className={tableStyles.row}>
                    <td className={tableStyles.td}>
                      {href ? <Link href={href} className="font-semibold hover:underline">{h.name}</Link> : <span className="font-semibold">{h.name}</span>}
                      {!cash && <span className="ml-2 text-xs text-muted">{h.instrument}</span>}
                    </td>
                    <td className={`${tableStyles.td} num text-right`}>{cash ? "" : Number(h.units).toFixed(h.kind === "fund" ? 4 : 0)}</td>
                    <td className={`${tableStyles.td} num text-right`}>
                      {cash ? "" : <>{formatUsd(h.price)}<span className="block text-xs text-muted">{formatDate(h.price_as_of)}</span></>}
                    </td>
                    <td className={`${tableStyles.td} num text-right font-semibold`}>{formatUsd(h.value)}</td>
                    <td className={`${tableStyles.td} num text-right ${Number(h.pnl) >= 0 ? "text-gain" : "text-loss"}`}>
                      {cash ? "" : <>{formatSignedUsd(h.pnl)}<span className="block text-xs">{formatPct(h.pnl_pct, 2, true)}</span></>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="How it is spread">
        <div className="grid gap-8 2xl:grid-cols-2">
          <AllocationBar title="By asset class" slices={slices(portfolio.by_asset_class, ASSET)} total={total} />
          <AllocationBar title="By region" slices={slices(portfolio.by_region, REGION)} total={total} />
        </div>
      </Section>

      <WhyPanel title="how this valuation was computed" model="deterministic valuation engine (no AI)"
        evidence={[
          { label: "Prices", detail: "Each fund is valued at its last published price. Shares and ETFs you hold directly are valued at the latest quote, and paper cash at face value." },
          { label: "Paid in", detail: "The purchase cost of the units and shares you still hold, first in, first out, plus your paper cash. Realised gains are excluded." },
          { label: "Asset class and region", detail: "Each fund's value is split across the ETFs it holds, using their fixed weights; a share counts as a US stock." },
        ]} />
    </div>
  );
}
