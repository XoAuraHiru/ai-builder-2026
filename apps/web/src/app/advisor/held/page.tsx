"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { describeOrder, type ReviewNote, type TradeOrder } from "@/lib/trading";
import { AiProse } from "@/components/ai-prose";
import { CheckList, VerdictScale } from "@/components/guardian-panel";
import { TrustBadge } from "@/components/score-badge";
import { Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Panel } from "@/components/ui";

const SUGGESTION: Record<ReviewNote["suggestion"], string> = {
  release: "release the order", reject: "reject the order", call_client: "call the client before deciding",
};
const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function Review({ note }: { note: ReviewNote }) {
  return (
    <AiProse caption={`Written by ${note.model} from the Guardian's report. A suggestion only: you decide.`}
      warning={note.verified ? undefined : `Check before relying on this: ${note.unsupported_figures.join(", ")} did not come from the Guardian.`}>
      <p>{note.summary}</p>
      <p className="mt-4 font-semibold">Worth weighing</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">{note.considerations.map((c) => <li key={c}>{c}</li>)}</ul>
      <p className="mt-4 font-semibold">Questions for the client</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">{note.questions_for_client.map((c) => <li key={c}>{c}</li>)}</ul>
      <p className="mt-4"><span className="font-semibold">Suggestion: {SUGGESTION[note.suggestion]}.</span> {note.suggestion_reason}</p>
    </AiProse>
  );
}

export default function HeldOrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const load = useCallback(async () => {
    const rows = await api<TradeOrder[]>("/orders/held");
    setOrders(rows);
    setSelected((s) => (s && rows.some((o) => o.id === s) ? s : rows[0]?.id ?? null));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load the held orders. Try again.")));
  }, [load]);

  const order = orders?.find((o) => o.id === selected) ?? null;

  async function reviewNote() {
    if (!order) return;
    setBusy("note");
    setError("");
    try {
      const updated = await api<TradeOrder>(`/orders/${order.id}/review-note`, { method: "POST" });
      setOrders((list) => list && list.map((o) => (o.id === updated.id ? updated : o)));
    } catch (e) {
      setError(msg(e, "The review note is unavailable right now."));
    } finally {
      setBusy("");
    }
  }

  async function decide(action: "release" | "reject") {
    if (!order) return;
    setBusy(action);
    setError("");
    try {
      const o = await api<TradeOrder>(`/orders/${order.id}/${action}`, { method: "POST", body: JSON.stringify({ note }) });
      setDone(`${action === "release" ? "Released" : "Rejected"}: ${describeOrder(o)} for ${o.client_name}. ${o.timeline[o.timeline.length - 1]?.note ?? ""}`);
      setNote("");
      await load();
    } catch (e) {
      setError(msg(e, "Atrium could not record the decision. Try again."));
    } finally {
      setBusy("");
    }
  }

  const header = (
    <PageHeader title="Held orders"
      description="Orders the Pre-trade Guardian held for a person to decide: far outside a client's risk profile, too concentrated, or a possible account takeover. Nothing is bought or sold until you release it." />
  );
  if (!orders) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading held orders" />}</>;
  return (
    <>
      {header}
      {done && <div className="mb-6"><Notice tone="success" title="Decision recorded">{done}</Notice></div>}
      {orders.length === 0 ? <EmptyState title="Nothing is waiting">When the Guardian holds an order, it appears here with every check it made.</EmptyState> : (
        <div className="grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
          <ul className="h-fit divide-y divide-line border-y border-line">
            {orders.map((o) => {
              const reasons = (o.guardian?.checks ?? []).filter((c) => c.outcome === "hold").map((c) => c.title.toLowerCase());
              return (
                <li key={o.id}>
                  <button type="button" onClick={() => { setSelected(o.id); setDone(""); setNote(""); }} aria-current={o.id === selected}
                    className={`block w-full px-2 py-3 text-left ${o.id === selected ? "bg-surface" : "hover:bg-surface/60"}`}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">{o.client_name}</span>
                      <TrustBadge band={o.trust_band} score={o.trust_score} />
                    </span>
                    <span className="block text-sm text-ink-2">{describeOrder(o)}</span>
                    <span className="block text-xs text-muted">Held for {reasons.join(" and ") || "review"}. {formatDate(o.created_at)}.</span>
                  </button>
                </li>
              );
            })}
          </ul>
          {order && (
            <div className="min-w-0 space-y-6">
              <Panel className="space-y-5 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-[17px] font-semibold">{describeOrder(order)}</h2>
                    <p className="text-sm text-ink-2">{order.name}. {order.client_name}, account {order.account_number}. About {formatUsd(order.estimated_value)}.</p>
                  </div>
                  <TrustBadge band={order.trust_band} score={order.trust_score} />
                </div>
                {order.guardian?.verdict && <VerdictScale verdict={order.guardian.verdict} />}
                <CheckList checks={order.guardian?.checks ?? []} />
                <p className="text-xs text-muted">The checks as the client saw them when placing the order.</p>
              </Panel>
              <section className="space-y-3">
                <h2 className="text-[17px] font-semibold">Review note</h2>
                {order.ai_review ? <Review note={order.ai_review} /> : (
                  <div className="flex flex-wrap items-center gap-3">
                    <Button variant="secondary" busy={busy === "note"} onClick={reviewNote}>Ask Gemini Pro for a review note</Button>
                    <span className="text-xs text-muted">It reads the Guardian&apos;s report and suggests; it takes about half a minute.</span>
                  </div>
                )}
              </section>
              <section className="space-y-3 border-t border-line pt-6">
                <Field label="Your note" hint="Saved with the decision and shown to the client.">
                  <textarea className={`${inputClass} min-h-20`} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)}
                    placeholder="For example: Called the client, who confirmed the order and understands the risk." />
                </Field>
                {error && <Notice tone="error">{error}</Notice>}
                <div className="flex flex-wrap gap-2">
                  <Button busy={busy === "release"} onClick={() => decide("release")}>Release the order</Button>
                  <Button variant="danger" busy={busy === "reject"} onClick={() => decide("reject")}>Reject the order</Button>
                </div>
              </section>
            </div>
          )}
        </div>
      )}
    </>
  );
}
