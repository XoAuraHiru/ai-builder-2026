"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { THINKING } from "@/lib/invest";
import { actionLabel, canPlace, estimateCost, orderBody, type Draft, type GuardianReport, type TradeOrder } from "@/lib/trading";
import { NarrativeView, type Narrative } from "@/components/ai-prose";
import { AiThinking } from "@/components/ai-thinking";
import { GuardianPanel } from "@/components/guardian-panel";
import { Button, Field, inputClass, Notice, Panel, Segmented } from "@/components/ui";
import { Confirmed } from "@/app/investor/_parts/confirmed";

const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

/** The order's outcome. One that went through (filled, waiting for its price, or with an advisor) confirms with a
 *  drawn check; one that was not placed is an error, without one. */
function Placed({ order }: { order: TradeOrder }) {
  const last = order.timeline[order.timeline.length - 1]?.note ?? "";
  const view = order.state === "filled" ? { tone: "success" as const, title: `Filled at ${formatUsd(order.fill_price ?? 0)} a share`, text: last }
    : order.state === "held" ? { tone: "caution" as const, title: "Sent to an advisor",
      text: "Nothing is bought or sold until an advisor decides. They see every check the Guardian made." }
    : order.state === "open" ? { tone: "info" as const, title: "Waiting to fill", text: last }
    : { tone: "error" as const, title: "Not placed", text: last };
  const action = <Link href="/investor/trades" className="whitespace-nowrap text-sm font-semibold text-green-600 hover:text-green-800 hover:underline">See it in Trades</Link>;
  if (view.tone === "error") return <Notice tone="error" title={view.title} action={action}>{view.text}</Notice>;
  return <Confirmed tone={view.tone} title={view.title} action={action}>{view.text}</Confirmed>;
}

/** `initialQuantity` and `analysisId` come from the front-door analyzer: the purchase records the analysis, once. */
export function OrderTicket({ accountId, symbol, price, held, onPlaced, initialQuantity, analysisId }:
  { accountId: string; symbol: string; price: string; held: number; onPlaced: () => void; initialQuantity?: number;
    analysisId?: string }) {
  const [draft, setDraft] = useState<Draft>({ symbol, side: "buy", order_type: "market", quantity: String(initialQuantity ?? 1), limit_price: "" });
  const [linked, setLinked] = useState(Boolean(analysisId));
  const [report, setReport] = useState<GuardianReport | null>(null);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [explainError, setExplainError] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState<"" | "check" | "place">("");
  const [error, setError] = useState("");
  const [placed, setPlaced] = useState<TradeOrder | null>(null);
  const run = useRef(0);

  function reset() {
    run.current += 1;
    setReport(null);
    setNarrative(null);
    setExplainError("");
    setAck(false);
    setError("");
    setBusy("");
  }

  function change(patch: Partial<Draft>) {
    reset();
    setPlaced(null);
    setDraft((d) => ({ ...d, ...patch }));
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    const built = orderBody(draft);
    if ("error" in built) {
      setError(built.error);
      return;
    }
    reset();
    setPlaced(null);
    const id = run.current;
    setBusy("check");
    try {
      const r = await api<GuardianReport>(`/accounts/${accountId}/orders/preview`, { method: "POST", body: JSON.stringify(built.body) });
      if (id !== run.current) return;
      setReport(r);
      api<{ narrative: Narrative }>(`/accounts/${accountId}/orders/explain`, { method: "POST", body: JSON.stringify(built.body) })
        .then((x) => { if (id === run.current) setNarrative(x.narrative); })
        .catch((err) => { if (id === run.current) setExplainError(message(err, "The explanation is unavailable right now.")); });
    } catch (err) {
      if (id === run.current) setError(message(err, "The Guardian could not check this order. Try again."));
    } finally {
      if (id === run.current) setBusy("");
    }
  }

  async function place() {
    const built = orderBody(draft, ack);
    if ("error" in built) {
      setError(built.error);
      return;
    }
    const fromAnalysis = linked && analysisId && draft.side === "buy";
    setBusy("place");
    setError("");
    try {
      const order = await api<TradeOrder>(`/accounts/${accountId}/orders`, { method: "POST",
        body: JSON.stringify(fromAnalysis ? { ...built.body, analysis_id: analysisId } : built.body) });
      if (fromAnalysis) setLinked(false);
      reset();
      setPlaced(order);
      onPlaced();
    } catch (err) {
      setError(message(err, "Atrium could not place this order. Try again."));
      setBusy("");
    }
  }

  const limit = draft.limit_price.replace(/[$,\s]/g, "");
  const estimate = estimateCost(draft.order_type === "limit" && limit ? limit : price, draft.quantity);
  return (
    <div className="space-y-5">
      <Panel className="p-5 sm:p-6">
        <form onSubmit={check} className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Segmented label="Buy or sell" value={draft.side} onChange={(v) => change({ side: v })}
              options={[{ value: "buy", label: "Buy" }, { value: "sell", label: "Sell" }]} />
            <Segmented label="Order type" value={draft.order_type} onChange={(v) => change({ order_type: v })}
              options={[{ value: "market", label: "Market" }, { value: "limit", label: "Limit" }]} />
          </div>
          <Field label="Shares" hint={draft.side === "sell" ? `You hold ${held} ${held === 1 ? "share" : "shares"}` : "Whole shares only"}>
            <input inputMode="numeric" className={`${inputClass} num`} value={draft.quantity}
              onChange={(e) => change({ quantity: e.target.value.replace(/[^\d]/g, "") })} />
          </Field>
          {draft.order_type === "limit" && (
            <Field label={draft.side === "buy" ? "The most you'll pay a share" : "The least you'll accept a share"}>
              <input inputMode="decimal" className={`${inputClass} num`} value={draft.limit_price} placeholder={Number(price).toFixed(2)}
                onChange={(e) => change({ limit_price: e.target.value })} />
            </Field>
          )}
          <p className="text-sm text-ink-700">{estimate !== null ? `About ${formatUsd(estimate)}, before the spread.` : "Enter how many shares."}</p>
          {linked && analysisId && draft.side === "buy" && (
            <p className="text-xs text-ink-500">Filled in from your analysis: the whole shares your amount buys at the latest price. The order records the analysis.</p>
          )}
          <Button type="submit" variant="tonal" busy={busy === "check"} className="w-full">Check order</Button>
        </form>
      </Panel>
      {error && <Notice tone="error">{error}</Notice>}
      {placed && <Placed order={placed} />}
      {report && (
        <GuardianPanel report={report}>
          {narrative ? <NarrativeView narrative={narrative} />
            : explainError ? <p className="text-sm text-ink-500">{explainError}</p>
            : <AiThinking {...THINKING.order} />}
          {report.verdict === "warn" && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 accent-green-500" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              I have read the warnings and want to go ahead.
            </label>
          )}
          <Button className="w-full" busy={busy === "place"} disabled={!canPlace(report.verdict, ack)} onClick={place}>
            {actionLabel(report.verdict)}
          </Button>
        </GuardianPanel>
      )}
    </div>
  );
}
