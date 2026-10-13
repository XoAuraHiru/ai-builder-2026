"use client";

import { useEffect, useState } from "react";
import { NarrativeView, type Narrative } from "@/components/ai-prose";
import { FanChart } from "@/components/fan-chart";
import { UnitPriceChart } from "@/components/unit-price-chart";
import { Badge, Button, ButtonLink, Field, Figure, inputClass, MoneyInput, Notice, Panel, RiskBand, Segmented } from "@/components/ui";
import {
  applyLink, disclosure, fundOrderLink, MAX_YEARS, shareOrderLink, unitRange, unitStats, validate, wholeShares,
  type Analysis, type AnalyzerKind, type AnalyzerOptions, type UnitHistory, type UnitRange,
} from "@/lib/analyzer";
import { api, ApiError } from "@/lib/api";
import { deviceId } from "@/lib/device";
import { formatDate, formatMonth, formatPct, formatUsd } from "@/lib/format";
import { parseMoney, SERIES } from "@/lib/invest";
import type { MarketDetail } from "@/lib/markets";
import { useSession } from "@/lib/session-context";

const KINDS: { value: AnalyzerKind; label: string }[] = [
  { value: "unit_trust", label: "Unit trust (Atrium fund)" },
  { value: "share", label: "Shares" },
];
const RANGES: { value: UnitRange; label: string }[] = [
  { value: "1y", label: "1Y" }, { value: "2y", label: "2Y" }, { value: "all", label: "Since 2007" },
];

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <fieldset className="border-t border-line pt-5 first:border-t-0 first:pt-0">
      <legend className="flex items-center gap-2.5 text-sm font-semibold">
        <span aria-hidden="true" className="num flex h-6 w-6 items-center justify-center rounded-full border border-ink text-xs">{n}</span>
        {title}
      </legend>
      <div className="mt-3">{children}</div>
    </fieldset>
  );
}

/** Front-door return analyzer: anyone can ask what an amount in one fund or one share could become. */
export function Analyzer() {
  const { me } = useSession();
  const [options, setOptions] = useState<AnalyzerOptions | null>(null);
  const [loadError, setLoadError] = useState("");
  const [kind, setKind] = useState<AnalyzerKind | null>(null);
  const [code, setCode] = useState("");
  const [initial, setInitial] = useState("10000");
  const [monthly, setMonthly] = useState("");
  const [years, setYears] = useState(10);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<UnitHistory | null>(null);
  const [range, setRange] = useState<UnitRange>("all");
  const [price, setPrice] = useState<number | null>(null);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState("");

  const investor = Boolean(me?.roles.includes("investor") && me.accounts.length);

  useEffect(() => {
    api<AnalyzerOptions>("/analyzer/options").then(setOptions)
      .catch(() => setLoadError("The analyzer could not load its funds and shares. Refresh the page to try again."));
  }, []);

  // A share's live price, for "buy N shares": only an investor can buy, and only they may read quotes.
  useEffect(() => {
    setPrice(null);
    if (!analysis || analysis.kind !== "share" || !investor) return;
    api<MarketDetail>(`/markets/${analysis.code}`).then((d) => setPrice(Number(d.quote.price))).catch(() => setPrice(null));
  }, [analysis, investor]);

  function choose(next: AnalyzerKind) {
    setKind(next);
    setCode("");
    setError("");
    if (next === "share") setMonthly("");
  }

  async function run() {
    if (!options || !kind) return;
    const input = { kind, code, initial: parseMoney(initial), monthly: kind === "share" ? 0 : parseMoney(monthly), years };
    const problem = validate(input, options);
    setError(problem ?? "");
    if (problem) return;
    setRunning(true);
    setNarrative(null);
    setExplainError("");
    try {
      const out = await api<Analysis>("/analyzer", { method: "POST", body: JSON.stringify({
        kind, code, initial_usd: input.initial, monthly_usd: input.monthly, years, device_id: deviceId() ?? "front-door-visitor" }) });
      setAnalysis(out);
      setHistory(null);
      if (out.kind === "unit_trust") {
        api<UnitHistory>(`/funds/${out.code}/unit-history`).then(setHistory).catch(() => setHistory(null));
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The analyzer is unavailable right now; please try again.");
    } finally {
      setRunning(false);
    }
  }

  async function explain() {
    if (!analysis) return;
    setExplaining(true);
    setExplainError("");
    try {
      setNarrative((await api<{ narrative: Narrative }>(`/analyzer/${analysis.id}/explain`, { method: "POST" })).narrative);
    } catch (e) {
      setExplainError(e instanceof ApiError ? e.message : "The explanation is unavailable right now.");
    } finally {
      setExplaining(false);
    }
  }

  if (loadError) return <Notice tone="error" title="Something went wrong">{loadError}</Notice>;

  const fund = options?.funds.find((f) => f.code === code);
  const stocks = options?.shares.filter((s) => s.kind === "stock") ?? [];
  const etfs = options?.shares.filter((s) => s.kind === "etf") ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] lg:items-start">
      <Panel className="p-5 sm:p-6">
        <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <Step n={1} title="What would you invest in?">
            <Segmented label="Investment type" value={kind ?? ("" as AnalyzerKind)} options={KINDS} onChange={choose} />
          </Step>

          {kind === "unit_trust" && (
            <Step n={2} title="Choose a fund">
              <div role="radiogroup" aria-label="Fund" className="grid gap-2">
                {options?.funds.map((f) => (
                  <button key={f.code} type="button" role="radio" aria-checked={code === f.code} onClick={() => setCode(f.code)}
                    className={`flex min-h-11 flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-control border px-3.5 py-2.5 text-left text-sm ${
                      code === f.code ? "border-ink bg-ground" : "border-line hover:border-line-strong"}`}>
                    <span className="font-semibold">{f.name.replace(/^Atrium /, "")}</span>
                    <span className="flex items-center gap-3">
                      <RiskBand band={f.risk_band} showLabel={false} />
                      <span className="num text-xs text-muted">{(f.fee_bps / 100).toFixed(2)}% a year</span>
                    </span>
                  </button>
                ))}
              </div>
            </Step>
          )}

          {kind === "share" && (
            <Step n={2} title="Choose a share">
              <Field label="Stock or ETF" hint={`Shares with at least ${options?.min_share_years ?? 10} years of prices.`}>
                <select className={inputClass} value={code} onChange={(e) => setCode(e.target.value)}>
                  <option value="">Choose…</option>
                  <optgroup label="Stocks">{stocks.map((s) => <option key={s.symbol} value={s.symbol}>{s.name} ({s.symbol})</option>)}</optgroup>
                  <optgroup label="ETFs">{etfs.map((s) => <option key={s.symbol} value={s.symbol}>{s.name} ({s.symbol})</option>)}</optgroup>
                </select>
              </Field>
            </Step>
          )}

          {kind && code && (
            <>
              <Step n={3} title="How much?">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
                  <Field label="One-time amount" hint={fund ? `At least ${formatUsd(fund.min_investment, 0)}.` : "Required."}>
                    <MoneyInput label="One-time amount" value={initial} onChange={setInitial} />
                  </Field>
                  {kind === "unit_trust" && (
                    <Field label="Every month" hint={`Optional, from ${formatUsd(options?.monthly_minimum ?? 50, 0)}.`}>
                      <MoneyInput label="Every month" value={monthly} onChange={setMonthly} placeholder="0" />
                    </Field>
                  )}
                </div>
              </Step>
              <Step n={4} title="For how long?">
                <div className="flex items-center gap-4">
                  <input type="range" min={1} max={MAX_YEARS} value={years} onChange={(e) => setYears(Number(e.target.value))}
                    aria-label="Years" className="h-11 flex-1 accent-[var(--color-ink)]" />
                  <span className="num w-20 text-right text-[15px] font-semibold">{years} year{years === 1 ? "" : "s"}</span>
                </div>
              </Step>
              {error && <p role="alert" className="text-sm text-loss">{error}</p>}
              <Button type="submit" busy={running} className="w-full">{running ? "Simulating 10,000 futures" : "Analyze"}</Button>
            </>
          )}
        </form>
      </Panel>

      <div className="min-w-0">
        {analysis ? (
          <Result analysis={analysis} history={history} range={range} onRange={setRange} price={price} investor={investor}
            signedIn={Boolean(me)} narrative={narrative} explaining={explaining} explainError={explainError} onExplain={explain} />
        ) : (
          <Panel className="flex min-h-[320px] flex-col justify-center p-6 sm:p-8">
            <p className="wide max-w-[24ch] text-[22px] font-semibold leading-snug">Choose an investment, an amount and a duration.</p>
            <p className="mt-3 max-w-[52ch] text-ink-2">
              Atrium replays real markets since 2007 ten thousand ways and shows the range of what your money could become,
              with what you pay in beside it. For a fund you also see how its unit price has moved.
            </p>
          </Panel>
        )}
      </div>
    </div>
  );
}

function Result({ analysis, history, range, onRange, price, investor, signedIn, narrative, explaining, explainError, onExplain }: {
  analysis: Analysis; history: UnitHistory | null; range: UnitRange; onRange: (r: UnitRange) => void; price: number | null;
  investor: boolean; signedIn: boolean; narrative: Narrative | null; explaining: boolean; explainError: string; onExplain: () => void;
}) {
  const r = analysis.result;
  const s = r.scenarios[0];
  const scenarios = analysis.comparison ? [s, analysis.comparison] : [s];
  const shown = history ? unitRange(history.points, range) : [];
  const stats = unitStats(shown);
  const buy = analysis.kind === "share" && price ? wholeShares(r.initial_usd, price) : null;
  const paid = `${formatUsd(r.initial_usd, 0)}${r.monthly_usd ? ` plus ${formatUsd(r.monthly_usd, 0)} a month` : ""}`;

  return (
    <div className="space-y-6">
      <Panel className="p-5 sm:p-7">
        <p className="text-sm text-muted">{paid} in {analysis.name}, for {r.years} year{r.years === 1 ? "" : "s"}</p>
        <div className="mt-4">
          <Figure size="lg" label="Middle outcome" value={formatUsd(s.final.p50, 0)}
            detail="Half the simulated futures end above this, half below." />
        </div>
        <div className="mt-6 grid gap-6 border-t border-line pt-5 sm:grid-cols-2">
          <Figure label="Likely range" value={`${formatUsd(s.final.p10, 0)} to ${formatUsd(s.final.p90, 0)}`}
            detail="Eight in ten futures end in this range." />
          <Figure label="You pay in" value={formatUsd(r.contributed, 0)}
            detail={`${formatPct(s.prob_loss)} of futures end below this.`} tone={s.prob_loss >= 25 ? "loss" : undefined} />
        </div>
        <div className="mt-6 overflow-x-auto">
          <div className="min-w-[520px]">
            <FanChart scenarios={scenarios} active={0} goal={null} colors={SERIES} />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-2">
          <span className="flex items-center gap-2"><span aria-hidden="true" className="h-0.5 w-5" style={{ background: SERIES[0] }} />{analysis.name}, middle and ranges</span>
          {analysis.comparison && (
            <span className="flex items-center gap-2"><span aria-hidden="true" className="h-0.5 w-5" style={{ background: SERIES[1] }} />
              {analysis.comparison.label}, middle {formatUsd(analysis.comparison.final.p50, 0)}</span>
          )}
          <span className="flex items-center gap-2"><span aria-hidden="true" className="w-5 border-t border-dashed border-ink-2" />Paid in</span>
        </div>
        <p className="mt-4 text-sm text-ink-2">
          History used: {formatMonth(s.history.window_start)} to {formatMonth(s.history.window_end)}. Its worst 12 months
          were {formatPct(s.history.worst_12m_pct, 1, true)} and its largest fall {formatPct(s.history.max_drawdown_pct)}.
          {analysis.kind === "unit_trust" && s.fee_cost > 0 && ` Fees cost about ${formatUsd(s.fee_cost, 0)} over the period in the middle outcome.`}
        </p>
      </Panel>

      {analysis.kind === "unit_trust" && history && shown.length > 1 && (
        <Panel className="p-5 sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-[18px] font-semibold">Unit price</h3>
              <p className="text-sm text-muted">Published since {formatDate(history.inception_on)}; before that, a backtest of the fund&apos;s ETFs.</p>
            </div>
            <Segmented label="Unit price range" value={range} options={RANGES} onChange={onRange} />
          </div>
          {stats && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge tone={stats.changePct >= 0 ? "gain" : "loss"}>{formatPct(stats.changePct, 1, true)} over the range</Badge>
              <Badge tone="caution">Largest fall {formatPct(stats.fallPct)}, {formatDate(stats.fallFrom)} to {formatDate(stats.fallTo)}</Badge>
            </div>
          )}
          <div className="mt-4 overflow-x-auto">
            <div className="min-w-[520px]"><UnitPriceChart points={shown} inception={history.inception_on} /></div>
          </div>
        </Panel>
      )}

      <Panel className="p-5 sm:p-7">
        <h3 className="text-[18px] font-semibold">Turn this into an investment</h3>
        {investor ? (
          analysis.kind === "unit_trust" ? (
            <>
              <p className="mt-1 text-sm text-ink-2">Fund orders opens with {analysis.name} and {formatUsd(r.initial_usd, 0)} filled in
                {r.monthly_usd ? `, and a monthly plan of ${formatUsd(r.monthly_usd, 0)}` : ""}. You review the checks before anything is sent.</p>
              <div className="mt-4"><ButtonLink href={fundOrderLink(analysis)}>Invest in {analysis.name}</ButtonLink></div>
            </>
          ) : buy && buy.shares > 0 ? (
            <>
              <p className="mt-1 text-sm text-ink-2">At {formatUsd(price ?? 0)} a share, {formatUsd(r.initial_usd, 0)} buys {buy.shares} whole
                share{buy.shares === 1 ? "" : "s"} for {formatUsd(buy.cost)}, leaving {formatUsd(buy.left)}. The Pre-trade Guardian checks the order first.</p>
              <div className="mt-4"><ButtonLink href={shareOrderLink(analysis, price ?? 0)}>Buy {buy.shares} share{buy.shares === 1 ? "" : "s"} of {analysis.code}</ButtonLink></div>
            </>
          ) : (
            <p className="mt-1 text-sm text-ink-2">
              {buy ? `${formatUsd(r.initial_usd, 0)} is less than one share at ${formatUsd(price ?? 0)}.` : "Fetching the live price…"}
            </p>
          )
        ) : (
          <>
            <p className="mt-1 text-sm text-ink-2">An advisor gets your application with this analysis attached, so the conversation starts from it.</p>
            <div className="mt-4"><ButtonLink href={applyLink(analysis)}>Talk to an advisor about this plan</ButtonLink></div>
          </>
        )}
      </Panel>

      {signedIn && (
        <Panel className="p-5 sm:p-7">
          {narrative ? <NarrativeView narrative={narrative} /> : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-ink-2">Gemini can explain these figures in plain words; every figure it writes is checked.</p>
              <Button variant="secondary" busy={explaining} onClick={onExplain}>Explain this</Button>
            </div>
          )}
          {explainError && <p role="alert" className="mt-3 text-sm text-loss">{explainError}</p>}
        </Panel>
      )}

      <div className="space-y-2 text-xs leading-relaxed text-muted">
        {disclosure(analysis).map((p) => <p key={p.slice(0, 24)}>{p}</p>)}
      </div>
    </div>
  );
}
