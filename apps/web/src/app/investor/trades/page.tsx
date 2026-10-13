"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { concerns, describeOrder, STATE_COPY, VERDICT_COPY, type Orders, type TradeOrder } from "@/lib/trading";
import { useMe } from "@/lib/session-context";
import { CheckList } from "@/components/guardian-panel";
import { TickerTile } from "@/components/market-bits";
import { EASE } from "@/components/motion";
import { Badge, Button, ButtonLink, EmptyState, Figure, Notice, PageHeader, Panel, Section } from "@/components/ui";
import { Confirmed } from "../_parts/confirmed";
import { FigureSkeleton, LoadingRegion, SectionTitleSkeleton, TileRowSkeleton } from "../_parts/shapes";

const WAITING = ["held", "open"];
// A row leaving a list (an order cancelled out of Waiting) fades and folds away; one arriving (in History) unfolds.
const ROW = {
  initial: { opacity: 0, height: 0 }, animate: { opacity: 1, height: "auto" }, exit: { opacity: 0, height: 0 },
  transition: { duration: 0.28, ease: EASE },
} as const;

/** Trades while orders load: the cash figures, then the waiting orders and the history as ticker rows. */
function TradesSkeleton() {
  return (
    <LoadingRegion label="Loading your trades" className="space-y-12">
      <div className="grid items-end gap-x-10 gap-y-6 rounded-panel border border-sand-200 bg-white p-6 sm:grid-cols-2">
        <FigureSkeleton size="lg" /><FigureSkeleton />
      </div>
      {[2, 4].map((rows, i) => (
        <div key={i}>
          <SectionTitleSkeleton description={i === 0} />
          <div className="divide-y divide-sand-100 rounded-panel border border-sand-200 bg-white px-6 py-1">
            {Array.from({ length: rows }, (_, r) => <TileRowSkeleton key={r} />)}
          </div>
        </div>
      ))}
    </LoadingRegion>
  );
}
const at = (iso: string) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function Timeline({ order }: { order: TradeOrder }) {
  return (
    <ol className="ml-1.5 space-y-3 border-l border-sand-200 pl-4 text-sm">
      {order.timeline.map((s, i) => (
        <li key={`${s.state}-${i}`} className="relative">
          <span aria-hidden="true" className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-green-500 ring-2 ring-white" />
          <span className="font-medium">{s.state.charAt(0).toUpperCase() + s.state.slice(1)}</span>{" "}
          <span className="text-xs text-ink-500">{at(s.at)}</span>
          <span className="block text-ink-700">{s.note}</span>
        </li>
      ))}
    </ol>
  );
}

function TradeRow({ order, busy, onCancel }: { order: TradeOrder; busy: boolean; onCancel: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const state = STATE_COPY[order.state] ?? { label: order.state, tone: "neutral" as const };
  const found = concerns(order.guardian?.checks);
  const value = order.fill_price ? Number(order.fill_price) * order.quantity : Number(order.estimated_value);
  return (
    <motion.li {...ROW} className="overflow-hidden">
      <div className="py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex min-w-0 items-center gap-3 text-left">
          <TickerTile symbol={order.symbol} />
          <span className="min-w-0">
            <span className="block text-sm font-medium hover:underline">{describeOrder(order)}</span>
            <span className="block text-xs text-ink-500">{order.name}. Placed {formatDate(order.created_at)}.</span>
          </span>
        </button>
        <span className="flex items-center gap-3">
          <span className="num text-sm">{formatUsd(value)}</span>
          <Badge tone={state.tone}>{state.label}</Badge>
        </span>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div key="body" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: EASE }} className="overflow-hidden">
            <div className="grid gap-6 pt-4 md:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium">What happened</p>
                <Timeline order={order} />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">The Guardian&apos;s verdict: {VERDICT_COPY[order.verdict]?.label ?? order.verdict}</p>
                {found.length ? <CheckList checks={found} /> : <p className="text-sm text-ink-700">Nothing in the checks stood in the way.</p>}
                {order.review_note && <p className="mt-3 text-sm text-ink-700">{order.reviewed_by_name ?? "The advisor"} noted: {order.review_note}</p>}
              </div>
            </div>
            {WAITING.includes(order.state) && (
              <div className="pt-4"><Button variant="danger" busy={busy} onClick={() => onCancel(order.id)}>Cancel order</Button></div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </motion.li>
  );
}

export default function TradesPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [data, setData] = useState<Orders | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [cancelled, setCancelled] = useState("");

  const load = useCallback(async () => {
    if (!account) return;
    setData(await api<Orders>(`/accounts/${account.id}/orders`));
  }, [account]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load your trades. Try again."));
  }, [load]);

  async function cancel(id: string) {
    const order = data?.orders.find((o) => o.id === id);
    setBusy(id);
    setError("");
    setCancelled("");
    try {
      await api(`/accounts/${account!.id}/orders/${id}/cancel`, { method: "POST" });
      await load();
      if (order) setCancelled(`${describeOrder(order)}. Nothing was bought or sold.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Atrium could not cancel the order. Try again.");
    } finally {
      setBusy("");
    }
  }

  const header = (
    <PageHeader title="Trades" description="Orders for shares and ETFs, each with the Pre-trade Guardian's verdict. Paper money at real prices."
      actions={<ButtonLink href="/investor/markets">Find something to trade</ButtonLink>} />
  );
  if (!account) return <>{header}<EmptyState title="No investment account yet">Choose an investor persona to trade.</EmptyState></>;
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <TradesSkeleton />}</>;

  const waiting = data.orders.filter((o) => WAITING.includes(o.state));
  const done = data.orders.filter((o) => !WAITING.includes(o.state));
  const setAside = Number(data.cash) - Number(data.cash_free);
  return (
    <>
      {header}
      <div className="space-y-12">
        <Panel className="grid items-end gap-x-10 gap-y-6 p-6 sm:grid-cols-2">
          <Figure size="lg" label="Paper cash" value={formatUsd(data.cash)} />
          <Figure label="Free to trade" value={formatUsd(data.cash_free)}
            detail={setAside > 0 ? `${formatUsd(setAside)} is set aside for orders still waiting.` : "Nothing is set aside."} />
        </Panel>
        {error && <Notice tone="error">{error}</Notice>}
        {cancelled && <Confirmed title="Order cancelled">{cancelled}</Confirmed>}
        <AnimatePresence initial={false}>
          {waiting.length > 0 && (
            <motion.div key="waiting" exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.28, ease: EASE }} className="overflow-hidden">
              <Section title="Waiting" description="Orders with an advisor, and limit orders waiting for their price. You can cancel either.">
                <Panel className="px-6 py-1">
                  <ul className="divide-y divide-sand-100">
                    <AnimatePresence initial={false}>
                      {waiting.map((o) => <TradeRow key={o.id} order={o} busy={busy === o.id} onCancel={cancel} />)}
                    </AnimatePresence>
                  </ul>
                </Panel>
              </Section>
            </motion.div>
          )}
        </AnimatePresence>
        <Section title="History">
          {done.length ? (
            <Panel className="px-6 py-1">
              <ul className="divide-y divide-sand-100">
                <AnimatePresence initial={false}>
                  {done.map((o) => <TradeRow key={o.id} order={o} busy={false} onCancel={cancel} />)}
                </AnimatePresence>
              </ul>
            </Panel>
          ) : <EmptyState title="No trades yet" action={<ButtonLink href="/investor/markets">Open Markets</ButtonLink>}>Every order shows the Guardian&apos;s checks before you place it.</EmptyState>}
        </Section>
      </div>
    </>
  );
}
