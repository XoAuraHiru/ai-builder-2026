"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { describeOrder, type ReviewNote, type TradeOrder } from "@/lib/trading";
import { HeldSkeleton } from "@/components/advisor-skeletons";
import { AiProse } from "@/components/ai-prose";
import { AiThinking } from "@/components/ai-thinking";
import { CardSection } from "@/components/card-section";
import { Confirmed } from "@/components/form-feedback";
import { CheckList } from "@/components/guardian-panel";
import { EASE, Reveal } from "@/components/motion";
import { TrustBadge, TrustScoreCard } from "@/components/score-badge";
import { Button, EmptyState, Field, inputClass, Notice, PageHeader, Sparkle } from "@/components/ui";

// The review note is one Gemini Pro call over the Guardian's report; its figures are then checked against that report.
const NOTE_STEPS = [
  "Gemini Pro is reading the Guardian's report",
  "Weighing the checks against the client's risk profile",
  "Writing questions for the client and a suggestion",
  "Checking every figure against the Guardian's report",
];

const SUGGESTION: Record<ReviewNote["suggestion"], string> = {
  release: "release the order", reject: "reject the order", call_client: "call the client before deciding",
};
const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function holdReasons(o: TradeOrder): string {
  return (o.guardian?.checks ?? []).filter((c) => c.outcome === "hold").map((c) => c.title.toLowerCase()).join(" and ") || "review";
}

function Review({ note }: { note: ReviewNote }) {
  return (
    <AiProse model={note.model} caption={`Written from the Guardian's report. A suggestion only: you decide.`}
      warning={note.verified ? undefined : `Check before relying on this: ${note.unsupported_figures.join(", ")} did not come from the Guardian.`}>
      <p>{note.summary}</p>
      <p className="mt-4 font-sans text-sm font-semibold">Worth weighing</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">{note.considerations.map((c) => <li key={c}>{c}</li>)}</ul>
      <p className="mt-4 font-sans text-sm font-semibold">Questions for the client</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">{note.questions_for_client.map((c) => <li key={c}>{c}</li>)}</ul>
      <p className="mt-4"><span className="font-sans text-sm font-semibold">Suggestion: {SUGGESTION[note.suggestion]}.</span> {note.suggestion_reason}</p>
    </AiProse>
  );
}

/** The design's hold banner: coral-50, a white icon tile, what was held and why, and the way in. */
function HoldBanner({ order, open, onOpen }: { order: TradeOrder; open: boolean; onOpen: () => void }) {
  return (
    <div className="flex flex-wrap items-start gap-4 rounded-panel bg-coral-50 p-5 sm:p-6">
      <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-white text-coral-700">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="M12 8v4" /><path d="M12 16h.01" />
        </svg>
      </span>
      <div className="flex min-w-0 flex-1 basis-[260px] flex-col gap-1.5">
        <h2 className="text-base font-semibold leading-[22px] text-ink-900">Order held: {describeOrder(order)}</h2>
        <p className="text-sm leading-[21px] text-ink-700">
          {order.client_name}, account <span className="code text-[13px]">{order.account_number}</span>. About{" "}
          <span className="num">{formatUsd(order.estimated_value)}</span> of {order.name.replace(/\.$/, "")}. Held for {holdReasons(order)} on {formatDate(order.created_at)}.
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <TrustBadge band={order.trust_band} score={order.trust_score} />
          <span className="num text-[13px] text-ink-700">Trust {order.trust_score} / 100</span>
        </div>
      </div>
      {!open && <Button variant="tonal" onClick={onOpen}>Review this order</Button>}
    </div>
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
  if (!orders) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <HeldSkeleton />}</>;
  return (
    <>
      {header}
      {done && <div className="mb-6"><Confirmed key={done} title="Decision recorded">{done}</Confirmed></div>}
      {orders.length === 0 ? <EmptyState title="Nothing is waiting">When the Guardian holds an order, it appears here with every check it made.</EmptyState> : (
        // The orders arrive in order; one that is released or rejected fades, then its space closes.
        <ul>
          <AnimatePresence>
            {orders.map((o, i) => {
              const open = o.id === selected;
              const trust = o.guardian?.trust;
              return (
                <motion.li key={o.id} className="overflow-hidden [&:last-child>div]:pb-0"
                  initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0, transition: { duration: 0.28, delay: Math.min(i, 8) * 0.06, ease: EASE } }}
                  exit={{ opacity: 0, height: 0, transition: { opacity: { duration: 0.2 }, height: { duration: 0.32, delay: 0.14, ease: EASE } } }}>
                  <div className="space-y-4 pb-6">
                    <HoldBanner order={o} open={open} onOpen={() => { setSelected(o.id); setDone(""); setNote(""); setError(""); }} />
                    {open && (
                      <Reveal className="grid gap-4 lg:grid-cols-2 lg:items-start">
                        <div className="min-w-0 space-y-4">
                          <CardSection title="What the Guardian checked" description="The checks as the client saw them when placing the order.">
                            <CheckList checks={o.guardian?.checks ?? []} />
                          </CardSection>
                          <TrustScoreCard title="Account trust" score={trust?.score ?? o.trust_score} band={trust?.band ?? o.trust_band}
                            signals={trust?.signals ?? null} evidence />
                        </div>
                        <div className="min-w-0 space-y-4">
                          <CardSection title="Review note" description="Gemini Pro reads the Guardian's report and suggests; you decide.">
                            {o.ai_review ? <Review note={o.ai_review} />
                              : busy === "note" ? <AiThinking steps={NOTE_STEPS} usually="about 16 s" /> : (
                                <Button variant="ai" disabled={Boolean(busy)} onClick={reviewNote}>
                                  <Sparkle />Ask Gemini Pro for a review note
                                </Button>
                              )}
                          </CardSection>
                          <CardSection title="Your decision" description="Saved with the decision and shown to the client.">
                            <div className="space-y-4">
                              <Field label="Your note">
                                <textarea className={`${inputClass} min-h-24`} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)}
                                  placeholder="For example: Called the client, who confirmed the order and understands the risk." />
                              </Field>
                              {error && <Notice tone="error">{error}</Notice>}
                              <div className="flex flex-wrap gap-2">
                                <Button busy={busy === "release"} disabled={Boolean(busy) && busy !== "release"} onClick={() => decide("release")}>Release the order</Button>
                                <Button variant="danger" busy={busy === "reject"} disabled={Boolean(busy) && busy !== "reject"} onClick={() => decide("reject")}>Reject the order</Button>
                              </div>
                            </div>
                          </CardSection>
                        </div>
                      </Reveal>
                    )}
                  </div>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </>
  );
}
