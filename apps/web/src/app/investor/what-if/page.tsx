"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Portfolio } from "@/lib/api";
import { formatMonth, formatPct, formatUsd } from "@/lib/format";
import { currentMix, parseMoney, SERIES, scenarioKey, toggleScenario, type Fund, type Narrative, type ScenarioIn,
  type ScenarioOut, type WhatIf } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { FanChart } from "@/components/fan-chart";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Button, Field, Loading, MoneyInput, Notice, PageHeader, Panel, RiskBand, Section, tableStyles } from "@/components/ui";

const message = (e: unknown) => (e instanceof ApiError ? e.message : "Atrium could not reach its server. Try again.");

function OutcomeTable({ result, active, onSelect }: { result: WhatIf; active: number; onSelect: (i: number) => void }) {
  const rows: [string, (s: ScenarioOut) => string][] = [
    ["Middle outcome", (s) => formatUsd(s.final.p50, 0)],
    ["1 in 10 ends below", (s) => formatUsd(s.final.p10, 0)],
    ["1 in 10 ends above", (s) => formatUsd(s.final.p90, 0)],
  ];
  if (result.goal_usd) rows.push(["Chance of reaching your goal", (s) => formatPct(s.prob_goal ?? 0)]);
  rows.push(["Chance of ending below what you paid in", (s) => formatPct(s.prob_loss)]);
  rows.push([`Fees over ${result.years} years`, (s) => `${formatUsd(s.fee_cost, 0)} (${formatPct(s.fee_bps / 100, 2)} a year)`]);
  return (
    <Section title={`After ${result.years} year${result.years === 1 ? "" : "s"}`} description={`You pay in ${formatUsd(result.contributed, 0)} in total.`}>
      <div className={tableStyles.wrap}>
        <table className={tableStyles.table}>
          <thead className={tableStyles.head}>
            <tr>
              <th className={tableStyles.th}><span className="sr-only">Measure</span></th>
              {result.scenarios.map((s, i) => (
                <th key={i} className={`${tableStyles.th} text-right`}>
                  <button type="button" onClick={() => onSelect(i)} aria-pressed={i === active}
                    className={`inline-flex items-center gap-1.5 ${i === active ? "text-ink" : "hover:text-ink"}`}>
                    <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: SERIES[i] }} />{s.label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className={tableStyles.row}>
                <td className={`${tableStyles.td} text-ink-2`}>{label}</td>
                {result.scenarios.map((s, i) => (
                  <td key={i} className={`${tableStyles.td} num text-right ${i === active ? "font-semibold" : ""}`}>{value(s)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

export default function WhatIfStudio() {
  const me = useMe();
  const account = me.accounts[0];
  const [funds, setFunds] = useState<Fund[]>([]);
  const [mix, setMix] = useState<Record<string, number> | null>(null);
  const [initial, setInitial] = useState("10000");
  const [monthly, setMonthly] = useState("500");
  const [years, setYears] = useState(15);
  const [goal, setGoal] = useState("");
  const [scenarios, setScenarios] = useState<ScenarioIn[] | null>(null);
  const [result, setResult] = useState<WhatIf | null>(null);
  const [active, setActive] = useState(0);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState("");
  const latest = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        setFunds(await api<Fund[]>("/funds"));
        let m: Record<string, number> | null = null;
        if (account) {
          const p = await api<Portfolio>(`/accounts/${account.id}/portfolio`);
          m = currentMix(p.by_fund);
          if (m) setInitial(String(Math.round(Number(p.total_value))));
        }
        setMix(m);
        setScenarios(m ? [{ label: "Your current mix", allocation: m }, { allocation: { "ATR-BAL": 1 } }]
          : [{ allocation: { "ATR-BAL": 1 } }, { allocation: { "ATR-GRW": 1 } }]);
      } catch (e) {
        setError(message(e));
      }
    })();
  }, [account]);

  const payload = useCallback(() => ({
    initial_usd: parseMoney(initial), monthly_usd: parseMoney(monthly), years,
    goal_usd: parseMoney(goal) > 0 ? parseMoney(goal) : null, scenarios,
  }), [initial, monthly, years, goal, scenarios]);

  useEffect(() => {
    if (!scenarios) return;
    if (parseMoney(initial) === 0 && parseMoney(monthly) === 0) {
      setError("Enter a starting amount, a monthly amount, or both.");
      return;
    }
    const ticket = ++latest.current;
    const timer = setTimeout(async () => {
      setRunning(true);
      try {
        const r = await api<WhatIf>("/invest/what-if", { method: "POST", body: JSON.stringify(payload()) });
        if (ticket !== latest.current) return;
        setResult(r);
        setError("");
        setNarrative(null);
        setExplainError("");
        setActive((a) => Math.min(a, r.scenarios.length - 1));
      } catch (e) {
        if (ticket === latest.current) setError(message(e));
      } finally {
        if (ticket === latest.current) setRunning(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [payload, scenarios, initial, monthly]);

  async function explain() {
    setExplaining(true);
    setExplainError("");
    try {
      const r = await api<{ result: WhatIf; narrative: Narrative }>("/invest/what-if/explain", { method: "POST", body: JSON.stringify(payload()) });
      setNarrative(r.narrative);
    } catch (e) {
      setExplainError(message(e));
    } finally {
      setExplaining(false);
    }
  }

  const options = [
    ...(mix ? [{ scenario: { label: "Your current mix", allocation: mix } as ScenarioIn, name: "Your current mix", band: null as number | null }] : []),
    ...funds.map((f) => ({ scenario: { allocation: { [f.code]: 1 } } as ScenarioIn, name: f.name.replace(/^Atrium /, ""), band: f.risk_band as number | null })),
  ];
  const selected = new Set((scenarios ?? []).map(scenarioKey));

  return (
    <>
      <PageHeader title="What-if Studio"
        description="Choose an amount, a monthly habit and a time frame. Atrium simulates 10,000 futures from real market history since 2007, crashes included." />
      <div className="grid gap-8 lg:grid-cols-[290px_minmax(0,1fr)]">
        <Panel className="h-fit space-y-5 p-5 lg:sticky lg:top-8">
          <Field label="Start with"><MoneyInput value={initial} onChange={setInitial} /></Field>
          <Field label="Add every month"><MoneyInput value={monthly} onChange={setMonthly} /></Field>
          <div>
            <label htmlFor="years" className="flex items-baseline justify-between text-sm font-medium">
              <span>For</span><span className="num">{years} year{years === 1 ? "" : "s"}</span>
            </label>
            <input id="years" type="range" min={1} max={40} value={years} onChange={(e) => setYears(Number(e.target.value))}
              className="mt-2 w-full accent-[var(--color-ink)]" />
          </div>
          <Field label="Goal" hint="Optional: the amount you hope to reach."><MoneyInput value={goal} onChange={setGoal} placeholder="No goal set" /></Field>
          <fieldset>
            <legend className="text-sm font-medium">Compare</legend>
            <p className="text-xs text-muted">Choose up to three.</p>
            <ul className="mt-2 space-y-1">
              {options.map((o) => {
                const on = selected.has(scenarioKey(o.scenario));
                return (
                  <li key={o.name}>
                    <button type="button" aria-pressed={on} onClick={() => setScenarios((list) => toggleScenario(list ?? [], o.scenario))}
                      className={`flex w-full items-center justify-between gap-2 rounded-control border px-2.5 py-1.5 text-left text-sm ${on ? "border-ink bg-ground" : "border-transparent hover:border-line-strong"}`}>
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className={`flex h-3.5 w-3.5 items-center justify-center rounded-[3px] border ${on ? "border-ink bg-ink" : "border-line-strong"}`}>
                          {on && <svg viewBox="0 0 14 14" className="h-3 w-3 text-white"><path d="M3 7.5 6 10l5-6" fill="none" stroke="currentColor" strokeWidth="1.75" /></svg>}
                        </span>
                        {o.name}
                      </span>
                      {o.band !== null && <RiskBand band={o.band} showLabel={false} />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        </Panel>
        <div className="min-w-0 space-y-10">
          {error && <Notice tone="error">{error}</Notice>}
          {!result ? <Loading label="Simulating 10,000 futures" /> : (
            <>
              <section aria-label="Projection">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  {result.scenarios.map((s, i) => (
                    <button key={`${s.label}-${i}`} type="button" aria-pressed={i === active} onClick={() => setActive(i)}
                      className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm ${i === active ? "border-ink text-ink" : "border-line text-ink-2 hover:border-line-strong"}`}>
                      <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: SERIES[i] }} />{s.label}
                    </button>
                  ))}
                  {running && <span role="status" className="text-xs text-muted">Updating…</span>}
                </div>
                <FanChart scenarios={result.scenarios} active={active} goal={result.goal_usd} colors={SERIES} />
                <p className="mt-2 text-xs text-muted">
                  Shaded: the middle 50% and 80% of simulated outcomes. Dashed: what you pay in. Point at the chart to read any year.
                </p>
              </section>
              <OutcomeTable result={result} active={active} onSelect={setActive} />
              <Section title="What this means for you" description="Gemini reads the figures above and explains them. It cannot change them.">
                {narrative ? <NarrativeView narrative={narrative} /> : (
                  <Button variant="secondary" busy={explaining} onClick={explain}>
                    {explaining ? "Gemini is reading the figures" : "Explain these results"}
                  </Button>
                )}
                {explainError && <div className="mt-3"><Notice tone="caution">{explainError}</Notice></div>}
              </Section>
              <WhyPanel title="how this simulation works" model="Atrium Monte Carlo engine (no AI in the numbers)"
                evidence={[
                  { label: "Method", detail: result.method },
                  { label: "History used", detail: `${result.months} months from ${formatMonth(result.window_start)} to ${formatMonth(result.window_end)}, including the 2008 crisis, the 2020 crash and the 2022 rate shock.` },
                  ...result.scenarios.map((s) => ({ label: s.label, detail: `Worst 12 months in that history ${formatPct(s.history.worst_12m_pct)}; largest fall ${formatPct(s.history.max_drawdown_pct)}; yearly fee ${formatPct(s.fee_bps / 100, 2)}.` })),
                  { label: "Before you rely on it", detail: "A simulation, not a forecast. Markets can behave in ways the last two decades did not." },
                ]} />
            </>
          )}
        </div>
      </div>
    </>
  );
}
