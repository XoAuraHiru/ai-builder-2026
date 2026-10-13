"use client";

import { useEffect, useReducer, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { formatMonth } from "@/lib/format";
import { ANALOGUE_TITLE, canMap, clampedNote, EXAMPLES, FACTOR_LABEL, formatShock, impactTitle, INITIAL_STUDIO,
  recoveryText, signedPct, signedUsd0, sliderRows, studio, windowText, type HoldingChange, type History, type Impact,
  type MapResult, type Narrative, type Replay, type SliderRow, type Studio } from "@/lib/scenarios";
import { useMe } from "@/lib/session-context";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Button, ButtonLink, EmptyState, Field, inputClass, KeyMoment, Loading, Notice, PageHeader, Panel,
  Section, Sparkle } from "@/components/ui";

const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const DESCRIPTION = "Replay real market history on what you hold, or describe a scenario and see what it could do. "
  + "Simulations, not investment advice.";
const LINK = "font-semibold text-green-600 hover:text-green-800 hover:underline";

/** Gemini's words in a small size: the violet panel and Newsreader, captioned with the sparkle, like AiProse. */
function AiLine({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="mt-2.5 max-w-[64ch] rounded-control bg-ai-50 px-3.5 py-2.5">
      <div className="font-serif text-[15px] leading-[22px] text-ink-900">{children}</div>
      <p className="mt-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-ai-700"><Sparkle size={10} />{caption}</p>
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
              <span className={`num ${loss ? "text-coral-700" : h.change_usd > 0 ? "text-green-700" : "text-ink-700"}`}>
                {signedUsd0(h.change_usd)} <span className="text-ink-500">({signedPct(h.change_pct)})</span>
              </span>
            </div>
            <span className="mt-1.5 block h-1.5 rounded-full bg-sand-100" aria-hidden="true">
              <span className={`block h-1.5 rounded-full ${loss ? "bg-coral-500" : "bg-green-500"}`}
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
    <Panel className="scroll-mt-24 p-6">
      <article id={`replay-${replay.key}`} aria-labelledby={`replay-${replay.key}-title`}
        className="grid gap-x-8 gap-y-4 md:grid-cols-2 xl:grid-cols-1">
        <div className="min-w-0">
          <h3 id={`replay-${replay.key}-title`} className="font-semibold">{replay.title}</h3>
          <p className="text-xs text-ink-500">{windowText(replay.start, replay.end)}</p>
          <p className={`num mt-3 text-[30px] font-medium leading-[34px] tracking-[-0.02em] ${loss ? "text-coral-700" : "text-green-700"}`}>
            {signedUsd0(replay.loss_usd)}
          </p>
          <p className="mt-1.5 text-sm text-ink-700">{signedPct(replay.loss_pct)} of what you hold today</p>
        </div>
        <dl className="min-w-0 space-y-2.5 text-sm">
          {replay.worst_holding && (
            <div>
              <dt className="text-ink-500">Hardest hit</dt>
              <dd className="text-ink-900">{replay.worst_holding.name} <span className="num text-coral-700">{signedPct(replay.worst_holding.pct)}</span></dd>
            </div>
          )}
          <div>
            <dt className="text-ink-500">Recovery</dt>
            <dd className="text-ink-900">
              {recoveryText(replay.recovery_months)}
              {replay.trough_month && <span className="text-ink-500"> from its low in {formatMonth(replay.trough_month)}</span>}
            </dd>
          </div>
          {replay.notes.length > 0 && (
            <div>
              <dt className="sr-only">Notes</dt>
              <dd>
                <ul className="space-y-1 text-xs text-ink-500">{replay.notes.map((n) => <li key={n}>{n}</li>)}</ul>
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
        <span className={`num text-sm font-semibold ${row.pct < 0 ? "text-coral-700" : row.pct > 0 ? "text-green-700" : "text-ink-700"}`}>
          {formatShock(row.pct)}
        </span>
      </div>
      <input id={id} type="range" min={row.min} max={row.max} step={1} value={row.pct}
        aria-valuetext={formatShock(row.pct)} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-green-500" />
      <div className="flex justify-between text-[11px] text-ink-500" aria-hidden="true">
        <span>{formatShock(row.min)}</span><span>{formatShock(row.max)}</span>
      </div>
      {row.clamped && <p className="mt-1 text-xs font-medium text-amber-800">{clampedNote(row.factor, row.pct)}</p>}
      {row.reason ? <AiLine caption="Gemini's reason">{row.reason}</AiLine>
        : <p className="mt-1 text-xs text-ink-500">Not moved by this scenario. Move it to add your own shock.</p>}
    </li>
  );
}

/** Google's own rendering of the searches behind the sources. Google's terms ask for it to be shown as sent; a
 * sandboxed frame keeps its markup and styles away from the page, and its links open in a new tab. */
function SearchSuggestions({ html }: { html: string }) {
  const doc = `<!doctype html><html><head><meta charset="utf-8"><base target="_blank"></head>`
    + `<body style="margin:0">${html}</body></html>`;
  return (
    <iframe title="Google Search suggestions" srcDoc={doc} sandbox="allow-popups allow-popups-to-escape-sandbox"
      className="mt-3 h-18 w-full rounded-control border border-sand-200 bg-white" />
  );
}

function ScenarioResult({ s, onShock, onExplain }:
  { s: Studio & { result: MapResult; impact: Impact }; onShock: (factor: string, pct: number) => void; onExplain: () => void }) {
  const { result, impact, shocks, updating, narrative, explaining, explainError } = s;
  const p = result.proposal;
  const rows = sliderRows(result, shocks);
  const loss = impact.total_usd < 0;
  const total = impactTitle(impact.total_usd, impact.total_pct);

  return (
    <div className="space-y-10">
      <p className="sr-only" aria-live="polite">{`If this happened: ${total}`}</p>
      <KeyMoment tone={loss ? "alert" : "good"} label={`If this happened: ${p.title}`} title={total}>
        <p className="max-w-[62ch] text-[15px] text-ink-700">
          Over about {p.horizon_months} month{p.horizon_months === 1 ? "" : "s"}, with the shocks below applied to what you hold today.
          {updating && <span className="ml-2 text-xs text-ink-500">Updating…</span>}
        </p>
        <ChangeBars holdings={impact.holdings} />
      </KeyMoment>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <Section title="The shocks" description="Gemini proposed these; Atrium holds each within fixed limits. Move any of them and the figures above follow.">
          <Panel className="p-6">
            <ul className="divide-y divide-sand-100">
              {rows.map((row) => <ShockSlider key={row.factor} row={row} onChange={(pct) => onShock(row.factor, pct)} />)}
            </ul>
          </Panel>
          {result.dropped.length > 0 && (
            <p className="mt-3 text-xs text-ink-500">Left out: {result.dropped.join(", ")}. Atrium does not model {result.dropped.length === 1 ? "that factor" : "those factors"}.</p>
          )}
        </Section>

        <div className="space-y-8">
          <Section title="Why these shocks">
            <Panel className="p-6">
              {p.analogue !== "none" && (
                <div>
                  <p className="text-sm">
                    <span className="text-ink-500">Closest in history: </span>
                    <a href={`#replay-${p.analogue}`} className={LINK}>{ANALOGUE_TITLE[p.analogue]}</a>
                  </p>
                  {p.analogue_reason && <AiLine caption="Gemini's reading">{p.analogue_reason}</AiLine>}
                </div>
              )}
              {p.assumptions.length > 0 && (
                <div className={p.analogue !== "none" ? "mt-5" : ""}>
                  <p className="text-sm font-semibold">Assumptions</p>
                  <AiLine caption="Gemini's assumptions">
                    <ul className="list-disc space-y-1 pl-5">{p.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
                  </AiLine>
                </div>
              )}
              {p.analogue === "none" && p.assumptions.length === 0 && <p className="text-sm text-ink-500">Gemini gave no analogue or assumptions for this scenario.</p>}
            </Panel>
          </Section>
          <Section title="Sources" description="What Gemini read on the web, through Google Search, before proposing the shocks.">
            <Panel className="p-6">
              {result.sources.length > 0 ? (
                <ul className="space-y-1.5 text-sm">
                  {result.sources.map((s) => (
                    <li key={s.uri}>
                      <a href={s.uri} target="_blank" rel="noopener noreferrer" className={LINK}>{s.title}</a>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-ink-500">{result.sources_note ?? "No sources were cited."}</p>}
              {result.search_suggestions && <SearchSuggestions html={result.search_suggestions} />}
            </Panel>
          </Section>
        </div>
      </div>

      <Section title="What this means for you" description="Gemini reads the figures above and explains them. It cannot change them.">
        {narrative ? <NarrativeView narrative={narrative} /> : (
          <Button variant="ai" busy={explaining} onClick={onExplain}>{!explaining && <Sparkle />}{explaining ? "Gemini is reading the result" : "Explain this result"}</Button>
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
  const [s, dispatch] = useReducer(studio, INITIAL_STUDIO);
  const tickets = useRef(0);
  const resultRef = useRef<HTMLDivElement>(null);
  const { result, shocks, edits } = s;

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  useEffect(() => {
    if (!account) return;
    api<History>(`/accounts/${account.id}/scenarios/history`).then(setHistory)
      .catch((e) => setHistoryError(message(e, "Atrium could not replay history on your portfolio.")));
  }, [account]);

  useEffect(() => {
    if (!account || edits === 0) return;
    const timer = setTimeout(async () => {
      const ticket = ++tickets.current;
      dispatch({ type: "applying", ticket });
      try {
        const impact = await api<Impact>(`/accounts/${account.id}/scenarios/apply`, { method: "POST", body: JSON.stringify({ shocks }) });
        dispatch({ type: "applied", ticket, impact });
      } catch (e) {
        dispatch({ type: "applyFailed", ticket, error: message(e, "Atrium could not apply the shocks. Try again.") });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [account, shocks, edits]);

  async function map(scenario: string) {
    if (!account || !canMap(s, scenario)) return;
    const ticket = ++tickets.current;
    setText(scenario);
    dispatch({ type: "map", ticket });
    try {
      const r = await api<MapResult>(`/accounts/${account.id}/scenarios/map`, { method: "POST", body: JSON.stringify({ text: scenario.trim() }) });
      dispatch({ type: "mapped", ticket, result: r });
    } catch (e) {
      dispatch({ type: "mapFailed", ticket, error: message(e, "Atrium could not reach its server. Try again.") });
    }
  }

  async function explain() {
    if (!account) return;
    const forShocks = shocks;
    dispatch({ type: "explain" });
    try {
      const narrative = await api<Narrative>(`/accounts/${account.id}/scenarios/explain`, { method: "POST", body: JSON.stringify({ shocks: forShocks }) });
      dispatch({ type: "explained", forShocks, narrative });
    } catch (e) {
      dispatch({ type: "explainFailed", forShocks, error: message(e, "The explanation is unavailable right now; the figures above are complete.") });
    }
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
            <p className="max-w-[62ch] text-[15px] text-ink-700">
              {windowText(worst.start, worst.end)}. {recoveryText(worst.recovery_months)}.
            </p>
          </KeyMoment>
        )}

        <Section title="History" description="What the three hardest stretches of recent markets would do to what you hold today, from month-end closes.">
          <div className="grid gap-4 xl:grid-cols-3">
            {history.replays.map((r) => <ReplayCard key={r.key} replay={r} />)}
          </div>
        </Section>

        <Section id="your-scenario" title="Your scenario"
          description="Describe a market scenario in your own words. Gemini, grounded with Google Search, proposes the shocks; Atrium's engine applies them to what you hold, and you can change every one.">
          {history.paused ? (
            <Notice tone="caution" title="Only the history replays are available right now">
              {history.paused} The replays above still work; they use no AI.
            </Notice>
          ) : (
            <Panel className="space-y-4 p-6">
              <Field label="Scenario" hint="For example a rate move, an oil shock or a sector sell-off. Up to 400 characters.">
                <textarea value={text} maxLength={400} rows={2} onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void map(text); } }}
                  placeholder="Oil at $150 and a US recession" className={`${inputClass} resize-y`} />
              </Field>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-500">Try:</span>
                {EXAMPLES.map((x) => (
                  <Button key={x} variant="secondary" size="sm" disabled={s.mapping} onClick={() => map(x)}>{x}</Button>
                ))}
              </div>
              <div>
                <Button busy={s.mapping} disabled={!canMap(s, text)} onClick={() => map(text)}>
                  {s.mapping ? "Gemini is reading the scenario…" : "See what it could do"}
                </Button>
              </div>
            </Panel>
          )}
          {s.mapError && (
            <div role="alert" className="mt-4"><Notice tone="caution" title="The scenario was not mapped">{s.mapError}</Notice></div>
          )}
        </Section>

        {result && (
          <div ref={resultRef} className="scroll-mt-24 space-y-6">
            {!result.proposal.in_scope && (
              <div role="status"><Notice tone="info" title="Gemini did not turn this into shocks">{result.proposal.refusal}</Notice></div>
            )}
            {s.applyError && <Notice tone="error">{s.applyError}</Notice>}
            {result.proposal.in_scope && s.impact && (
              <ScenarioResult s={{ ...s, result, impact: s.impact }} onExplain={explain}
                onShock={(factor, pct) => dispatch({ type: "move", factor, pct })} />
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
