"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type Holding, type Portfolio } from "@/lib/api";
import { formatDate, formatPct, formatSignedUsd, formatUsd } from "@/lib/format";
import { ASSET_COLOR, BAND_COLOR, CATEGORY, copilotHref, overlapLine, riskState, topExposures, verdictText, type RiskReport,
  type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar, type Slice } from "@/components/allocation-bar";
import { TickerTile } from "@/components/market-bits";
import { RiskScale } from "@/components/risk-scale";
import { WhyPanel } from "@/components/why-panel";
import { ButtonLink, ChangeChip, EmptyState, KeyMoment, Loading, Notice, Panel, Section, Sparkle, tableStyles } from "@/components/ui";

const ASSET: Record<string, string> = { equity: "Stocks", bond: "Bonds", cash: "Cash and T-bills" };
const REGION: Record<string, string> = { US: "United States", DM_ex_US: "Developed outside the US", EM: "Emerging markets", Global: "Global" };
// Paper cash sits in the bar in sand-300: present, but quieter than anything that carries risk.
const CASH_SAND = "#dcdad1";

/** Slices ranked largest first; asset classes keep their own calm colours, anything else takes the series in order. */
function slices(map: Record<string, string>, names: Record<string, string>): Slice[] {
  return Object.entries(map).map(([k, v]) => ({ key: k, label: names[k] ?? k, value: Number(v) }))
    .sort((a, b) => b.value - a.value)
    .map((s, i) => ({ ...s, color: ASSET_COLOR[s.key] ?? CATEGORY[i % CATEGORY.length] }));
}

function holdingHref(h: Holding): string | null {
  if (h.kind === "fund") return `/investor/funds/${h.instrument}`;
  if (h.kind === "cash") return "/investor/trades";
  return `/investor/markets/${h.instrument}`;
}

function holdingDetail(h: Holding): string {
  if (h.kind === "cash") return "Paper cash for trading";
  if (h.kind === "fund") return `${Number(h.units).toFixed(4)} units`;
  const n = Number(h.units);
  return `${n} ${h.kind === "etf" ? "ETF " : ""}${n === 1 ? "share" : "shares"}`;
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
      <p className="max-w-[60ch] text-[15px] leading-[22px] text-ink-700">{verdictText(risk.verdict, risk.portfolio_band, risk.profile_band)}</p>
    </KeyMoment>
  );
}

/** H3: the largest exposures from the X-ray, so Home says what you own underneath. */
function WhereMoneySits({ xray, failed }: { xray: XRay | null; failed: boolean }) {
  const rows = xray ? topExposures(xray.sectors) : [];
  const caption = xray ? overlapLine(xray.overlaps) ?? (xray.warnings[0] ? `The X-ray found: ${xray.warnings[0].title.toLowerCase()}.` : null) : null;
  return (
    <Panel className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Where your money sits</h2>
        <Link href="/investor/xray" className="text-[13px] font-semibold text-green-600 hover:text-green-800 hover:underline">Open X-ray</Link>
      </div>
      {xray ? (
        <ul className="flex flex-col gap-3">
          {rows.map((r) => (
            <li key={r.name} className="grid grid-cols-[minmax(0,120px)_minmax(0,1fr)_48px] items-center gap-3 text-[13px]">
              <span className="truncate" title={r.name}>{r.name}</span>
              <span aria-hidden="true" className="h-2 rounded-[4px] bg-sand-100">
                <span className="block h-2 rounded-[4px] bg-green-400" style={{ width: `${r.width}%` }} />
              </span>
              <span className="num text-right">{formatPct(r.pct)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-[13px] text-ink-500" role="status">{failed ? "The X-ray is unavailable right now." : "Looking through your funds…"}</p>}
      {caption && <p className="text-xs leading-[18px] text-ink-500">{caption}</p>}
    </Panel>
  );
}

/** H4: suggested questions beside the drift card, in the Gemini style; each opens the copilot with it in the box. */
function AskAtrium({ questions }: { questions: string[] }) {
  return (
    <section aria-labelledby="ask-atrium" className="flex flex-col gap-3.5 rounded-panel bg-ai-50 px-6 py-[22px]">
      <h2 id="ask-atrium" className="inline-flex items-center gap-2 text-sm font-semibold text-ai-700"><Sparkle />Ask Atrium</h2>
      <ul className="flex flex-col gap-2">
        {questions.map((q) => (
          <li key={q}>
            <Link href={copilotHref(q)} className="block rounded-control bg-white px-3.5 py-2.5 font-serif text-base leading-[22px] text-ink-900 transition-shadow hover:ring-2 hover:ring-ai-100">
              {q}
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-xs leading-[18px] text-ai-700">Answers come from your own figures.</p>
    </section>
  );
}

export default function InvestorHome() {
  const me = useMe();
  const account = me.accounts[0];
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [riskError, setRiskError] = useState("");
  const [xray, setXray] = useState<XRay | null>(null);
  const [xrayFailed, setXrayFailed] = useState(false);
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
      const state = riskState(r);
      if ("report" in state) setRisk(state.report);
      else setRiskError(state.error);
      if (x.status === "fulfilled") setXray(x.value);
      else setXrayFailed(true);
    })();
  }, [account]);

  if (!account) return <EmptyState title="No investment account yet">Choose an investor on the front page to see a portfolio.</EmptyState>;
  if (error) return <Notice tone="error" title="Could not load your portfolio">{error}</Notice>;
  if (!portfolio) return <Loading label="Valuing your portfolio" />;

  const total = Number(portfolio.total_value);
  const pnl = Number(portfolio.pnl);
  const pricedOn = portfolio.holdings.map((h) => h.price_as_of).sort().at(-1) ?? portfolio.as_of;
  const holdingSlices = portfolio.holdings.map((h) => ({
    key: h.instrument, label: h.name, value: Number(h.value), color: h.kind === "cash" ? CASH_SAND : BAND_COLOR[h.risk_band ?? 3] }));
  const questions = ["Should I rebalance?",
    risk ? `Why is my portfolio in band ${risk.portfolio_band}?` : "How risky is my portfolio compared with my profile?"];

  return (
    <div className="space-y-12">
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-6 pt-1 sm:px-2 sm:pt-3">
          <div className="flex min-w-0 flex-col gap-2.5">
            <h1 className="text-sm font-medium text-ink-700">Your portfolio</h1>
            <p className="num text-[44px] font-medium leading-[48px] tracking-[-0.03em] sm:text-[60px] sm:leading-[60px] sm:tracking-[-0.035em]">
              {formatUsd(portfolio.total_value)}
            </p>
            <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
              <ChangeChip size="md" value={pnl}>
                <span className="sr-only">{pnl >= 0 ? "Up" : "Down"} </span>
                <span aria-hidden="true">{pnl >= 0 ? "↑" : "↓"}</span> {formatUsd(Math.abs(pnl))} · {formatPct(Math.abs(Number(portfolio.pnl_pct)), 2)}
              </ChangeChip>
              <span className="text-sm text-ink-700">on what you paid in</span>
              <span className="text-[13px] text-ink-500">· Account {account.number} · priced {formatDate(pricedOn)}</span>
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ButtonLink href="/investor/orders" variant="secondary">Invest or withdraw</ButtonLink>
            <ButtonLink href="/investor/markets" variant="secondary">Trade shares</ButtonLink>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)]">
          {risk ? <RiskMoment risk={risk} /> : riskError ? (
            <KeyMoment tone="info" label="Could not check your mix" title="Atrium could not compare your mix with your risk profile just now."
              actions={<ButtonLink href="/investor/risk" variant="secondary">Open your risk report</ButtonLink>}>
              <p className="text-[15px] text-ink-700">{riskError}</p>
            </KeyMoment>
          ) : <Panel className="p-7"><Loading label="Checking your mix against your risk profile" /></Panel>}
          <div className="flex flex-col gap-4">
            <WhereMoneySits xray={xray} failed={xrayFailed} />
            <AskAtrium questions={questions} />
          </div>
        </div>
      </div>

      <Section title="What you hold" description="Each holding's colour shows its risk band, from 1 (calmest) to 5 (most volatile). Paper cash for trading is sand.">
        <Panel className="px-6 pb-2 pt-6">
          <AllocationBar slices={holdingSlices} total={total} />
          <div className={`${tableStyles.wrap} mt-4`}>
            <table className={`${tableStyles.table} min-w-[520px]`}>
              <thead className={tableStyles.head}>
                <tr>
                  <th className={tableStyles.th}>Holding</th>
                  <th className={`${tableStyles.th} text-right`}>Price</th>
                  <th className={`${tableStyles.th} text-right`}>Value</th>
                  <th className={`${tableStyles.th} text-right`}>Gain or loss</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h) => {
                  const href = holdingHref(h);
                  const cash = h.kind === "cash";
                  const gain = Number(h.pnl);
                  return (
                    <tr key={h.instrument} className={tableStyles.row}>
                      <td className={tableStyles.td}>
                        <span className="flex items-center gap-3">
                          <TickerTile size="sm" symbol={cash ? "USD" : h.instrument.replace(/^ATR-/, "")}
                            tone={h.kind === "fund" ? "fund" : h.kind === "etf" ? "etf" : cash ? "cash" : "stock"} />
                          <span className="flex min-w-0 flex-col">
                            {href ? <Link href={href} className="font-medium hover:underline">{h.name}</Link> : <span className="font-medium">{h.name}</span>}
                            <span className="text-xs text-ink-500">{holdingDetail(h)}</span>
                          </span>
                        </span>
                      </td>
                      <td className={`${tableStyles.td} num text-right`}>
                        {cash ? "" : <>{formatUsd(h.price)}<span className="block text-xs text-ink-500">{formatDate(h.price_as_of)}</span></>}
                      </td>
                      <td className={`${tableStyles.td} num text-right font-medium`}>{formatUsd(h.value)}</td>
                      <td className={`${tableStyles.td} num text-right ${gain >= 0 ? "text-green-700" : "text-coral-700"}`}>
                        {cash ? "" : <>{formatSignedUsd(h.pnl)}<span className="block text-xs">{formatPct(h.pnl_pct, 2, true)}</span></>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </Section>

      <Section title="How it is spread">
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel className="min-w-0 p-6"><AllocationBar title="By asset class" slices={slices(portfolio.by_asset_class, ASSET)} total={total} /></Panel>
          <Panel className="min-w-0 p-6"><AllocationBar title="By region" slices={slices(portfolio.by_region, REGION)} total={total} /></Panel>
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
