"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { concerns, describeOrder, STATE_COPY, VERDICT_COPY, type Orders, type TradeOrder } from "@/lib/trading";
import { useMe } from "@/lib/session-context";
import { CheckList } from "@/components/guardian-panel";
import { Badge, Button, ButtonLink, EmptyState, Figure, Loading, Notice, PageHeader, Section } from "@/components/ui";

const WAITING = ["held", "open"];
const at = (iso: string) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function Timeline({ order }: { order: TradeOrder }) {
  return (
    <ol className="ml-1.5 space-y-3 border-l border-line pl-4 text-sm">
      {order.timeline.map((s, i) => (
        <li key={`${s.state}-${i}`} className="relative">
          <span aria-hidden="true" className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-ink" />
          <span className="font-medium">{s.state.charAt(0).toUpperCase() + s.state.slice(1)}</span>{" "}
          <span className="text-xs text-muted">{at(s.at)}</span>
          <span className="block text-ink-2">{s.note}</span>
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
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="min-w-0 text-left">
          <span className="font-medium hover:underline">{describeOrder(order)}</span>
          <span className="block text-xs text-muted">{order.name}. Placed {formatDate(order.created_at)}.</span>
        </button>
        <span className="flex items-center gap-3">
          <span className="num text-sm">{formatUsd(value)}</span>
          <Badge tone={state.tone}>{state.label}</Badge>
        </span>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div key="body" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden">
            <div className="grid gap-6 pt-4 md:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium">What happened</p>
                <Timeline order={order} />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">The Guardian&apos;s verdict: {VERDICT_COPY[order.verdict]?.label ?? order.verdict}</p>
                {found.length ? <CheckList checks={found} /> : <p className="text-sm text-ink-2">Nothing in the checks stood in the way.</p>}
                {order.review_note && <p className="mt-3 text-sm text-ink-2">{order.reviewed_by_name ?? "The advisor"} noted: {order.review_note}</p>}
              </div>
            </div>
            {WAITING.includes(order.state) && (
              <div className="pt-4"><Button variant="secondary" busy={busy} onClick={() => onCancel(order.id)}>Cancel order</Button></div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export default function TradesPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [data, setData] = useState<Orders | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    if (!account) return;
    setData(await api<Orders>(`/accounts/${account.id}/orders`));
  }, [account]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load your trades. Try again."));
  }, [load]);

  async function cancel(id: string) {
    setBusy(id);
    setError("");
    try {
      await api(`/accounts/${account!.id}/orders/${id}/cancel`, { method: "POST" });
      await load();
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
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading your trades" />}</>;

  const waiting = data.orders.filter((o) => WAITING.includes(o.state));
  const done = data.orders.filter((o) => !WAITING.includes(o.state));
  const setAside = Number(data.cash) - Number(data.cash_free);
  return (
    <>
      {header}
      <div className="space-y-12">
        <div className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
          <Figure size="lg" label="Paper cash" value={formatUsd(data.cash)} />
          <Figure label="Free to trade" value={formatUsd(data.cash_free)}
            detail={setAside > 0 ? `${formatUsd(setAside)} is set aside for orders still waiting.` : "Nothing is set aside."} />
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        {waiting.length > 0 && (
          <Section title="Waiting" description="Orders with an advisor, and limit orders waiting for their price. You can cancel either.">
            <ul className="divide-y divide-line border-y border-line">
              {waiting.map((o) => <TradeRow key={o.id} order={o} busy={busy === o.id} onCancel={cancel} />)}
            </ul>
          </Section>
        )}
        <Section title="History">
          {done.length ? (
            <ul className="divide-y divide-line border-y border-line">
              {done.map((o) => <TradeRow key={o.id} order={o} busy={false} onCancel={cancel} />)}
            </ul>
          ) : <EmptyState title="No trades yet" action={<ButtonLink href="/investor/markets">Open Markets</ButtonLink>}>Every order shows the Guardian&apos;s checks before you place it.</EmptyState>}
        </Section>
      </div>
    </>
  );
}
