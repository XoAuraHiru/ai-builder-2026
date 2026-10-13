"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth, formatPct, formatUsd } from "@/lib/format";
import { heat, verdictText, type Fund, type Narrative, type RiskReport } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { RiskScale } from "@/components/risk-scale";
import { Button, ButtonLink, EmptyState, Figure, KeyMoment, Loading, Notice, PageHeader, Panel, Section, Sparkle } from "@/components/ui";

const MOMENT = {
  above: { tone: "attention", label: "Above your risk profile" },
  below: { tone: "info", label: "Calmer than your risk profile" },
  within: { tone: "good", label: "In line with your risk profile" },
  no_profile: { tone: "attention", label: "No risk profile to compare with" },
} as const;

function Bar({ label, pct, fill }: { label: string; pct: number; fill: string }) {
  return (
    <div className="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-3">
      <span className="text-xs text-ink-500">{label}</span>
      <span className="h-2 rounded-[4px] bg-sand-100"><span className={`block h-2 rounded-[4px] ${fill}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></span>
      <span className="num text-right text-xs text-ink-700">{formatPct(pct)}</span>
    </div>
  );
}

export default function RiskPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [report, setReport] = useState<RiskReport | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [empty, setEmpty] = useState("");
  const [error, setError] = useState("");
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [busy, setBusy] = useState(false);
  const [explainError, setExplainError] = useState("");

  useEffect(() => {
    if (!account) return;
    Promise.all([api<RiskReport>(`/accounts/${account.id}/risk`), api<Fund[]>("/funds")])
      .then(([r, f]) => { setReport(r); setNames(Object.fromEntries(f.map((x) => [x.code, x.name]))); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 409) setEmpty(e.message);
        else setError(e instanceof ApiError ? e.message : "Atrium could not load your risk report.");
      });
  }, [account]);

  async function explain() {
    setBusy(true);
    setExplainError("");
    try {
      setNarrative((await api<{ narrative: Narrative }>(`/accounts/${account!.id}/risk/explain`, { method: "POST" })).narrative);
    } catch (e) {
      setExplainError(e instanceof ApiError ? e.message : "The explanation is unavailable right now.");
    } finally {
      setBusy(false);
    }
  }

  if (!account || empty) return <><PageHeader title="Risk" /><EmptyState title="No risk to measure yet" action={<ButtonLink href="/investor/orders">Make your first investment</ButtonLink>}>{empty || "Choose an investor persona."}</EmptyState></>;
  if (error) return <><PageHeader title="Risk" /><Notice tone="error" title="Could not load your risk report">{error}</Notice></>;
  if (!report) return <><PageHeader title="Risk" /><Loading label="Replaying your mix through market history" /></>;

  const r = report;
  const codes = Object.keys(r.weights);
  const name = (c: string) => r.names?.[c] ?? names[c] ?? c;
  const m = MOMENT[r.verdict];
  const action = r.verdict === "no_profile" ? <ButtonLink href="/investor/profile">Set your risk profile</ButtonLink>
    : r.verdict === "above" ? <><ButtonLink href="/investor/what-if">See what it means for your future</ButtonLink><ButtonLink href="/investor/orders" variant="secondary">Review your funds</ButtonLink></>
    : undefined;
  return (
    <>
      <PageHeader title="Risk" description={`How your current mix would have behaved through real markets from ${formatMonth(r.window_start)} to ${formatMonth(r.window_end)}.`} />
      <div className="space-y-12">
        <KeyMoment tone={m.tone} label={m.label} title={verdictText(r.verdict, r.portfolio_band, r.profile_band)} actions={action}>
          <RiskScale profile={r.profile_band} portfolio={r.portfolio_band} />
        </KeyMoment>
        <Section title="In numbers">
          <Panel className="p-6">
            <div className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
              <Figure label="Yearly swings" value={formatPct(r.annual_volatility_pct)} detail="Volatility: how far a typical year moves" />
              <Figure label="Worst fall" value={formatPct(r.max_drawdown_pct)} tone="loss" detail={`From ${formatMonth(r.drawdown_peak)} to ${formatMonth(r.drawdown_trough)}`} />
              <Figure label="A bad month" value={`−${formatUsd(r.var95_1m_usd, 0)}`} detail={`One month in 20 has lost more than ${formatPct(r.var95_1m_pct)}`} />
              <Figure label="Moves with the S&P 500" value={r.beta.toFixed(2)} detail={`A 10% market move has meant about ${(Math.abs(r.beta) * 10).toFixed(1)}% for you`} />
              <Figure label="Return for the risk taken" value={r.sharpe.toFixed(2)} detail="Sharpe ratio, after Treasury-bill returns" />
              <Figure label="Worst single month" value={formatPct(r.worst_month.pct)} tone="loss" detail={formatMonth(r.worst_month.month)} />
            </div>
          </Panel>
        </Section>
        <div className="grid gap-x-4 gap-y-12 xl:grid-cols-2">
          <Section title="Where the risk comes from" description="A fund can be a small share of your money and a large share of the swings.">
            <Panel className="p-6">
              <p className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-700">
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2 w-3.5 rounded-[3px] bg-sand-300" />Share of your money</span>
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2 w-3.5 rounded-[3px] bg-green-500" />Share of the swings</span>
              </p>
              <ul className="space-y-5">
                {codes.map((c) => (
                  <li key={c} className="space-y-1.5 text-sm">
                    <p className="font-medium">{name(c)}</p>
                    <Bar label="Money" pct={r.weights[c] * 100} fill="bg-sand-300" />
                    <Bar label="Risk" pct={r.risk_contributions_pct[c]} fill="bg-green-500" />
                  </li>
                ))}
              </ul>
            </Panel>
          </Section>
          {codes.length > 1 && (
            <Section title="How your funds move together" description="1.00 means two funds move in step; values near 0 mean they move independently.">
              <Panel className="p-6">
                <div className="overflow-x-auto">
                  <table className="text-sm">
                    <thead><tr><th />{codes.map((c) => <th key={c} className="code px-3 py-2 text-[11px] font-medium text-ink-500">{c}</th>)}</tr></thead>
                    <tbody>
                      {codes.map((a) => (
                        <tr key={a}>
                          <th className="py-1 pr-3 text-left text-xs font-medium text-ink-700">{name(a)}</th>
                          {codes.map((b) => (
                            <td key={b} className="num px-1 py-1 text-center">
                              <span className="block rounded-tile px-2 py-1.5 text-ink-900" style={{ background: heat(r.correlations[a][b]) }}>{r.correlations[a][b].toFixed(2)}</span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </Section>
          )}
        </div>
        <Section title="What this means for you" description="Gemini reads the figures above and explains them. It cannot change them.">
          {narrative ? <NarrativeView narrative={narrative} /> : (
            <Button variant="ai" busy={busy} onClick={explain}>{!busy && <Sparkle />}{busy ? "Gemini is reading your risk report" : "Explain my risk"}</Button>
          )}
          {explainError && <div className="mt-3"><Notice tone="caution">{explainError}</Notice></div>}
        </Section>
        <WhyPanel title="how these numbers were computed" model="risk engine over real monthly history (no AI in the figures)"
          evidence={[
            { label: "Your mix", detail: "Today's weights of your funds, held constant and rebalanced monthly over the whole history." },
            { label: "History", detail: `${r.months} months of real returns from ${formatMonth(r.window_start)} to ${formatMonth(r.window_end)}, after ETF costs and before the Atrium fee.` },
            { label: "A bad month", detail: "The 5th percentile of monthly returns (95% one-month value at risk), applied to today's value." },
            { label: "Beta and Sharpe", detail: "Beta against the S&P 500 (SPY); Sharpe uses one-to-three-month Treasury bills (BIL) as the risk-free rate." },
            { label: "Bands", detail: "Your portfolio's band is the value-weighted average of its funds' bands, rounded." },
          ]} />
      </div>
    </>
  );
}
