"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth } from "@/lib/format";
import { ANALOGUE_TITLE, clampedNote, EXAMPLES, FACTOR_LABEL, formatShock, impactTitle, recoveryText, signedPct,
  signedUsd0, sliderRows, windowText, type HoldingChange, type History, type Impact, type MapResult, type Narrative,
  type Replay, type SliderRow } from "@/lib/scenarios";
import { useMe } from "@/lib/session-context";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Button, ButtonLink, EmptyState, Field, inputClass, KeyMoment, Loading, Notice, PageHeader, Panel,
  Section } from "@/components/ui";

const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const DESCRIPTION = "Replay real market history on what you hold, or describe a scenario and see what it could do. "
  + "Simulations, not investment advice.";

/** Gemini's words in a small size: serif, with the daylight caption that marks AI. */
function AiLine({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="mt-2 max-w-[64ch]">
      <p className="font-serif text-[15px] leading-relaxed text-ink">{children}</p>
      <p className="mt-1 flex items-center gap-1.5 text-[11px] text-daylight-ink">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-[1px] bg-daylight" />{caption}
      </p>
    </div>
  );
}

function ChangeBars({ holdings }: { holdings: HoldingChange[] }) {
  const widest = Math.max(1, ...holdings.map((h) => Math.abs(h.change_usd)));
  return (
    <ul className="space-y-3">
      {holdings.map((h) => {
        const loss = h.change_usd < 0;
        return (
          <li key={h.symbol} className="text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="min-w-0 font-medium">{h.name}</span>
              <span className={`num ${loss ? "text-loss" : h.change_usd > 0 ? "text-gain" : "text-ink-2"}`}>
                {signedUsd0(h.change_usd)} <span className="text-muted">({signedPct(h.change_pct)})</span>
              </span>
            </div>
            <span className="mt-1.5 block h-1.5 rounded-full bg-line" aria-hidden="true">
              <span className={`block h-1.5 rounded-full ${loss ? "bg-loss" : "bg-gain"}`}
                style={{ width: `${(Math.abs(h.change_usd) / widest) * 100}%` }} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function ReplayCard({ replay }: { replay: Replay }) {
  const loss = replay.loss_usd < 0;
  return (
    <Panel className="scroll-mt-24 p-5 sm:p-6">
      <article id={`replay-${replay.key}`} aria-labelledby={`replay-${replay.key}-title`}
        className="grid gap-x-8 gap-y-4 md:grid-cols-2 2xl:grid-cols-1">
        <div className="min-w-0">
          <h3 id={`replay-${replay.key}-title`} className="font-semibold">{replay.title}</h3>
          <p className="text-xs text-muted">{windowText(replay.start, replay.end)}</p>
          <p className={`num wide mt-3 text-[30px] font-semibold leading-none tracking-[-0.02em] ${loss ? "text-loss" : "text-gain"}`}>
            {signedUsd0(replay.loss_usd)}
          </p>
          <p className="mt-1.5 text-sm text-ink-2">{signedPct(replay.loss_pct)} of what you hold today</p>
        </div>
        <dl className="min-w-0 space-y-2.5 text-sm">
          {replay.worst_holding && (
            <div>
              <dt className="text-muted">Hardest hit</dt>
              <dd className="text-ink">{replay.worst_holding.name} <span className="num text-loss">{signedPct(replay.worst_holding.pct)}</span></dd>
            </div>
          )}
          <div>
            <dt className="text-muted">Recovery</dt>
            <dd className="text-ink">
              {recoveryText(replay.recovery_months)}
              {replay.trough_month && <span className="text-muted"> from its low in {formatMonth(replay.trough_month)}</span>}
            </dd>
          </div>
          {replay.notes.length > 0 && (
            <div>
              <dt className="sr-only">Notes</dt>
              <dd>
                <ul className="space-y-1 text-xs text-muted">{replay.notes.map((n) => <li key={n}>{n}</li>)}</ul>
              </dd>
            </div>
          )}
        </dl>
      </article>
    </Panel>
  );
}

function ShockSlider({ row, onChange }: { row: SliderRow; onChange: (pct: number) => void }) {
  const id = `shock-${row.factor}`;
  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-semibold">{row.label}</label>
        <span className={`num text-sm font-semibold ${row.pct < 0 ? "text-loss" : row.pct > 0 ? "text-gain" : "text-ink-2"}`}>
          {formatShock(row.pct)}
        </span>
      </div>
      <input id={id} type="range" min={row.min} max={row.max} step={1} value={row.pct}
        aria-valuetext={formatShock(row.pct)} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-ink" />
      <div className="flex justify-between text-[11px] text-muted" aria-hidden="true">
        <span>{formatShock(row.min)}</span><span>{formatShock(row.max)}</span>
      </div>
      {row.clamped && <p className="mt-1 text-xs font-medium text-caution">{clampedNote(row.factor, row.pct)}</p>}
      {row.reason ? <AiLine caption="Gemini's reason">{row.reason}</AiLine>
        : <p className="mt-1 text-xs text-muted">Not moved by this scenario. Move it to add your own shock.</p>}
    </li>
  );
}

function ScenarioResult({ result, impact, shocks, onShock, updating, accountId }:
  { result: MapResult; impact: Impact; shocks: Record<string, number>; onShock: (factor: string, pct: number) => void;
    updating: boolean; accountId: string }) {
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState("");
  const p = result.proposal;
  const rows = sliderRows(result, shocks);
  const loss = impact.total_usd < 0;

  useEffect(() => { setNarrative(null); setExplainError(""); }, [shocks]);

  async function explain() {
    setExplaining(true);
    setExplainError("");
    try {
      setNarrative(await api<Narrative>(`/accounts/${accountId}/scenarios/explain`, { method: "POST", body: JSON.stringify({ shocks }) }));
    } catch (e) {
      setExplainError(message(e, "The explanation is unavailable right now; the figures above are complete."));
    } finally {
      setExplaining(false);
    }
  }

  return (
    <div className="space-y-10">
      <KeyMoment tone={loss ? "attention" : "good"} label={`If this happened: ${p.title}`} title={impactTitle(impact.total_usd, impact.total_pct)}>
        <p className="max-w-[62ch] text-[15px] text-ink-2">
          Over about {p.horizon_months} month{p.horizon_months === 1 ? "" : "s"}, with the shocks below applied to what you hold today.
          {updating && <span role="status" className="ml-2 text-xs text-muted">Updating…</span>}
        </p>
        <ChangeBars holdings={impact.holdings} />
      </KeyMoment>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <Section title="The shocks" description="Gemini proposed these; Atrium holds each within fixed limits. Move any of them and the figures above follow.">
          <Panel className="p-5">
            <ul className="divide-y divide-line">
              {rows.map((row) => <ShockSlider key={row.factor} row={row} onChange={(pct) => onShock(row.factor, pct)} />)}
            </ul>
          </Panel>
          {result.dropped.length > 0 && (
            <p className="mt-3 text-xs text-muted">Left out: {result.dropped.join(", ")}. Atrium does not model {result.dropped.length === 1 ? "that factor" : "those factors"}.</p>
          )}
        </Section>

        <div className="space-y-8">
          <Section title="Why these shocks">
            {p.analogue !== "none" && (
              <div>
                <p className="text-sm">
                  <span className="text-muted">Closest in history: </span>
                  <a href={`#replay-${p.analogue}`} className="font-semibold underline decoration-line-strong underline-offset-4 hover:decoration-ink">
                    {ANALOGUE_TITLE[p.analogue]}
                  </a>
                </p>
                {p.analogue_reason && <AiLine caption="Gemini's reading">{p.analogue_reason}</AiLine>}
              </div>
            )}
            {p.assumptions.length > 0 && (
              <div className="mt-5">
                <p className="text-sm font-semibold">Assumptions</p>
                <ul className="mt-1 list-disc space-y-1 pl-5 font-serif text-[15px] text-ink">
                  {p.assumptions.map((a) => <li key={a}>{a}</li>)}
                </ul>
                <p className="mt-1 flex items-center gap-1.5 text-[11px] text-daylight-ink">
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-[1px] bg-daylight" />Gemini&apos;s assumptions
                </p>
              </div>
            )}
          </Section>
          <Section title="Sources" description="What Gemini read on the web, through Google Search, before proposing the shocks.">
            {result.sources.length > 0 ? (
              <ul className="space-y-1.5 text-sm">
                {result.sources.map((s) => (
                  <li key={s.uri}>
                    <a href={s.uri} target="_blank" rel="noopener noreferrer" className="underline decoration-line-strong underline-offset-4 hover:decoration-ink">{s.title}</a>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">{result.sources_note ?? "No sources were cited."}</p>}
          </Section>
        </div>
      </div>

      <Section title="What this means for you" description="Gemini reads the figures above and explains them. It cannot change them.">
        {narrative ? <NarrativeView narrative={narrative} /> : (
          <Button variant="secondary" busy={explaining} onClick={explain}>{explaining ? "Gemini is reading the result" : "Explain this result"}</Button>
        )}
        {explainError && <div className="mt-3"><Notice tone="caution">{explainError}</Notice></div>}
      </Section>
    </div>
  );
}

export default function ScenariosPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [history, setHistory] = useState<History | null>(null);
  const [historyError, setHistoryError] = useState("");
  const [text, setText] = useState("");
  const [mapping, setMapping] = useState(false);
  const [mapError, setMapError] = useState("");
  const [result, setResult] = useState<MapResult | null>(null);
  const [shocks, setShocks] = useState<Record<string, number>>({});
  const [impact, setImpact] = useState<Impact | null>(null);
  const [edited, setEdited] = useState(0);
  const [updating, setUpdating] = useState(false);
  const [applyError, setApplyError] = useState("");
  const latest = useRef(0);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  useEffect(() => {
    if (!account) return;
    api<History>(`/accounts/${account.id}/scenarios/history`).then(setHistory)
      .catch((e) => setHistoryError(message(e, "Atrium could not replay history on your portfolio.")));
  }, [account]);

  useEffect(() => {
    if (!account || edited === 0) return;
    const ticket = ++latest.current;
    const timer = setTimeout(async () => {
      setUpdating(true);
      try {
        const next = await api<Impact>(`/accounts/${account.id}/scenarios/apply`, { method: "POST", body: JSON.stringify({ shocks }) });
        if (ticket === latest.current) { setImpact(next); setApplyError(""); }
      } catch (e) {
        if (ticket === latest.current) setApplyError(message(e, "Atrium could not apply the shocks. Try again."));
      } finally {
        if (ticket === latest.current) setUpdating(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [account, shocks, edited]);

  async function map(scenario: string) {
    if (!account || scenario.trim().length < 3) return;
    setText(scenario);
    setMapping(true);
    setMapError("");
    try {
      const r = await api<MapResult>(`/accounts/${account.id}/scenarios/map`, { method: "POST", body: JSON.stringify({ text: scenario.trim() }) });
      latest.current++;
      setResult(r);
      setShocks(r.shocks);
      setImpact(r.impact);
      setEdited(0);
      setApplyError("");
    } catch (e) {
      setMapError(message(e, "Atrium could not reach its server. Try again."));
    } finally {
      setMapping(false);
    }
  }

  function moveShock(factor: string, pct: number) {
    setShocks((s) => ({ ...s, [factor]: pct }));
    setEdited((n) => n + 1);
  }

  const header = <PageHeader title="Scenarios" description={DESCRIPTION} />;
  if (!account) return <>{header}<EmptyState title="No investment account yet">Choose an investor persona to stress-test a portfolio.</EmptyState></>;
  if (historyError) return <>{header}<Notice tone="error" title="Could not load your scenarios">{historyError}</Notice></>;
  if (!history) return <>{header}<Loading label="Replaying 2008, 2020 and 2022 on what you hold" /></>;
  if (history.empty) {
    return <>{header}<EmptyState title="Nothing to stress-test yet" action={<ButtonLink href="/investor/funds">Browse the funds</ButtonLink>}>
      Scenarios replay market history on the funds and shares you hold. Cash alone does not move with markets.
    </EmptyState></>;
  }

  const worst = [...history.replays].sort((a, b) => a.loss_pct - b.loss_pct)[0];
  return (
    <>
      {header}
      <div className="space-y-12">
        {worst && (
          <KeyMoment tone={worst.loss_usd < 0 ? "alert" : "good"} label="The hardest stretch since 2007, on what you hold"
            title={`${signedUsd0(worst.loss_usd)} (${signedPct(worst.loss_pct)}) in ${worst.title.replace(/^The /, "the ")}`}
            actions={<ButtonLink href="#your-scenario" variant="secondary">Try your own scenario</ButtonLink>}>
            <p className="max-w-[62ch] text-[15px] text-ink-2">
              {windowText(worst.start, worst.end)}. {recoveryText(worst.recovery_months)}.
            </p>
          </KeyMoment>
        )}

        <Section title="History" description="What the three hardest stretches of recent markets would do to what you hold today, from month-end closes.">
          <div className="grid gap-4 2xl:grid-cols-3">
            {history.replays.map((r) => <ReplayCard key={r.key} replay={r} />)}
          </div>
        </Section>

        <Section id="your-scenario" title="Your scenario"
          description="Describe a market scenario in your own words. Gemini, grounded with Google Search, proposes the shocks; Atrium's engine applies them to what you hold, and you can change every one.">
          <Panel className="space-y-4 p-5">
            <Field label="Scenario" hint="For example a rate move, an oil shock or a sector sell-off. Up to 400 characters.">
              <textarea value={text} maxLength={400} rows={2} onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void map(text); } }}
                placeholder="Oil at $150 and a US recession" className={`${inputClass} resize-y`} />
            </Field>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted">Try:</span>
              {EXAMPLES.map((x) => (
                <Button key={x} variant="secondary" size="sm" disabled={mapping} onClick={() => map(x)}>{x}</Button>
              ))}
            </div>
            <div>
              <Button busy={mapping} disabled={text.trim().length < 3} onClick={() => map(text)}>
                {mapping ? "Gemini is reading the scenario…" : "See what it could do"}
              </Button>
            </div>
          </Panel>
          {mapError && <div className="mt-4"><Notice tone="caution" title="The scenario was not mapped">{mapError}</Notice></div>}
        </Section>

        {result && (
          <div ref={resultRef} className="scroll-mt-24 space-y-6">
            {!result.proposal.in_scope && (
              <Notice tone="info" title="Gemini did not turn this into shocks">{result.proposal.refusal}</Notice>
            )}
            {applyError && <Notice tone="error">{applyError}</Notice>}
            {result.proposal.in_scope && impact && (
              <ScenarioResult result={result} impact={impact} shocks={shocks} onShock={moveShock} updating={updating} accountId={account.id} />
            )}
          </div>
        )}

        <WhyPanel title="how these figures are computed" model="Atrium scenario engine over real monthly history; Gemini proposes shocks only"
          evidence={[
            { label: "History replays", detail: "Each holding's change between month-end closes, from the committed monthly history. House funds use their ETFs, rebalanced monthly; an ETF that had not launched has its weight spread across the fund's others, and a share that had not listed uses its sector ETF or the S&P 500, with a note on the card." },
            { label: "Recovery", detail: "Months from the window's lowest month-end until what you hold today would have regained its starting value." },
            { label: "Your scenario", detail: "Gemini reads current context through Google Search, then proposes shocks for US and international stocks, bonds, cash and eleven sectors. Atrium holds each shock within fixed limits: stocks and sectors −70% to +50%, bonds −30% to +20%, cash −5% to +5%." },
            { label: "The engine", detail: `Each fund is looked through to its ETFs' sector weights; a sector with no shock of its own takes the US or international stock shock. Factors: ${Object.values(FACTOR_LABEL).join(", ")}.` },
            { label: "Before you rely on it", detail: "Simulations, not investment advice. The arithmetic is exact; the shocks are judgements, and real markets can move differently." },
          ]} />
      </div>
    </>
  );
}
