"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth, formatPct, formatUsd } from "@/lib/format";
import { heat, verdictText, type Fund, type Narrative, type RiskReport } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Button, ButtonLink, EmptyState, Figure, Loading, Notice, PageHeader, RiskBand, Section } from "@/components/ui";

function Bar({ label, pct, fill }: { label: string; pct: number; fill: string }) {
  return (
    <div className="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-3">
      <span className="text-xs text-muted">{label}</span>
      <span className="h-1.5 rounded-full bg-line"><span className={`block h-1.5 rounded-full ${fill}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></span>
      <span className="num text-right text-xs text-ink-2">{formatPct(pct)}</span>
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
  const tone = r.verdict === "above" ? "caution" : r.verdict === "within" ? "success" : "info";
  return (
    <>
      <PageHeader title="Risk" description={`How your current mix would have behaved through real markets from ${formatMonth(r.window_start)} to ${formatMonth(r.window_end)}.`} />
      <div className="space-y-12">
        <Section title="Compared with your risk profile">
          <div className="grid gap-6 sm:grid-cols-2">
            <div><p className="text-sm text-muted">Your portfolio behaves like</p><div className="mt-2"><RiskBand band={r.portfolio_band} size="lg" /></div></div>
            <div><p className="text-sm text-muted">Your risk profile</p><div className="mt-2"><RiskBand band={r.profile_band} size="lg" /></div></div>
          </div>
          <div className="mt-5">
            <Notice tone={tone} action={r.verdict === "no_profile" ? <ButtonLink href="/investor/profile" variant="secondary">Set your profile</ButtonLink>
              : r.verdict === "above" ? <ButtonLink href="/investor/orders" variant="secondary">Review your funds</ButtonLink> : undefined}>
              {verdictText(r.verdict, r.portfolio_band, r.profile_band)}
            </Notice>
          </div>
        </Section>
        <Section title="In numbers">
          <div className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
            <Figure label="Yearly swings" value={formatPct(r.annual_volatility_pct)} detail="Volatility: how far a typical year moves" />
            <Figure label="Worst fall" value={formatPct(r.max_drawdown_pct)} tone="loss" detail={`From ${formatMonth(r.drawdown_peak)} to ${formatMonth(r.drawdown_trough)}`} />
            <Figure label="A bad month" value={`−${formatUsd(r.var95_1m_usd, 0)}`} detail={`One month in 20 has lost more than ${formatPct(r.var95_1m_pct)}`} />
            <Figure label="Moves with the S&P 500" value={r.beta.toFixed(2)} detail={`A 10% market move has meant about ${(Math.abs(r.beta) * 10).toFixed(1)}% for you`} />
            <Figure label="Return for the risk taken" value={r.sharpe.toFixed(2)} detail="Sharpe ratio, after Treasury-bill returns" />
            <Figure label="Worst single month" value={formatPct(r.worst_month.pct)} tone="loss" detail={formatMonth(r.worst_month.month)} />
          </div>
        </Section>
        <Section title="Where the risk comes from" description="A fund can be a small share of your money and a large share of the swings.">
          <ul className="space-y-5">
            {codes.map((c) => (
              <li key={c} className="text-sm">
                <p className="mb-1.5 font-medium">{name(c)}</p>
                <Bar label="Money" pct={r.weights[c] * 100} fill="bg-line-strong" />
                <Bar label="Risk" pct={r.risk_contributions_pct[c]} fill="bg-ink" />
              </li>
            ))}
          </ul>
        </Section>
        {codes.length > 1 && (
          <Section title="How your funds move together" description="1.00 means two funds move in step; values near 0 mean they move independently.">
            <div className="overflow-x-auto">
              <table className="text-sm">
                <thead><tr><th />{codes.map((c) => <th key={c} className="px-3 py-2 text-xs font-medium text-muted">{c}</th>)}</tr></thead>
                <tbody>
                  {codes.map((a) => (
                    <tr key={a}>
                      <th className="py-1 pr-3 text-left text-xs font-medium text-muted">{name(a)}</th>
                      {codes.map((b) => (
                        <td key={b} className="num px-1 py-1 text-center">
                          <span className="block rounded-[4px] px-2 py-1.5" style={{ background: heat(r.correlations[a][b]) }}>{r.correlations[a][b].toFixed(2)}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}
        <Section title="What this means for you" description="Gemini reads the figures above and explains them. It cannot change them.">
          {narrative ? <NarrativeView narrative={narrative} /> : (
            <Button variant="secondary" busy={busy} onClick={explain}>{busy ? "Gemini is reading your risk report" : "Explain my risk"}</Button>
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
