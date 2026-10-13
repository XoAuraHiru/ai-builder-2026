"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatMonth, formatPct } from "@/lib/format";
import type { Fund } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AiProse } from "@/components/ai-prose";
import { GrowthChart } from "@/components/line-chart";
import { YearBars } from "@/components/year-bars";
import { TickerTile } from "@/components/market-bits";
import { BAND_LABEL, Button, ButtonLink, Figure, KeyMoment, Loading, Notice, PageHeader, Panel, RiskBand, Section, Sparkle,
  tableStyles } from "@/components/ui";

type Facts = {
  window_start: string; window_end: string; annual_return_pct: number; annual_volatility_pct: number;
  max_drawdown_pct: number; drawdown_from: string; drawdown_to: string;
  best_year: { year: number; return_pct: number }; worst_year: { year: number; return_pct: number };
  calendar_years: { year: number; return_pct: number; months: number }[];
  fees: { atrium_pct: number; etf_pct: number; total_pct: number; per_10k_usd: number };
  holdings: { ticker: string; weight_pct: number; asset_class: string; region: string; expense_ratio_pct: number | null }[];
  top_companies: { symbol: string; name: string; pct: number }[];
  growth_of_10k: { month: string; value: number }[];
};
type DocSection = { id: string; title: string; paragraphs: string[]; table: { head: string[]; rows: string[][] } | null };
type Explainer = { fund: Fund; facts: Facts; sections: DocSection[] };
type Fit = {
  headline: string; points: { text: string; citations: string[] }[]; caution: string;
  citations: { id: string; title: string; text: string }[];
  suitability: { fund_band: number; your_band: number | null; verdict: "above" | "within" | "no_profile" };
  retriever: string; unsupported_figures: string[]; verified: boolean; model: string;
};

function suitabilityText(s: Fit["suitability"]): string {
  if (s.verdict === "no_profile") return `Set your risk profile to see whether a band ${s.fund_band} fund suits you.`;
  if (s.verdict === "above") return `This fund is risk band ${s.fund_band}; your profile is band ${s.your_band}. It carries more risk than your profile suggests.`;
  return `This fund is risk band ${s.fund_band}, within your profile's band ${s.your_band}.`;
}

function retrieverName(r: string): string {
  if (r === "vertex-ai-search") return "Vertex AI Search";
  return r.includes("unavailable") ? "Atrium's local document index (Vertex AI Search was unavailable)" : "Atrium's local document index";
}

export default function FundPage() {
  const { code } = useParams<{ code: string }>();
  const me = useMe();
  const [data, setData] = useState<Explainer | null>(null);
  const [error, setError] = useState("");
  const [fit, setFit] = useState<Fit | null>(null);
  const [busy, setBusy] = useState(false);
  const [fitError, setFitError] = useState("");

  const [profile, setProfile] = useState<number | null>(null);
  const isInvestor = me.roles.includes("investor");

  useEffect(() => {
    api<Explainer>(`/funds/${code}/explainer`).then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load this fund."));
  }, [code]);

  useEffect(() => {
    if (isInvestor) api<{ current_band: number | null }>("/me/risk-profile").then((p) => setProfile(p.current_band)).catch(() => setProfile(null));
  }, [isInvestor]);

  async function askFit() {
    setBusy(true);
    setFitError("");
    try {
      setFit(await api<Fit>(`/funds/${code}/fit`, { method: "POST" }));
    } catch (e) {
      setFitError(e instanceof ApiError ? e.message : "The reading is unavailable right now.");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Notice tone="error" title="Could not load this fund">{error}</Notice>;
  if (!data) return <Loading label="Loading the fund" />;
  const { fund, facts } = data;
  const titles = Object.fromEntries(data.sections.map((s) => [s.id, s.title]));
  const investor = isInvestor;
  const band = `Risk band ${fund.risk_band}, ${BAND_LABEL[fund.risk_band]}`;
  const moment = profile === null ? { tone: "info" as const, label: band }
    : fund.risk_band > profile ? { tone: "attention" as const, label: `${band}: above your profile` }
    : { tone: "good" as const, label: `${band}: within your profile` };
  return (
    <>
      <PageHeader title={fund.name} description={fund.objective} back={{ href: "/investor/funds", label: "All funds" }}
        actions={investor ? <ButtonLink href={`/investor/orders?fund=${fund.code}`}>Invest in this fund</ButtonLink> : undefined} />
      <div className="space-y-12">
        <KeyMoment tone={moment.tone} label={moment.label} title={fund.who_for}>
          <RiskBand band={fund.risk_band} profile={profile ?? fund.risk_band} size="lg" />
          <div className="grid gap-x-8 gap-y-6 border-t border-sand-100 pt-6 sm:grid-cols-2 lg:grid-cols-4">
            <Figure label="Average a year" value={formatPct(facts.annual_return_pct)} detail={`Since ${formatMonth(facts.window_start)}, before the Atrium fee`} />
            <Figure label="Yearly swings" value={formatPct(facts.annual_volatility_pct)} detail="Volatility" />
            <Figure label="Largest fall" value={formatPct(facts.max_drawdown_pct)} tone="loss" detail={`${formatMonth(facts.drawdown_from)} to ${formatMonth(facts.drawdown_to)}`} />
            <Figure label="Yearly cost" value={formatPct(facts.fees.total_pct, 2)} detail={`$${facts.fees.per_10k_usd.toFixed(0)} on $10,000`} />
          </div>
        </KeyMoment>
        <div className="grid grid-cols-1 gap-x-4 gap-y-12 xl:grid-cols-2">
          <Section title="Growth of $10,000" description="The fund's mix through real markets, on a log scale so equal percentage moves look the same size. Before October 2024 this is a backtest of the same ETFs.">
            <Panel className="p-4 sm:p-6">
              <GrowthChart points={facts.growth_of_10k} shade={{ from: facts.drawdown_from, to: facts.drawdown_to, label: "Largest fall" }} />
            </Panel>
          </Section>
          <Section title="Year by year" description={`Best ${facts.best_year.year} (${formatPct(facts.best_year.return_pct, 1, true)}); worst ${facts.worst_year.year} (${formatPct(facts.worst_year.return_pct, 1, true)}).`}>
            <Panel className="p-4 sm:p-6"><YearBars years={facts.calendar_years} /></Panel>
          </Section>
        </div>
        <Section title="What it holds">
          <Panel className="px-6 py-2">
          <div className={tableStyles.wrap}>
            <table className={`${tableStyles.table} min-w-[480px]`}>
              <thead className={tableStyles.head}>
                <tr><th className={tableStyles.th}>ETF</th><th className={`${tableStyles.th} text-right`}>Weight</th><th className={tableStyles.th}>Holds</th>
                  <th className={tableStyles.th}>Region</th><th className={`${tableStyles.th} text-right`}>Expense ratio</th></tr>
              </thead>
              <tbody>
                {facts.holdings.map((h) => (
                  <tr key={h.ticker} className={tableStyles.row}>
                    <td className={tableStyles.td}><TickerTile size="sm" tone="etf" symbol={h.ticker} /><span className="sr-only">{h.ticker}</span></td>
                    <td className={`${tableStyles.td} num text-right`}>{formatPct(h.weight_pct, 0)}</td>
                    <td className={`${tableStyles.td} text-ink-700`}>{h.asset_class === "equity" ? "Stocks" : h.asset_class === "bond" ? "Bonds" : "T-bills"}</td>
                    <td className={`${tableStyles.td} text-ink-700`}>{h.region === "DM_ex_US" ? "Developed ex-US" : h.region}</td>
                    <td className={`${tableStyles.td} num text-right`}>{h.expense_ratio_pct === null ? "n/a" : formatPct(h.expense_ratio_pct, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {facts.top_companies.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 border-t border-sand-100 py-4 text-sm text-ink-700">
              <span className="mr-1">Largest companies underneath:</span>
              {facts.top_companies.map((c) => (
                <span key={c.symbol} className="whitespace-nowrap rounded-full bg-fill px-2.5 py-1 text-xs font-medium text-ink-900">
                  {c.name} <span className="num text-ink-500">{formatPct(c.pct)}</span>
                </span>
              ))}
            </div>
          )}
          </Panel>
        </Section>
        <Section title="Is it right for you?" description="Gemini reads this fund's documents and your risk profile. Every point cites the passage it relies on.">
          {fit ? (
            <div className="space-y-4">
              <Notice tone={fit.suitability.verdict === "above" ? "caution" : fit.suitability.verdict === "within" ? "success" : "info"}>
                {suitabilityText(fit.suitability)}
              </Notice>
              <AiProse caption={`Written by ${fit.model}. Passages retrieved by ${retrieverName(fit.retriever)}.`}
                warning={fit.verified ? undefined : `Check before relying on this: ${fit.unsupported_figures.join(", ")} did not come from the fund documents.`}>
                <p className="text-[20px] font-semibold leading-snug">{fit.headline}</p>
                <ul className="mt-3 space-y-3">
                  {fit.points.map((p, i) => (
                    <li key={i}>
                      {p.text}{" "}
                      <span className="inline-flex flex-wrap gap-1 align-middle font-sans">
                        {p.citations.map((c) => (
                          <a key={c} href={`#doc-${c.split("#")[1]}`}
                            className="rounded-[4px] border border-ai-100 bg-ai-50 px-1.5 py-px text-xs font-medium text-ai-700 hover:border-ai-500">
                            {titles[c.split("#")[1]] ?? c}
                          </a>
                        ))}
                      </span>
                    </li>
                  ))}
                </ul>
                {fit.caution && <p className="mt-3 text-[15px] text-ink-700">{fit.caution}</p>}
              </AiProse>
            </div>
          ) : investor ? (
            <Button variant="ai" busy={busy} onClick={askFit}>{!busy && <Sparkle />}{busy ? "Gemini is reading the fund documents" : "Ask Gemini whether it fits me"}</Button>
          ) : (
            <p className="text-sm text-ink-500">Personal readings are for investors.</p>
          )}
          {fitError && <div className="mt-3"><Notice tone="caution">{fitError}</Notice></div>}
        </Section>
        <Section title="Fact sheet" description="The same document Atrium's search indexes and the AI cites.">
          <Panel className="space-y-6 p-6">
            {data.sections.map((s) => (
              <section key={s.id} id={`doc-${s.id}`} className="scroll-mt-20">
                <h3 className="text-sm font-semibold">{s.title}</h3>
                {s.paragraphs.map((p, i) => <p key={i} className="mt-1.5 max-w-[72ch] text-sm leading-relaxed text-ink-700">{p}</p>)}
              </section>
            ))}
          </Panel>
        </Section>
      </div>
    </>
  );
}
